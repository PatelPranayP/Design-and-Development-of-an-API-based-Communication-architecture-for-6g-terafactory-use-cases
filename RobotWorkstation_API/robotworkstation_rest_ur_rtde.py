import logging
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
import rtde_control
import rtde_receive

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

ROBOT_IP = "192.168.0.10"  # Change to your UR5e controller IP

# Optional motion/program parameters
USE_MOVEJ_FALLBACK = False  # True = execute a simple moveJ from Python instead of play()
TARGET_JOINTS = [0.0, -1.57, 1.57, -1.57, -1.57, 0.0]
MOVE_SPEED = 0.5
MOVE_ACCELERATION = 0.5

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
)
logger = logging.getLogger("robotworkstation-rest-api")

app = FastAPI(title="Robot Workstation REST API", version="2.0.0")

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


def trigger_robot_program():
    rtde_c = None
    rtde_r = None
    try:
        rtde_c = rtde_control.RTDEControlInterface(ROBOT_IP)
        rtde_r = rtde_receive.RTDEReceiveInterface(ROBOT_IP)

        if not rtde_r.isConnected():
            raise RuntimeError("RTDE receive interface could not connect to robot")

        if USE_MOVEJ_FALLBACK:
            success = rtde_c.moveJ(TARGET_JOINTS, MOVE_SPEED, MOVE_ACCELERATION)
            if not success:
                raise RuntimeError("moveJ command failed")
            message = "UR5e moveJ executed successfully"
        else:
            success = rtde_c.play()
            if not success:
                raise RuntimeError("Robot program could not be started with play()")
            message = "UR5e program started successfully"

        logger.info(message)
        return {
            "ok": True,
            "message": message,
            "robot_ip": ROBOT_IP,
            "mode": "moveJ" if USE_MOVEJ_FALLBACK else "play",
        }
    except Exception as exc:
        logger.exception("Robot trigger error: %s", exc)
        return {
            "ok": False,
            "error": str(exc),
            "robot_ip": ROBOT_IP,
            "mode": "moveJ" if USE_MOVEJ_FALLBACK else "play",
        }
    finally:
        if rtde_c:
            try:
                rtde_c.disconnect()
            except Exception:
                pass
        if rtde_r:
            try:
                rtde_r.disconnect()
            except Exception:
                pass


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
        result = trigger_robot_program()
        state["last_triggered_row"] = dict(row)
        state["last_trigger_result"] = result
        state["last_seen_event_datetime"] = row["event_datetime"]
        state["last_seen_row_id"] = row["row_id"]
        count += 1

    return {
        "checked": True,
        "new_rows": count,
        "message": "New rows processed.",
        "last_trigger_result": state["last_trigger_result"],
    }


def polling_loop():
    logger.info("Background polling started. Interval=%s sec", POLL_INTERVAL_SECONDS)

    while not stop_event.wait(POLL_INTERVAL_SECONDS):
        try:
            result = check_for_new_rows_once()
            if result["new_rows"] > 0:
                logger.info("Processed %s new robot trigger event(s).", result["new_rows"])
        except Exception as exc:
            logger.exception("Polling error: %s", exc)

    logger.info("Background polling stopped.")


@app.on_event("startup")
def startup_event():
    global polling_thread

    schema = validate_schema()
    if not schema["ok"]:
        raise RuntimeError(f"Missing required columns: {schema['missing']}")

    initialize_last_seen_marker()

    stop_event.clear()
    polling_thread = threading.Thread(
        target=polling_loop,
        daemon=True,
        name="robotworkstation-rest-poller"
    )
    polling_thread.start()
    logger.info("Robot Workstation REST API started.")


@app.on_event("shutdown")
def shutdown_event():
    stop_event.set()
    if polling_thread and polling_thread.is_alive():
        polling_thread.join(timeout=3)
    logger.info("Robot Workstation REST API stopped.")


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "Robot Workstation REST API",
        "db_path": DB_PATH,
        "table": TABLE_NAME,
        "date_column": DATE_COLUMN,
        "time_column": TIME_COLUMN,
        "status_column": STATUS_COLUMN,
        "trigger_status": TRIGGER_STATUS,
        "comparison_mode": "CreatedOn + CreatedTime with rowid tie-breaker",
        "robot_ip": ROBOT_IP,
        "trigger_mode": "moveJ" if USE_MOVEJ_FALLBACK else "play",
        "thread_running": polling_thread.is_alive() if polling_thread else False,
    }


@app.get("/schema-check")
def schema_check():
    return validate_schema()


@app.get("/last-trigger")
def last_trigger():
    return {
        "last_seen_event_datetime": state["last_seen_event_datetime"],
        "last_seen_row_id": state["last_seen_row_id"],
        "last_triggered_row": state["last_triggered_row"],
        "last_trigger_result": state["last_trigger_result"],
    }


@app.post("/check-now")
def check_now():
    return check_for_new_rows_once()
