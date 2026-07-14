import json
import sqlite3
import paho.mqtt.client as mqtt

DB_PATH = "ar_workstations.db"

MQTT_BROKER = "localhost"
MQTT_PORT = 1883

REQUEST_TOPIC = "ar/workstation/request"
RESPONSE_TOPIC = "ar/workstation/response"


def split_list(value: str):
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]

def row_to_dict(row):
    return {
        "workstation_id": row[0],
        "name": row[1],
        "location": row[2],
        "status": row[3],
        "ui_mode": row[4],
        "supported_devices": split_list(row[5]),
        "required_inputs": split_list(row[6]),
    }

def fetch_all():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT workstation_id, name, location, status, ui_mode, supported_devices, required_inputs
        FROM ar_workstations
        ORDER BY workstation_id
    """)
    rows = cur.fetchall()
    con.close()
    return [row_to_dict(r) for r in rows]

def fetch_one(workstation_id: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT workstation_id, name, location, status, ui_mode, supported_devices, required_inputs
        FROM ar_workstations
        WHERE workstation_id = ?
    """, (workstation_id,))
    row = cur.fetchone()
    con.close()
    return row_to_dict(row) if row else None

def on_connect(client, userdata, flags, rc):
    print("✅ MQTT connected:", rc)
    client.subscribe(REQUEST_TOPIC)
    print(f"📡 Listening on: {REQUEST_TOPIC}")

def on_message(client, userdata, msg):
    try:
        req = json.loads(msg.payload.decode() or "{}")

        if req.get("all") is True:
            res = {"ok": True, "type": "all", "data": fetch_all()}
        else:
            ws_id = req.get("workstation_id")
            if not ws_id:
                res = {"ok": False, "error": "Send {'all': true} or {'workstation_id': '...'}"}
            else:
                one = fetch_one(ws_id)
                res = {"ok": True, "type": "one", "data": one} if one else {
                    "ok": False, "error": "Workstation not found", "workstation_id": ws_id
                }

        client.publish(RESPONSE_TOPIC, json.dumps(res), qos=1)
        print(f"📤 Published response to {RESPONSE_TOPIC}")
    except Exception as e:
        client.publish(RESPONSE_TOPIC, json.dumps({"ok": False, "error": str(e)}), qos=1)

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()

