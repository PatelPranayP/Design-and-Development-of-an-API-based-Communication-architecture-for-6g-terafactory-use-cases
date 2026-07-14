import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any

import paho.mqtt.client as mqtt

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

# MQTT broker should be reachable by Laptop 2
# If broker runs on Laptop 1, keep localhost here for Laptop 1.
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# Laptop 1 publishes robot command here.
ROBOT_COMMAND_TOPIC = "robotworkstation/request"

# Optional response/status topic from Laptop 1 API.
API_RESPONSE_TOPIC = "robotworkstation/response"

# Command sent to Laptop 2 robot receiver.
ROBOT_COMMAND_PAYLOAD = {
    "action": "start_robot",
    "source": "robotworkstation_mqtt_publisher",
    "reason": "material_reached",
}

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
)
logger = logging.getLogger("robotworkstation-mqtt-publisher")

stop_event = threading.Event()
polling_thread: threading.Thread | None = None
mqtt_client: mqtt.Client | None = None

state = {
    # TEST MODE: this signature changes when you edit CreatedOn/CreatedTime/status of the latest row.
    "last_seen_signature": None,
    "last_seen_event_datetime": None,
    "last_seen_row_id": None,
    "last_published_row": None,
    "last_publish_result": None,
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
    # Converts DD.MM.YYYY + HH:MM:SS to SQLite datetime YYYY-MM-DD HH:MM:SS
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


def publish_robot_command(row: sqlite3.Row) -> dict[str, Any]:
    if mqtt_client is None:
        raise RuntimeError("MQTT client is not initialized")

    payload = dict(ROBOT_COMMAND_PAYLOAD)
    payload.update({
        "material_event": {
            "row_id": row["row_id"],
            "event_datetime": row["event_datetime"],
            "status": row[STATUS_COLUMN],
        }
    })

    result = mqtt_client.publish(
        ROBOT_COMMAND_TOPIC,
        json.dumps(payload),
        qos=1,
    )
    result.wait_for_publish(timeout=5)

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"MQTT publish failed with rc={result.rc}")

    logger.info("Published robot command to %s: %s", ROBOT_COMMAND_TOPIC, payload)
    return {
        "ok": True,
        "topic": ROBOT_COMMAND_TOPIC,
        "payload": payload,
    }


def row_signature(row: sqlite3.Row | None) -> str | None:
    """
    TEST MODE signature.
    If you edit CreatedOn or CreatedTime of the latest material_reached row,
    this value changes and a new MQTT command is published.
    """
    if row is None:
        return None
    return f'{row["row_id"]}|{row["event_datetime"]}|{row[STATUS_COLUMN]}'


def initialize_last_seen_marker():
    latest = get_latest_material_reached_row()
    sig = row_signature(latest)

    if latest:
        state["last_seen_signature"] = sig
        state["last_seen_event_datetime"] = latest["event_datetime"]
        state["last_seen_row_id"] = latest["row_id"]
        logger.info(
            "Initialized TEST baseline: signature=%s event_datetime=%s row_id=%s",
            sig,
            state["last_seen_event_datetime"],
            state["last_seen_row_id"],
        )
    else:
        state["last_seen_signature"] = None
        state["last_seen_event_datetime"] = None
        state["last_seen_row_id"] = None
        logger.info("No material_reached rows found during startup.")


def check_for_new_rows_once():
    """
    TEST MODE:
    Publishes when the latest material_reached row changes.
    This allows testing by editing CreatedTime instead of inserting a new row.
    """
    latest = get_latest_material_reached_row()
    current_sig = row_signature(latest)

    if latest is None:
        return {
            "checked": True,
            "new_rows": 0,
            "message": "No material_reached row found.",
        }

    if state["last_seen_signature"] is None:
        state["last_seen_signature"] = current_sig
        state["last_seen_event_datetime"] = latest["event_datetime"]
        state["last_seen_row_id"] = latest["row_id"]
        return {
            "checked": True,
            "new_rows": 0,
            "message": "Initialized baseline marker.",
        }

    if current_sig == state["last_seen_signature"]:
        return {
            "checked": True,
            "new_rows": 0,
            "message": "Latest material_reached row has not changed.",
        }

    try:
        publish_result = publish_robot_command(latest)
    except Exception as exc:
        logger.exception("Publish error: %s", exc)
        publish_result = {"ok": False, "error": str(exc)}

    state["last_seen_signature"] = current_sig
    state["last_seen_event_datetime"] = latest["event_datetime"]
    state["last_seen_row_id"] = latest["row_id"]
    state["last_published_row"] = dict(latest)
    state["last_publish_result"] = publish_result

    return {
        "checked": True,
        "new_rows": 1,
        "message": "Latest material_reached row changed; MQTT command published.",
        "last_publish_result": publish_result,
    }

def polling_loop():
    logger.info("Background polling started. Interval=%s sec", POLL_INTERVAL_SECONDS)

    while not stop_event.wait(POLL_INTERVAL_SECONDS):
        result = check_for_new_rows_once()
        if result["new_rows"] > 0:
            logger.info("Published %s new robot command event(s).", result["new_rows"])

    logger.info("Background polling stopped.")


def build_status_response():
    return {
        "ok": True,
        "service": "Robot Workstation MQTT Publisher API TEST MODE",
        "test_mode": "Triggers when latest material_reached row timestamp changes",
        "db_path": DB_PATH,
        "table": TABLE_NAME,
        "status_column": STATUS_COLUMN,
        "trigger_status": TRIGGER_STATUS,
        "last_seen_signature": state["last_seen_signature"],
        "last_seen_event_datetime": state["last_seen_event_datetime"],
        "last_seen_row_id": state["last_seen_row_id"],
        "last_published_row": state["last_published_row"],
        "last_publish_result": state["last_publish_result"],
        "robot_command_topic": ROBOT_COMMAND_TOPIC,
        "mqtt_broker": MQTT_BROKER,
    }


def on_connect(client, userdata, flags, rc):
    print("MQTT connected:", rc)
    client.publish(API_RESPONSE_TOPIC, json.dumps(build_status_response()), qos=1)


def start_background_polling():
    global polling_thread
    stop_event.clear()
    polling_thread = threading.Thread(
        target=polling_loop,
        daemon=True,
        name="robotworkstation-mqtt-publisher-poller",
    )
    polling_thread.start()


def main():
    global mqtt_client

    schema = validate_schema()
    if not schema["ok"]:
        raise RuntimeError(f"Missing required columns: {schema['missing']}")

    initialize_last_seen_marker()

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

    start_background_polling()

    print("Robot Workstation MQTT Publisher TEST MODE running.")
    print("Publishing robot commands to:", ROBOT_COMMAND_TOPIC)
    print("Press Ctrl+C to stop.")

    try:
        while True:
            stop_event.wait(1)
    except KeyboardInterrupt:
        logger.info("Stopping service...")
    finally:
        stop_event.set()
        if polling_thread and polling_thread.is_alive():
            polling_thread.join(timeout=3)
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()
