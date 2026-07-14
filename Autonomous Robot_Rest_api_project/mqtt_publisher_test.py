
import json
import time
import paho.mqtt.publish as publish

MQTT_BROKER = "localhost"  # Replace with robot broker IP if needed
MQTT_PORT = 1883
MQTT_TOPIC = "robot/maintenance/task"

# Combined surveillance + movement + metadata
task_data = {
    "task_id": "SRV-002",
    "fault_type": "surveillance_zone_scan",  # For consistency with maintenance schema
    "location_x": 12.5,
    "location_y": 6.3,
    "linear_x": 0.3,
    "angular_z": 0.2,
    "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "duration_minutes": 20,
    "record_video": True,
    "capture_images": False,
    "return_to_base": True,
    "camera_mode": "thermal"
}

# Publish to the unified task topic
publish.single(MQTT_TOPIC, json.dumps(task_data), hostname=MQTT_BROKER, port=MQTT_PORT)
print(f"✅ Published surveillance task to topic '{MQTT_TOPIC}':\n{json.dumps(task_data, indent=2)}")
