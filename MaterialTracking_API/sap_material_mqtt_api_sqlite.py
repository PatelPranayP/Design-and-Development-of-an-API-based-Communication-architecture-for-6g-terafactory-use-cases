import os
import json
import sqlite3
import paho.mqtt.client as mqtt

DB_PATH = os.getenv("SAP_DB_PATH", "sap_material.db")
TABLE_NAME = os.getenv("SAP_TABLE_NAME", "MaterialTracking")

MQTT_BROKER = "localhost"
MQTT_PORT = 1883

REQUEST_TOPIC = "sap/material/request"
RESPONSE_TOPIC = "sap/material/response"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({TABLE_NAME})")
    return [r["name"] for r in cur.fetchall()]


def build_where(filters: dict, existing_cols: list[str]):
    clauses = []
    values = []
    for k, v in (filters or {}).items():
        if v is None or v == "":
            continue
        if k in existing_cols:
            clauses.append(f'"{k}" = ?')
            values.append(str(v))
    if clauses:
        return " WHERE " + " AND ".join(clauses), values
    return "", values


def on_connect(client, userdata, flags, rc):
    print("MQTT connected:", rc)
    client.subscribe(REQUEST_TOPIC)
    print("Listening on:", REQUEST_TOPIC)


def on_message(client, userdata, msg):
    try:
        raw = msg.payload.decode(errors="ignore").strip()
        req = json.loads(raw) if raw else {}

        with get_conn() as conn:
            existing = table_columns(conn)
            cur = conn.cursor()

            # Special controls
            limit = req.pop("limit", None)
            offset = req.pop("offset", 0)
            if offset is None or offset == "":
                offset = 0
            offset = int(offset)

            if "row_id" in req:
                row_id = int(req["row_id"])
                cur.execute(
                    f"SELECT rowid as row_id, * FROM {TABLE_NAME} WHERE rowid = ?",
                    (row_id,)
                )
                one = cur.fetchone()
                if not one:
                    res = {"ok": False, "error": "row_id not found", "row_id": row_id}
                else:
                    res = {"ok": True, "type": "one", "data": dict(one)}
                client.publish(RESPONSE_TOPIC, json.dumps(res), qos=1)
                return

            if req.get("all") is True:
                where_sql, values = "", []
            else:
                req.pop("all", None)
                filters = req
                where_sql, values = build_where(filters, existing)

            cur.execute(f"SELECT COUNT(*) as c FROM {TABLE_NAME}{where_sql}", values)
            total = int(cur.fetchone()["c"])

            query = f"SELECT rowid as row_id, * FROM {TABLE_NAME}{where_sql}"
            query_values = values.copy()

            if limit is not None and str(limit) != "":
                query += " LIMIT ? OFFSET ?"
                query_values += [int(limit), offset]

            cur.execute(query, query_values)
            rows = [dict(r) for r in cur.fetchall()]

        res = {
            "ok": True,
            "type": "list",
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": rows,
            "source": DB_PATH,
        }
        client.publish(RESPONSE_TOPIC, json.dumps(res), qos=1)

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
