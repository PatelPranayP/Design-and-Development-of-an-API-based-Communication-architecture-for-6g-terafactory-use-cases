"""
MQTT API Performance Tester (Full Metrics)
==========================================
Tests end-to-end performance of MQTT request-response APIs.
Measures ALL metrics equivalent to JMeter Summary Report:
- Latency (avg, min, max, p50, p95, p99, std dev)
- Throughput (msg/sec)
- Received KB/sec
- Sent KB/sec
- Avg Response Bytes
- Error Rate

Usage:
    python mqtt_full_tester.py --api material --samples 10
    python mqtt_full_tester.py --api arvr --samples 100
    python mqtt_full_tester.py --api workstation --samples 50
    python mqtt_full_tester.py --api all --samples 10

Requirements:
    pip install paho-mqtt

IMPORTANT: Your MQTT APIs must be running before starting this test.
"""

import argparse
import json
import time
import threading
import statistics
import csv
from datetime import datetime
import paho.mqtt.client as mqtt


# =========================
# API CONFIGURATIONS
# =========================
API_CONFIGS = {
    "material": {
        "name": "Material Tracking API",
        "request_topic": "sap/material/request",
        "response_topic": "sap/material/response",
        "test_payloads": {
            "get_all": json.dumps({"all": True}),
            "get_filtered": json.dumps({"Status": "material_reached"}),
            "get_by_id": json.dumps({"row_id": 1}),
        },
    },
    "arvr": {
        "name": "AR/VR Workstation API",
        "request_topic": "ar/workstation/request",
        "response_topic": "ar/workstation/response",
        "test_payloads": {
            "get_all": json.dumps({"all": True}),
            "get_one": json.dumps({"workstation_id": "WS_AR_001"}),
        },
    },
    "workstation": {
        "name": "Robot Workstation API",
        "request_topic": "robotworkstation/request",
        "response_topic": "robotworkstation/response",
        "test_payloads": {
            "status": json.dumps({"action": "status"}),
            "check_now": json.dumps({"action": "check_now"}),
            "schema_check": json.dumps({"action": "schema_check"}),
        },
    },
}


