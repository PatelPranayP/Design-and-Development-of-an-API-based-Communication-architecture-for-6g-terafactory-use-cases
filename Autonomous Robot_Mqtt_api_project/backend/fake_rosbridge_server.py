import asyncio
import json
import websockets

HOST = "0.0.0.0"
PORT = 9090

async def handler(websocket):
    print("✅ Client connected")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except Exception:
                print("📩 Raw:", message)
                continue

            # Print important fields like a "fake ROS bridge"
            op = data.get("op")
            topic = data.get("topic")
            msg = data.get("msg")

            print(f"\n📨 WS Message Received:")
            print(f"  op: {op}")
            print(f"  topic: {topic}")
            print(f"  msg: {json.dumps(msg, indent=2)}")

            # Optional: send an ack (rosbridge sometimes sends back status)
            await websocket.send(json.dumps({"op": "status", "level": "info", "msg": "received"}))

    except websockets.ConnectionClosed:
        print("🔌 Client disconnected")

async def main():
    print(f"🚀 Fake rosbridge running at ws://localhost:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
