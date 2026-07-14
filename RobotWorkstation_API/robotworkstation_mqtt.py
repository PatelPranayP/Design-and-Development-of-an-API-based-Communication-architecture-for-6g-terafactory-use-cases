import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any

import paho.mqtt.client as mqtt
from websocket import create_connection

# =========================
# CONFIG
# =========================
DB_PATH = "sap_material.db"
TABLE_NAME = "MaterialTracking"

STATUS_COLUMN = "Status"
DATE_COLUMN = "CreatedOn"
TIME_COLUMN = "CreatedTime"

TRIGGER_STATUS = "material_reached"
POLL_INTERVAL_SECONDS = 5

ROSBRIDGE_URL = "ws://localhost:9090"
ROS_TOPIC = "/material_status"
ROS_TRIGGER_MESSAGE = "material_reached"

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
REQUEST_TOPIC = "robotworkstation/request"
RESPONSE_TOPIC = "robotworkstation/response"

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
)
logger = logging.getLogger("robotworkstation-mqtt-api")

stop_event = threading.Event()
polling_thread: threading.Thread | None = None

state = {
    "last_seen_event_datetime": None,
    "last_seen_row_id": None,
    "last_triggered_row": None,
    "last_trigger_result": None,
}


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def validate_schema() -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({TABLE_NAME})")
        cols = [r["name"] for r in cur.fetchall()]

    required = [STATUS_COLUMN, DATE_COLUMN, TIME_COLUMN]
    missing = [c for c in required if c not in cols]

    return {
        "ok": len(missing) == 0,
        "table": TABLE_NAME,
        "columns": cols,
        "missing": missing,
    }


def combined_datetime_expr() -> str:
    return (
        f'datetime('
        f'substr("{DATE_COLUMN}", 7, 4) || "-" || '
        f'substr("{DATE_COLUMN}", 4, 2) || "-" || '
        f'substr("{DATE_COLUMN}", 1, 2) || " " || '
        f'"{TIME_COLUMN}"'
        f')'
    )


def get_latest_material_reached_row():
    dt_expr = combined_datetime_expr()
    sql = f"""
        SELECT rowid AS row_id, *,
               {dt_expr} AS event_datetime
        FROM {TABLE_NAME}
        WHERE "{STATUS_COLUMN}" = ?
        ORDER BY event_datetime DESC, rowid DESC
        LIMIT 1
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, (TRIGGER_STATUS,))
        return cur.fetchone()


def get_new_material_reached_rows(last_seen_event_datetime: str | None, last_seen_row_id: int | None):
    if last_seen_event_datetime is None:
        return []

    dt_expr = combined_datetime_expr()
    sql = f"""
        SELECT rowid AS row_id, *,
               {dt_expr} AS event_datetime
        FROM {TABLE_NAME}
        WHERE "{STATUS_COLUMN}" = ?
          AND (
                event_datetime > ?
                OR (event_datetime = ? AND rowid > ?)
              )
        ORDER BY event_datetime ASC, rowid ASC
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            sql,
            (
                TRIGGER_STATUS,
                last_seen_event_datetime,
                last_seen_event_datetime,
                int(last_seen_row_id or 0),
            ),
        )
        return cur.fetchall()


def publish_material_reached_to_ros2():
    payload = {
        "op": "publish",
        "topic": ROS_TOPIC,
        "msg": {
            "data": ROS_TRIGGER_MESSAGE
        },
    }

    ws = None
    try:
        ws = create_connection(ROSBRIDGE_URL, timeout=5)
        ws.send(json.dumps(payload))
        logger.info("Published to ROS 2: %s", ROS_TRIGGER_MESSAGE)
        return {"ok": True, "message": ROS_TRIGGER_MESSAGE}
    finally:
        if ws:
            ws.close()


