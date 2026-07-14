import json
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from websocket import create_connection
from typing import List

app = FastAPI(title="REST to ROS WebSocket with Feedback")

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
# Send ROS message via WebSocket
# =========================
def send_ros_message(topic, msg_type, msg):
    try:
        ws = create_connection(ROSBRIDGE_WS)
        ros_msg = {
            "op": "publish",
            "topic": topic,
            "msg": msg
        }
        ws.send(json.dumps(ros_msg))
        ws.close()
        return True
    except Exception as e:
        print("❌ WebSocket Error:", e)
        return False

# =========================
# REST endpoint
# =========================
@app.post("/api/robot/send-task")
async def send_task(request: Request):
    data = await request.json()
    try:
        # -------------------------
        # Task metadata
        # -------------------------
        task_id = data.get("task_id", "unknown")
        fault_type = data.get("fault_type", "none")
        location_x = float(data.get("location_x", 0.0))
        location_y = float(data.get("location_y", 0.0))
        movement_duration = float(data.get("movement_duration", 3.0))

        # -------------------------
        # Motion intent (ONLY direction)
        # -------------------------
        direction = data.get("direction")

        # Convert direction → fixed velocities
        linear_x, angular_z = direction_to_velocity(direction)

        # -------------------------
        # Publish metadata topics
        # -------------------------
        send_ros_message("/robot/task_id", "std_msgs/String", {"data": task_id})
        send_ros_message("/robot/fault_type", "std_msgs/String", {"data": fault_type})
        send_ros_message(
            "/robot/target_location",
            "geometry_msgs/Point",
            {"x": location_x, "y": location_y, "z": 0.0}
        )
        send_ros_message(
            "/robot/movement_duration",
            "std_msgs/Float32",
            {"data": movement_duration}
        )

        # -------------------------
        # Start robot motion
        # -------------------------
        send_ros_message("/cmd_vel", "geometry_msgs/Twist", {
            "linear": {"x": linear_x, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": angular_z}
        })

        # Move for the requested duration
        #time.sleep(movement_duration)

        # -------------------------
        # Stop robot (CRITICAL)
        # -------------------------
        send_ros_message("/cmd_vel", "geometry_msgs/Twist", {
            "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.0}
        })

        # -------------------------
        # Simulated feedback
        # -------------------------
        robot_feedback_log.clear()
        robot_feedback_log.extend([
            "📦 Task Dispatched",
            "🤖 Robot Moving",
            "🛑 Robot Stopped",
            "🏁 Task Completed"
        ])

        return {
            "status": "sent to websocket",
            "task_id": task_id,
            "direction": direction,
            "duration": movement_duration
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}

# =========================
# Feedback endpoint
# =========================
@app.get("/api/robot/status-updates")
def get_status_updates():
    return JSONResponse(content={"updates": robot_feedback_log})
