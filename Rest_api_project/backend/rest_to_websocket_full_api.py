import json
import threading
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from websocket import create_connection
from typing import List

app = FastAPI(title="REST to ROS WebSocket - cmd_vel only")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# WebSocket address of ROS bridge
# =========================
ROSBRIDGE_WS = "ws://localhost:9090"

# =========================
# In-memory feedback storage
# =========================
robot_feedback_log: List[str] = []

# =========================
# FIXED robot velocities (as per supervisor)
# =========================
FIXED_LINEAR_SPEED = 0.5      # m/s
FIXED_ANGULAR_SPEED = 4.5     # rad/s

# =========================
# Persistent WebSocket connection
# (One connection reused for ALL requests instead of opening
#  a new one per message — eliminates handshake overhead)
# =========================
ws_lock = threading.Lock()
ws_conn = None


def get_ws():
    """Return a connected WebSocket, creating one if needed."""
    global ws_conn
    if ws_conn is None:
        ws_conn = create_connection(ROSBRIDGE_WS)
        print("✅ Persistent WebSocket connected to rosbridge")
    return ws_conn


def reset_ws():
    """Force reconnect on next call (e.g. after a network error)."""
    global ws_conn
    if ws_conn is not None:
        try:
            ws_conn.close()
        except Exception:
            pass
    ws_conn = None


# =========================
# Direction → Velocity mapping (FIXED)
# =========================
def direction_to_velocity(direction):
    if direction == "forward":
        return FIXED_LINEAR_SPEED, 0.0
    elif direction == "backward":
        return -FIXED_LINEAR_SPEED, 0.0
    elif direction == "left":
        return 0.0, FIXED_ANGULAR_SPEED
    elif direction == "right":
        return 0.0, -FIXED_ANGULAR_SPEED
    else:
        return 0.0, 0.0


# =========================
# Send ROS message via persistent WebSocket
# =========================
def send_ros_message(topic, msg):
    try:
        ros_msg = {
            "op": "publish",
            "topic": topic,
            "msg": msg,
        }
        with ws_lock:
            ws = get_ws()
            ws.send(json.dumps(ros_msg))
        return True
    except Exception as e:
        print("❌ WebSocket Error:", e)
        with ws_lock:
            reset_ws()
        return False


# =========================
# Startup / shutdown hooks
# =========================
@app.on_event("startup")
def startup_event():
    """Open the WebSocket connection at startup so the first request
    doesn't have to pay the handshake cost."""
    try:
        with ws_lock:
            get_ws()
    except Exception as e:
        print(f"⚠️  Could not connect to rosbridge at startup: {e}")
        print("   The connection will be retried on first request.")


@app.on_event("shutdown")
def shutdown_event():
    """Close the persistent WebSocket cleanly on shutdown."""
    with ws_lock:
        reset_ws()


# =========================
# REST endpoint
# =========================
@app.post("/api/robot/send-task")
async def send_task(request: Request):
    data = await request.json()
    try:
        # -------------------------
        # Task metadata (kept in API memory only — NOT sent to ROS)
        # -------------------------
        task_id = data.get("task_id", "unknown")
        fault_type = data.get("fault_type", "none")
        location_x = float(data.get("location_x", 0.0))
        location_y = float(data.get("location_y", 0.0))
        movement_duration = float(data.get("movement_duration", 3.0))

        # -------------------------
        # Motion intent (ONLY direction matters for cmd_vel)
        # -------------------------
        direction = data.get("direction")
        linear_x, angular_z = direction_to_velocity(direction)

        # -------------------------
        # Start robot motion (only /cmd_vel — this is what actually
        # moves the robot. Metadata topics are not needed for movement.)
        # -------------------------
        send_ros_message(
            "/cmd_vel",
            {
                "linear": {"x": linear_x, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": angular_z},
            },
        )

        # Move for the requested duration
        # time.sleep(movement_duration)

        # -------------------------
        # Stop robot (CRITICAL)
        # -------------------------
        send_ros_message(
            "/cmd_vel",
            {
                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
            },
        )

        # -------------------------
        # Simulated feedback
        # -------------------------
        robot_feedback_log.clear()
        robot_feedback_log.extend(
            [
                "📦 Task Dispatched",
                "🤖 Robot Moving",
                "🛑 Robot Stopped",
                "🏁 Task Completed",
            ]
        )

        return {
            "status": "sent to websocket",
            "task_id": task_id,
            "direction": direction,
            "duration": movement_duration,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# =========================
# Feedback endpoint
# =========================
@app.get("/api/robot/status-updates")
def get_status_updates():
    return JSONResponse(content={"updates": robot_feedback_log})