def initialize_last_seen_marker():
    latest = get_latest_material_reached_row()
    if latest:
        state["last_seen_event_datetime"] = latest["event_datetime"]
        state["last_seen_row_id"] = latest["row_id"]
        logger.info(
            "Initialized baseline: event_datetime=%s row_id=%s",
            state["last_seen_event_datetime"],
            state["last_seen_row_id"],
        )
    else:
        state["last_seen_event_datetime"] = None
        state["last_seen_row_id"] = None
        logger.info("No historical material_reached rows found during startup.")


def check_for_new_rows_once():
    last_seen_event_datetime = state["last_seen_event_datetime"]
    last_seen_row_id = state["last_seen_row_id"]

    if last_seen_event_datetime is None:
        latest = get_latest_material_reached_row()
        if latest:
            state["last_seen_event_datetime"] = latest["event_datetime"]
            state["last_seen_row_id"] = latest["row_id"]
        return {
            "checked": True,
            "new_rows": 0,
            "message": "No baseline marker existed; initialized if possible.",
        }

    rows = get_new_material_reached_rows(last_seen_event_datetime, last_seen_row_id)

    if not rows:
        return {
            "checked": True,
            "new_rows": 0,
            "message": "No new material_reached rows."
        }

    count = 0
    for row in rows:
        result = publish_material_reached_to_ros2()
        state["last_triggered_row"] = dict(row)
        state["last_trigger_result"] = result
        state["last_seen_event_datetime"] = row["event_datetime"]
        state["last_seen_row_id"] = row["row_id"]
        count += 1

    return {
        "checked": True,
        "new_rows": count,
        "message": "New rows triggered successfully."
    }


def polling_loop():
    logger.info("Background polling started. Interval=%s sec", POLL_INTERVAL_SECONDS)

    while not stop_event.wait(POLL_INTERVAL_SECONDS):
        try:
            result = check_for_new_rows_once()
            if result["new_rows"] > 0:
                logger.info("Triggered %s new ROS 2 event(s).", result["new_rows"])
        except Exception as exc:
            logger.exception("Polling error: %s", exc)

    logger.info("Background polling stopped.")


def build_status_response():
    return {
        "ok": True,
        "service": "Robot Workstation MQTT API",
        "db_path": DB_PATH,
        "table": TABLE_NAME,
        "date_column": DATE_COLUMN,
        "time_column": TIME_COLUMN,
        "status_column": STATUS_COLUMN,
        "comparison_mode": "CreatedOn + CreatedTime with rowid tie-breaker",
        "last_seen_event_datetime": state["last_seen_event_datetime"],
        "last_seen_row_id": state["last_seen_row_id"],
        "last_triggered_row": state["last_triggered_row"],
        "last_trigger_result": state["last_trigger_result"],
    }


def on_connect(client, userdata, flags, rc):
    print("MQTT connected:", rc)
    client.subscribe(REQUEST_TOPIC)
    print("Listening on:", REQUEST_TOPIC)


def on_message(client, userdata, msg):
    try:
        raw = msg.payload.decode(errors="ignore").strip()
        req = json.loads(raw) if raw else {}

        action = req.get("action", "status")

        if action == "status":
            res = build_status_response()
        elif action == "check_now":
            res = check_for_new_rows_once()
        elif action == "schema_check":
            res = validate_schema()
        else:
            res = {"ok": False, "error": f"Unknown action: {action}"}

        client.publish(RESPONSE_TOPIC, json.dumps(res), qos=1)

    except Exception as exc:
        client.publish(RESPONSE_TOPIC, json.dumps({"ok": False, "error": str(exc)}), qos=1)


def start_background_polling():
    global polling_thread
    stop_event.clear()
    polling_thread = threading.Thread(
        target=polling_loop,
        daemon=True,
        name="robotworkstation-mqtt-poller"
    )
    polling_thread.start()


def main():
    schema = validate_schema()
    if not schema["ok"]:
        raise RuntimeError(f"Missing required columns: {schema['missing']}")

    initialize_last_seen_marker()
    start_background_polling()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
