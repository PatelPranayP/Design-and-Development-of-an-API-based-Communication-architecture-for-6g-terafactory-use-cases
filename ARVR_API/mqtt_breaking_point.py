"""
MQTT API Breaking Point Finder
===============================
Gradually increases load until the API breaks or latency exceeds threshold.

What it does:
1. Starts with low load (fast delay between messages)
2. Gradually reduces delay (increases speed)
3. Finds the point where:
   - Latency exceeds your threshold (e.g., 100ms)
   - Error rate exceeds 5%
   - Messages start timing out

Usage:
    python mqtt_breaking_point.py --broker localhost --api arvr
    python mqtt_breaking_point.py --broker localhost --api material --threshold 100
    python mqtt_breaking_point.py --broker localhost --api workstation --threshold 10
    python mqtt_breaking_point.py --broker localhost --api all

Requirements:
    pip install paho-mqtt
"""

import argparse
import json
import time
import threading
import statistics
import csv
from datetime import datetime
import paho.mqtt.client as mqtt


API_CONFIGS = {
    "material": {
        "name": "Material Tracking API",
        "request_topic": "sap/material/request",
        "response_topic": "sap/material/response",
        "payload": json.dumps({"all": True}),
    },
    "arvr": {
        "name": "AR/VR Workstation API",
        "request_topic": "ar/workstation/request",
        "response_topic": "ar/workstation/response",
        "payload": json.dumps({"all": True}),
    },
    "workstation": {
        "name": "Robot Workstation API",
        "request_topic": "robotworkstation/request",
        "response_topic": "robotworkstation/response",
        "payload": json.dumps({"action": "status"}),
    },
}

# Stress levels: delay between messages (seconds)
# Goes from slow (easy) to fast (hard)
STRESS_LEVELS = [
    {"name": "Level 1  (very slow)",  "delay": 1.0,    "samples": 20},
    {"name": "Level 2  (slow)",       "delay": 0.5,    "samples": 30},
    {"name": "Level 3  (moderate)",   "delay": 0.2,    "samples": 50},
    {"name": "Level 4  (fast)",       "delay": 0.1,    "samples": 50},
    {"name": "Level 5  (very fast)",  "delay": 0.05,   "samples": 100},
    {"name": "Level 6  (extreme)",    "delay": 0.02,   "samples": 100},
    {"name": "Level 7  (brutal)",     "delay": 0.01,   "samples": 150},
    {"name": "Level 8  (insane)",     "delay": 0.005,  "samples": 200},
    {"name": "Level 9  (maximum)",    "delay": 0.002,  "samples": 200},
    {"name": "Level 10 (no delay)",   "delay": 0.0,    "samples": 300},
]


