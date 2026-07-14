# fake_ws_server.py

import asyncio
import websockets

async def echo(websocket):
    print("🌐 WebSocket client connected")
    try:
        async for message in websocket:
            print(f"📨 Message from subscriber: {message}")
            await websocket.send("✅ ACK: " + message)
    except websockets.ConnectionClosed:
        print("❌ WebSocket connection closed")

async def main():
    async with websockets.serve(echo, "0.0.0.0", 9090):
        print("🚀 Fake WebSocket server started at ws://0.0.0.0:9090")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
