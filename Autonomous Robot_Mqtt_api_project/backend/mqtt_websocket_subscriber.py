import json
import time
import threading
import websocket
import paho.mqtt.client as mqtt

# =========================
# MQTT settings
# =========================
MQTT_BROKER = "192.168.10.1"
MQTT_PORT = 1883
MQTT_PUB_TOPICS = [
    ("robot/movement/cmd_velocity", 0),
    ("robot/task_id", 0),
    ("robot/fault_type", 0)
]

# =========================
# WebSocket (rosbridge)
# =========================
ROSBRIDGE_WS_URL = "ws://192.168.10.22:9090"

ws = websocket.WebSocket()
ws.connect(ROSBRIDGE_WS_URL)
print("✅ Connected to rosbridge_websocket")

# =========================
# MQTT client
# =========================
mqtt_client = mqtt.Client()

# =========================
# FIXED robot velocities (from supervisor)
# =========================
FIXED_LINEAR_SPEED = 0.5     # m/s
FIXED_ANGULAR_SPEED = 4.5    # rad/s

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
# Send ROS message
# =========================
def send_ros_message(topic, msg_data):
    ros_msg = {
        "op": "publish",
        "topic": topic,
        "msg": msg_data
    }
    ws.send(json.dumps(ros_msg))
    print(f"📤 Sent to {topic}: {msg_data}")

# =========================
# MQTT callbacks
# =========================
def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker with result code", rc)
    client.subscribe(MQTT_PUB_TOPICS)

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode()
        print(f"📩 Received on {topic}: {payload}")

        # -------------------------
        # Task metadata topics
        # -------------------------
        if topic == "robot/task_id":
            send_ros_message("/robot/task_id", {"data": payload})

        elif topic == "robot/fault_type":
            send_ros_message("/robot/fault_type", {"data": payload})

        # -------------------------
        # Movement command (FIXED velocity)
        # -------------------------
        elif topic == "robot/movement/cmd_velocity":
            task = json.loads(payload)

            direction = task.get("direction")
            duration = float(task.get("movement_duration", 3.0))

            # Convert direction → FIXED velocity
            linear_x, angular_z = direction_to_velocity(direction)

            # Start movement
            twist_msg = {
                "linear": {"x": linear_x, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": angular_z}
            }
            send_ros_message("/cmd_vel", twist_msg)

            # Move for specified duration
            time.sleep(duration)

            # Stop robot (CRITICAL)
            stop_msg = {
                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0}
            }
            send_ros_message("/cmd_vel", stop_msg)
            print("🛑 Robot stopped")

    except Exception as e:
        print("❌ Error in MQTT message:", e)

# =========================
# MQTT listener
# =========================
def start_mqtt_listener():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_forever()

# =========================
# ROS → MQTT feedback listener
# =========================
def start_websocket_feedback_listener():
    while True:
        try:
            raw = ws.recv()
            msg = json.loads(raw)

            if msg.get("op") == "publish" and "topic" in msg:
                topic = msg["topic"]
                data = msg.get("msg", {}).get("data", None)

                if topic == "/robot/status/reached_location":
                    mqtt_client.publish("robot/status/reached_location", data)
                    print(f"📥 ROS ➝ MQTT: reached_location = {data}")

                elif topic == "/robot/status/task_started":
                    mqtt_client.publish("robot/status/task_started", data)
                    print(f"📥 ROS ➝ MQTT: task_started = {data}")

                elif topic == "/robot/status/task_completed":
                    mqtt_client.publish("robot/status/task_completed", data)
                    print(f"📥 ROS ➝ MQTT: task_completed = {data}")

        except Exception as e:
            print("❌ WebSocket listener error:", e)
            time.sleep(2)

# =========================
# Main
# =========================
if __name__ == "__main__":
    print("📡 Starting MQTT/WebSocket bridge with feedback...")
    threading.Thread(target=start_mqtt_listener, daemon=True).start()
    start_websocket_feedback_listener()