class BreakingPointTester:
    def __init__(self, broker_host, broker_port, api_config, qos=1):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.api_config = api_config
        self.qos = qos

        self.samples = []
        self.current_send_time = None
        self.current_send_bytes = 0
        self.response_received = threading.Event()
        self.connected = threading.Event()
        self.total_bytes_sent = 0
        self.total_bytes_received = 0

        self.client = mqtt.Client(client_id=f"stress_{int(time.time())}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self.api_config["response_topic"], qos=self.qos)
            self.connected.set()

    def _on_message(self, client, userdata, msg):
        received_time = time.perf_counter()
        received_bytes = len(msg.payload)

        if self.current_send_time is not None:
            latency_ms = (received_time - self.current_send_time) * 1000
            self.samples.append({
                "latency_ms": round(latency_ms, 3),
                "sent_bytes": self.current_send_bytes,
                "received_bytes": received_bytes,
                "success": True,
            })
            self.total_bytes_received += received_bytes

        self.response_received.set()

    def connect(self):
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        if not self.connected.wait(timeout=10):
            raise ConnectionError("Could not connect to MQTT broker")
        time.sleep(0.5)

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def send_request(self, payload, timeout=5):
        self.response_received.clear()
        payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
        self.current_send_bytes = len(payload_bytes)
        self.total_bytes_sent += self.current_send_bytes
        self.current_send_time = time.perf_counter()

        self.client.publish(
            self.api_config["request_topic"],
            payload_bytes,
            qos=self.qos,
        )

        if not self.response_received.wait(timeout=timeout):
            self.samples.append({
                "latency_ms": -1,
                "sent_bytes": self.current_send_bytes,
                "received_bytes": 0,
                "success": False,
            })
            return False
        return True

    def run_stress_level(self, level_config, payload):
        self.samples = []
        self.total_bytes_sent = 0
        self.total_bytes_received = 0

        delay = level_config["delay"]
        num_samples = level_config["samples"]

        start_time = time.perf_counter()

        for i in range(num_samples):
            self.send_request(payload, timeout=5)
            if delay > 0:
                time.sleep(delay)

        end_time = time.perf_counter()
        duration = end_time - start_time

        # Calculate stats
        successful = [s for s in self.samples if s["success"]]
        failed = [s for s in self.samples if not s["success"]]

        if not successful:
            return {
                "level": level_config["name"],
                "delay_sec": delay,
                "samples": num_samples,
                "successful": 0,
                "failed": num_samples,
                "error_rate_pct": 100.0,
                "avg_latency_ms": -1,
                "min_latency_ms": -1,
                "max_latency_ms": -1,
                "p50_latency_ms": -1,
                "p95_latency_ms": -1,
                "p99_latency_ms": -1,
                "std_dev_ms": -1,
                "throughput_msg_sec": 0,
                "received_kb_sec": 0,
                "sent_kb_sec": 0,
                "avg_received_bytes": 0,
                "duration_sec": round(duration, 2),
                "effective_rate_msg_sec": round(num_samples / duration, 2) if duration > 0 else 0,
                "broken": True,
            }

        latencies = [s["latency_ms"] for s in successful]
        sorted_lat = sorted(latencies)
        p50_idx = int(len(sorted_lat) * 0.50)
        p95_idx = int(len(sorted_lat) * 0.95)
        p99_idx = int(len(sorted_lat) * 0.99)

        throughput = len(successful) / duration if duration > 0 else 0
        recv_kb = (self.total_bytes_received / 1024) / duration if duration > 0 else 0
        sent_kb = (self.total_bytes_sent / 1024) / duration if duration > 0 else 0
        error_rate = len(failed) / num_samples * 100

        return {
            "level": level_config["name"],
            "delay_sec": delay,
            "samples": num_samples,
            "successful": len(successful),
            "failed": len(failed),
            "error_rate_pct": round(error_rate, 2),
            "avg_latency_ms": round(statistics.mean(latencies), 2),
            "min_latency_ms": round(min(latencies), 2),
            "max_latency_ms": round(max(latencies), 2),
            "p50_latency_ms": round(sorted_lat[min(p50_idx, len(sorted_lat)-1)], 2),
            "p95_latency_ms": round(sorted_lat[min(p95_idx, len(sorted_lat)-1)], 2),
            "p99_latency_ms": round(sorted_lat[min(p99_idx, len(sorted_lat)-1)], 2),
            "std_dev_ms": round(statistics.stdev(latencies), 2) if len(latencies) > 1 else 0,
            "throughput_msg_sec": round(throughput, 2),
            "received_kb_sec": round(recv_kb, 2),
            "sent_kb_sec": round(sent_kb, 2),
            "avg_received_bytes": round(statistics.mean([s["received_bytes"] for s in successful]), 0),
            "duration_sec": round(duration, 2),
            "effective_rate_msg_sec": round(num_samples / duration, 2) if duration > 0 else 0,
            "broken": False,
        }


def run_breaking_point_test(broker_host, broker_port, api_name, latency_threshold, qos):
    config = API_CONFIGS[api_name]
    payload = config["payload"]

    print(f"\n{'='*80}")
    print(f"  BREAKING POINT TEST")
    print(f"  API:              {config['name']}")
    print(f"  Broker:           {broker_host}:{broker_port}")
    print(f"  QoS:              {qos}")
    print(f"  Latency Threshold:{latency_threshold} ms")
    print(f"  Levels:           {len(STRESS_LEVELS)}")
    print(f"{'='*80}")

    tester = BreakingPointTester(broker_host, broker_port, config, qos)
    tester.connect()

    all_results = []
    breaking_point = None

    print(f"\n  {'Level':<25} {'Delay':<8} {'Samples':<8} {'Avg(ms)':<9} "
          f"{'P95(ms)':<9} {'Max(ms)':<9} {'Errors':<8} {'Thru(msg/s)':<12} {'Status':<10}")
    print(f"  {'─'*98}")

    for level in STRESS_LEVELS:
        # Small pause between levels to let the system settle
        time.sleep(1)

        result = tester.run_stress_level(level, payload)
        all_results.append(result)

        # Determine status
        if result["broken"]:
            status = "BROKEN"
        elif result["error_rate_pct"] > 5:
            status = "FAILING"
        elif result["avg_latency_ms"] > latency_threshold:
            status = "EXCEEDED"
        elif result["p95_latency_ms"] > latency_threshold:
            status = "P95 HIGH"
        else:
            status = "OK"

        # Status symbol
        if status == "OK":
            symbol = "[  OK  ]"
        elif status == "P95 HIGH":
            symbol = "[ WARN ]"
        elif status == "EXCEEDED":
            symbol = "[ HIGH ]"
        elif status == "FAILING":
            symbol = "[ FAIL ]"
        else:
            symbol = "[BROKEN]"

        avg_display = f"{result['avg_latency_ms']}" if result['avg_latency_ms'] >= 0 else "N/A"
        p95_display = f"{result['p95_latency_ms']}" if result['p95_latency_ms'] >= 0 else "N/A"
        max_display = f"{result['max_latency_ms']}" if result['max_latency_ms'] >= 0 else "N/A"

        print(f"  {level['name']:<25} {level['delay']:<8} {level['samples']:<8} "
              f"{avg_display:<9} {p95_display:<9} {max_display:<9} "
              f"{result['error_rate_pct']:<8} {result['throughput_msg_sec']:<12} {symbol:<10}")

        # Check if we found the breaking point
        if breaking_point is None and status in ["EXCEEDED", "FAILING", "BROKEN"]:
            breaking_point = result

        # Stop if completely broken
        if result["broken"] or result["error_rate_pct"] > 50:
            print(f"\n  Stopping — API is completely broken at this level.")
            break

    tester.disconnect()

    # Print breaking point analysis
    print(f"\n{'='*80}")
    print(f"  BREAKING POINT ANALYSIS")
    print(f"{'='*80}")

    if breaking_point:
        print(f"  Breaking Point Found:     {breaking_point['level']}")
        print(f"  Delay at Break:           {breaking_point['delay_sec']} sec")
        print(f"  Effective Rate at Break:  {breaking_point['effective_rate_msg_sec']} msg/sec")
        print(f"  Avg Latency at Break:     {breaking_point['avg_latency_ms']} ms")
        print(f"  P95 Latency at Break:     {breaking_point['p95_latency_ms']} ms")
        print(f"  Error Rate at Break:      {breaking_point['error_rate_pct']}%")
        print(f"  Latency Threshold:        {latency_threshold} ms")
    else:
        print(f"  NO BREAKING POINT FOUND!")
        print(f"  Your API survived all {len(STRESS_LEVELS)} stress levels.")
        print(f"  Maximum throughput achieved: {max(r['throughput_msg_sec'] for r in all_results)} msg/sec")
        print(f"  Maximum latency seen: {max(r['max_latency_ms'] for r in all_results if r['max_latency_ms'] > 0)} ms")

    # Find the last OK level (safe operating point)
    last_ok = None
    for r in all_results:
        if r["avg_latency_ms"] > 0 and r["avg_latency_ms"] <= latency_threshold and r["error_rate_pct"] <= 5:
            last_ok = r

    if last_ok:
        print(f"\n  SAFE OPERATING POINT:")
        print(f"  Level:                    {last_ok['level']}")
        print(f"  Max Safe Throughput:      {last_ok['throughput_msg_sec']} msg/sec")
        print(f"  Avg Latency at Safe:      {last_ok['avg_latency_ms']} ms")
        print(f"  P95 Latency at Safe:      {last_ok['p95_latency_ms']} ms")

    # Thesis recommendation
    print(f"\n  FOR YOUR THESIS:")
    if breaking_point:
        print(f"  \"The {config['name']} achieves stable operation at up to")
        print(f"   {last_ok['throughput_msg_sec'] if last_ok else 'N/A'} msg/sec with average latency of")
        print(f"   {last_ok['avg_latency_ms'] if last_ok else 'N/A'} ms. Beyond {breaking_point['effective_rate_msg_sec']} msg/sec,")
        print(f"   latency exceeds the {latency_threshold} ms threshold, indicating the")
        print(f"   need for 6G network optimization.\"")
    else:
        max_thru = max(r['throughput_msg_sec'] for r in all_results)
        max_lat = max(r['avg_latency_ms'] for r in all_results if r['avg_latency_ms'] > 0)
        print(f"  \"The {config['name']} sustained all stress levels up to")
        print(f"   {max_thru} msg/sec with maximum average latency of")
        print(f"   {max_lat} ms, remaining within the {latency_threshold} ms threshold.\"")

    print(f"{'='*80}")

    return all_results


def save_all_results(all_results, api_name, filename):
    if not all_results:
        return
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\n  Results saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(description="MQTT API Breaking Point Finder")
    parser.add_argument("--broker", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--api", required=True, choices=["material", "arvr", "workstation", "all"])
    parser.add_argument("--qos", type=int, default=1, choices=[0, 1, 2], help="MQTT QoS level")
    parser.add_argument("--threshold", type=int, default=100,
                        help="Latency threshold in ms (default: 100). API 'breaks' when avg latency exceeds this.")
    parser.add_argument("--output", default=None, help="Output CSV filename")

    args = parser.parse_args()

    apis_to_test = ["material", "arvr", "workstation"] if args.api == "all" else [args.api]

    for api_name in apis_to_test:
        results = run_breaking_point_test(
            args.broker, args.port, api_name, args.threshold, args.qos
        )

        output_file = args.output or f"breaking_point_{api_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_all_results(results, api_name, output_file)


if __name__ == "__main__":
    main()
