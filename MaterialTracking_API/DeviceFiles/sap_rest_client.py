#!/usr/bin/env python3
"""
Device/Robot REST client for SAP Material Tracking API.

Usage examples:
  python sap_rest_client.py --base-url http://localhost:8005 --limit 20
  python sap_rest_client.py --base-url http://localhost:8005 --filter MaterialNumber=4080175001 --filter Plant=1000 --limit 10
  python sap_rest_client.py --base-url http://localhost:8005 --row-id 5

Notes:
- Filter keys must match the REST API query params implemented in sap_material_rest_api.py:
  MaterialNumber, Plant, StorageLocation, Batch, DeliveryNumber
"""
import argparse
import json
import sys
from urllib.parse import urlencode
import urllib.request

def http_get(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", errors="ignore")
        return json.loads(data)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8005", help="REST base URL, e.g., http://localhost:8005")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--row-id", type=int, default=None, help="Fetch a single record by row_id")
    ap.add_argument("--filter", action="append", default=[], help="Add filter as Key=Value (repeatable)")
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    base_url = args.base_url.rstrip("/")

    try:
        if args.row_id is not None:
            url = f"{base_url}/api/materials/{args.row_id}"
            out = http_get(url, timeout=args.timeout)
        else:
            params = {"limit": args.limit, "offset": args.offset}
            for f in args.filter:
                if "=" not in f:
                    print(f"[WARN] Ignoring filter '{f}' (expected Key=Value)")
                    continue
                k, v = f.split("=", 1)
                params[k] = v
            url = f"{base_url}/api/materials?{urlencode(params)}"
            out = http_get(url, timeout=args.timeout)

        if args.pretty:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(out, ensure_ascii=False))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
