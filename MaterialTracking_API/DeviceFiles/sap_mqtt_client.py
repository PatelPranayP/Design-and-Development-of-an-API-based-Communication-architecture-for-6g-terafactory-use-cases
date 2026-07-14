#!/usr/bin/env python3
"""
Device/Robot MQTT client for SAP Material Tracking API (request/response).

This script:
- Subscribes to RESPONSE_TOPIC
- Publishes requests to REQUEST_TOPIC
- Prints the first response it receives

Usage examples:
  python sap_mqtt_client.py --broker 127.0.0.1 --all --limit 20
  python sap_mqtt_client.py --broker 127.0.0.1 --filter MaterialNumber=4080175001 --filter Plant=1000 --limit 10
  python sap_mqtt_client.py --broker 127.0.0.1 --row-id 5

Notes:
- Filter keys must match your Excel column headers exactly (case/spaces), because the server filters by column name.
"""
import argparse
import json
import sys
import time
import uuid
import paho.mqtt.client as mqtt

DEFAULT_REQUEST_TOPIC = "sap/material/request"
DEFAULT_RESPONSE_TOPIC = "sap/material/response"

def build_payload(args) -> dict:
    if args.row_id is not None:
        return {"row_id": args.row_id}

    payload = {"limit": args.limit, "offset": args.offset}

    if args.all:
        payload["all"] = True
        return payload

    filters = {}
    for f in args.filter:
        if "=" not in f:
            print(f"[WARN] Ignoring filter '{f}' (expected Key=Value)")
            continue
        k, v = f.split("=", 1)
        filters[k] = v

    payload["filters"] = filters
    return payload

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--request-topic", default=DEFAULT_REQUEST_TOPIC)
    ap.add_argument("--response-topic", default=DEFAULT_RESPONSE_TOPIC)
    ap.add_argument("--timeout", type=int, default=10)

    ap.add_argument("--all", action="store_true", help="Request all rows (paged by limit/offset)")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--row-id", type=int, default=None)
    ap.add_argument("--filter", action="append", default=[], help="Add filter as Column=Value (repeatable)")

    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    req = build_payload(args)

    corr_id = str(uuid.uuid4())
    req["_corr_id"] = corr_id

    got_response = {"done": False, "payload": None}

    def on_connect(client, userdata, flags, rc):
        if rc != 0:
            print(f"[ERROR] MQTT connect failed rc={rc}", file=sys.stderr)
            return
        client.subscribe(args.response_topic, qos=1)
        client.publish(args.request_topic, json.dumps(req), qos=1)
        print(f"[REQ] Published to {args.request_topic}: {req}")

    def on_message(client, userdata, msg):
        try:
            raw = msg.payload.decode("utf-8", errors="ignore")
            data = json.loads(raw) if raw else {"raw": raw}
            got_response["done"] = True
            got_response["payload"] = data
            client.disconnect()
        except Exception as e:
            got_response["done"] = True
            got_response["payload"] = {"ok": False, "error": str(e)}
            client.disconnect()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(args.broker, args.port, keepalive=60)
    except Exception as e:
        print(f"[ERROR] Could not connect to broker {args.broker}:{args.port} -> {e}", file=sys.stderr)
        sys.exit(1)

    client.loop_start()

    start = time.time()
    while not got_response["done"] and (time.time() - start) < args.timeout:
        time.sleep(0.05)

    client.loop_stop()

    if not got_response["done"]:
        print(f"[ERROR] No response within {args.timeout}s on topic {args.response_topic}", file=sys.stderr)
        sys.exit(2)

    out = got_response["payload"]
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
