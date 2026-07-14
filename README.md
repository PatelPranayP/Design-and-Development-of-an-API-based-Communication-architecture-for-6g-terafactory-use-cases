# API-Based Communication Architecture for 6G-Terafactory Use Cases

Middleware that bridges enterprise data (SAP) with robotic and operator systems in a smart factory environment, developed as part of a master's thesis at Hochschule Schmalkalden within the 6G-Terafactory project.

The system exposes four backend services, each addressing one industrial use case, over both REST (synchronous) and MQTT (publish–subscribe / request–response) interfaces:

- **AR/VR Workstation API** — serves workstation configuration data to AR devices
- **Material Tracking API** — provides SAP-derived logistics and material-movement data
- **Autonomous Robot API** — dispatches maintenance-mode commands to a ROS2 mobile robot via rosbridge
- **Robot Workstation API** — triggers UR5e pick-and-place execution via RTDE on material-arrival events

## Architecture

SAP data is exported to CSV, normalized, and stored in SQLite databases queried by the backend services. Commands reach the robots through two native interfaces: a rosbridge WebSocket bridge for the ROS2 mobile robot, and the RTDE interface (`ur_rtde`) for the UR5e workstation. The design keeps the enterprise, middleware, and robotic layers decoupled so each can be developed and extended independently.

## Tech stack

Python, FastAPI, Uvicorn, paho-mqtt, Mosquitto, SQLite, rosbridge / ROS2, ur_rtde (UR5e), React (operator dashboard). Validated over a Wi-Fi 6E network using JMeter (REST load testing), a custom MQTT concurrency tester, and iPerf3.

## Repository structure

- `/backend` — FastAPI services (REST + MQTT) for each API
- `/dashboard` — React operator dashboard
- `/robot` — rosbridge and RTDE integration scripts
- `/data` — SAP-derived CSV/SQLite datasets (sample)
- `/tests` — load-testing scripts and results

## Thesis

This repository accompanies the master's thesis *"Design and Development of an API-Based Communication Architecture for 6G-Terafactory Use Cases."*