class MQTTPerformanceTester:
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
        self.test_start_time = None
        self.test_end_time = None

        self.client = mqtt.Client(client_id=f"tester_{int(time.time())}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self.api_config["response_topic"], qos=self.qos)
            self.connected.set()
        else:
            print(f"  Connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        received_time = time.perf_counter()
        received_bytes = len(msg.payload)

        if self.current_send_time is not None:
            latency_ms = (received_time - self.current_send_time) * 1000
            self.samples.append({
                "latency_ms": round(latency_ms, 3),
                "sent_bytes": self.current_send_bytes,
                "received_bytes": received_bytes,
                "timestamp": datetime.now().isoformat(),
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

    def send_request(self, payload, timeout=10):
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
                "timestamp": datetime.now().isoformat(),
                "success": False,
            })
            return False
        return True

    def run_test(self, payload_name, payload, num_samples, delay_between=0.1):
        print(f"\n{'='*70}")
        print(f"  API:      {self.api_config['name']}")
        print(f"  Payload:  {payload_name}")
        print(f"  Samples:  {num_samples}")
        print(f"  QoS:      {self.qos}")
        print(f"  Broker:   {self.broker_host}:{self.broker_port}")
        print(f"{'='*70}")

        self.samples = []
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.test_start_time = time.perf_counter()

        for i in range(num_samples):
            success = self.send_request(payload)
            if success and len(self.samples) > 0:
                lat = self.samples[-1]["latency_ms"]
                print(f"  Sample {i+1}/{num_samples}: {lat:.1f} ms", end="\r")
            else:
                print(f"  Sample {i+1}/{num_samples}: TIMEOUT   ", end="\r")

            if i < num_samples - 1:
                time.sleep(delay_between)

        self.test_end_time = time.perf_counter()
        total_duration = self.test_end_time - self.test_start_time

        print()
        return self._calculate_stats(payload_name, num_samples, total_duration)

    def _calculate_stats(self, payload_name, num_samples, total_duration_sec):
        successful = [s for s in self.samples if s["success"]]
        failed = [s for s in self.samples if not s["success"]]

        if not successful:
            print("  No successful samples!")
            return None

        latencies = [s["latency_ms"] for s in successful]
        recv_sizes = [s["received_bytes"] for s in successful]

        sorted_lat = sorted(latencies)
        p50_idx = int(len(sorted_lat) * 0.50)
        p90_idx = int(len(sorted_lat) * 0.90)
        p95_idx = int(len(sorted_lat) * 0.95)
        p99_idx = int(len(sorted_lat) * 0.99)

        throughput = len(successful) / total_duration_sec if total_duration_sec > 0 else 0
        received_kb_sec = (self.total_bytes_received / 1024) / total_duration_sec if total_duration_sec > 0 else 0
        sent_kb_sec = (self.total_bytes_sent / 1024) / total_duration_sec if total_duration_sec > 0 else 0

        stats = {
            "api": self.api_config["name"],
            "payload": payload_name,
            "samples": num_samples,
            "successful": len(successful),
            "failed": len(failed),
            "error_rate_pct": round(len(failed) / num_samples * 100, 2),
            "avg_latency_ms": round(statistics.mean(latencies), 2),
            "min_latency_ms": round(min(latencies), 2),
            "max_latency_ms": round(max(latencies), 2),
            "p50_latency_ms": round(sorted_lat[min(p50_idx, len(sorted_lat)-1)], 2),
            "p90_latency_ms": round(sorted_lat[min(p90_idx, len(sorted_lat)-1)], 2),
            "p95_latency_ms": round(sorted_lat[min(p95_idx, len(sorted_lat)-1)], 2),
            "p99_latency_ms": round(sorted_lat[min(p99_idx, len(sorted_lat)-1)], 2),
            "std_dev_ms": round(statistics.stdev(latencies), 2) if len(latencies) > 1 else 0,
            "throughput_msg_sec": round(throughput, 2),
            "received_kb_sec": round(received_kb_sec, 2),
            "sent_kb_sec": round(sent_kb_sec, 2),
            "total_bytes_sent": self.total_bytes_sent,
            "total_bytes_received": self.total_bytes_received,
            "avg_sent_bytes": round(statistics.mean([s["sent_bytes"] for s in successful]), 0),
            "avg_received_bytes": round(statistics.mean(recv_sizes), 0),
            "test_duration_sec": round(total_duration_sec, 2),
            "qos": self.qos,
        }

        # Print JMeter-style results
        print(f"\n  {'─'*66}")
        print(f"  RESULTS")
        print(f"  {'─'*66}")
        print(f"  │ # Samples           │ {stats['samples']}")
        print(f"  │ # Successful        │ {stats['successful']}")
        print(f"  │ # Failed (Timeout)  │ {stats['failed']}")
        print(f"  │ Error %             │ {stats['error_rate_pct']}%")
        print(f"  │─────────────────────│─────────────────────────")
        print(f"  │ Average Latency     │ {stats['avg_latency_ms']} ms")
        print(f"  │ Min Latency         │ {stats['min_latency_ms']} ms")
        print(f"  │ Max Latency         │ {stats['max_latency_ms']} ms")
        print(f"  │ P50 (Median)        │ {stats['p50_latency_ms']} ms")
        print(f"  │ P90                 │ {stats['p90_latency_ms']} ms")
        print(f"  │ P95                 │ {stats['p95_latency_ms']} ms")
        print(f"  │ P99                 │ {stats['p99_latency_ms']} ms")
        print(f"  │ Std Deviation       │ {stats['std_dev_ms']} ms")
        print(f"  │─────────────────────│─────────────────────────")
        print(f"  │ Throughput          │ {stats['throughput_msg_sec']} msg/sec")
        print(f"  │ Received KB/sec     │ {stats['received_kb_sec']} KB/sec")
        print(f"  │ Sent KB/sec         │ {stats['sent_kb_sec']} KB/sec")
        print(f"  │─────────────────────│─────────────────────────")
        print(f"  │ Total Bytes Sent    │ {stats['total_bytes_sent']} bytes")
        print(f"  │ Total Bytes Recv    │ {stats['total_bytes_received']} bytes")
        print(f"  │ Avg Sent / msg      │ {stats['avg_sent_bytes']} bytes")
        print(f"  │ Avg Received / msg  │ {stats['avg_received_bytes']} bytes")
        print(f"  │─────────────────────│─────────────────────────")
        print(f"  │ Test Duration       │ {stats['test_duration_sec']} sec")
        print(f"  │ QoS Level           │ {stats['qos']}")
        print(f"  {'─'*66}")

        return stats


def save_results_csv(all_stats, filename):
    if not all_stats:
        return
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_stats[0].keys())
        writer.writeheader()
        writer.writerows(all_stats)
    print(f"\n  Results saved to: {filename}")


def print_jmeter_table(all_stats):
    print(f"\n{'='*140}")
    print(f"  JMETER-STYLE SUMMARY REPORT")
    print(f"{'='*140}")
    print(f"  {'Label':<30} {'#Samples':<9} {'Average':<9} {'Min':<9} {'Max':<9} "
          f"{'Std.Dev':<9} {'Error%':<8} {'Throughput':<13} {'Recv KB/s':<11} "
          f"{'Sent KB/s':<11} {'Avg.Bytes':<10}")
    print(f"  {'─'*135}")

    for s in all_stats:
        label = f"{s['payload']}"
        thru = f"{s['throughput_msg_sec']}/sec"
        print(f"  {label:<30} {s['samples']:<9} {s['avg_latency_ms']:<9} "
              f"{s['min_latency_ms']:<9} {s['max_latency_ms']:<9} "
              f"{s['std_dev_ms']:<9} {s['error_rate_pct']:<8} {thru:<13} "
              f"{s['received_kb_sec']:<11} {s['sent_kb_sec']:<11} "
              f"{s['avg_received_bytes']:<10}")

    # TOTAL row
    if len(all_stats) > 1:
        total_samples = sum(s["samples"] for s in all_stats)
        total_duration = max(s["test_duration_sec"] for s in all_stats)
        total_recv = sum(s["total_bytes_received"] for s in all_stats)
        total_sent = sum(s["total_bytes_sent"] for s in all_stats)
        avg_lat = round(sum(s["avg_latency_ms"]*s["samples"] for s in all_stats) / total_samples, 2)
        min_lat = min(s["min_latency_ms"] for s in all_stats)
        max_lat = max(s["max_latency_ms"] for s in all_stats)
        thru = f"{round(total_samples/total_duration, 2)}/sec" if total_duration > 0 else "0/sec"
        recv_kb = round((total_recv/1024)/total_duration, 2) if total_duration > 0 else 0
        sent_kb = round((total_sent/1024)/total_duration, 2) if total_duration > 0 else 0
        avg_bytes = round(total_recv/total_samples, 0) if total_samples > 0 else 0

        print(f"  {'─'*135}")
        print(f"  {'TOTAL':<30} {total_samples:<9} {avg_lat:<9} "
              f"{min_lat:<9} {max_lat:<9} "
              f"{'–':<9} {'–':<8} {thru:<13} "
              f"{recv_kb:<11} {sent_kb:<11} {avg_bytes:<10}")

    print(f"  {'─'*135}")


def main():
    parser = argparse.ArgumentParser(description="MQTT API Performance Tester")
    parser.add_argument("--broker", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--api", required=True, choices=["material", "arvr", "workstation", "all"])
    parser.add_argument("--samples", type=int, default=10, help="Number of samples per test")
    parser.add_argument("--qos", type=int, default=1, choices=[0, 1, 2], help="MQTT QoS level")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between samples (seconds)")
    parser.add_argument("--output", default=None, help="Output CSV filename")

    args = parser.parse_args()

    print(f"\n  MQTT API Performance Tester")
    print(f"  Broker: {args.broker}:{args.port}")
    print(f"  QoS: {args.qos}")
    print(f"  Samples: {args.samples}")

    apis_to_test = ["material", "arvr", "workstation"] if args.api == "all" else [args.api]
    all_stats = []

    for api_name in apis_to_test:
        config = API_CONFIGS[api_name]
        tester = MQTTPerformanceTester(args.broker, args.port, config, args.qos)

        try:
            tester.connect()
            for payload_name, payload in config["test_payloads"].items():
                stats = tester.run_test(payload_name, payload, args.samples, args.delay)
                if stats:
                    all_stats.append(stats)
        except ConnectionError as e:
            print(f"\n  ERROR: {e}")
        finally:
            tester.disconnect()

    if all_stats:
        output_file = args.output or f"mqtt_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_results_csv(all_stats, output_file)
        print_jmeter_table(all_stats)


if __name__ == "__main__":
    main()
