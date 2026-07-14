import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.publish as publish

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/mqtt/send-task")
async def send_task(request: Request):
    data = await request.json()

    print("📦 Incoming task:", data)

    # -------------------------
    # Task-level intent ONLY
    # -------------------------
    task_id = data.get("task_id", "unknown")
    fault_type = data.get("fault_type", "none")
    direction = data.get("direction")
    movement_duration = float(data.get("movement_duration", 3.0))

    # -------------------------
    # Publish task metadata
    # -------------------------
    publish.single("robot/task_id", task_id, hostname="localhost")
    publish.single("robot/fault_type", fault_type, hostname="localhost")

    # -------------------------
    # Publish movement intent (NO velocity)
    # -------------------------
    publish.single(
        "robot/movement/cmd_velocity",
        json.dumps({
            "direction": direction,
            "movement_duration": movement_duration
        }),
        hostname="localhost",
        qos=1
    )

    return {"status": "MQTT task published"}
