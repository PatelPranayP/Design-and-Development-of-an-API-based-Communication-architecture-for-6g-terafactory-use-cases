import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = "ar_workstations.db"

app = FastAPI(title="AR Workstation REST API (SQLite Source)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def split_list(value: str):
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]

def row_to_dict(row):
    return {
        "workstation_id": row[0],
        "name": row[1],
        "location": row[2],
        "status": row[3],
        "ui_mode": row[4],
        "supported_devices": split_list(row[5]),
        "required_inputs": split_list(row[6]),
    }

def fetch_all():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT workstation_id, name, location, status, ui_mode, supported_devices, required_inputs
        FROM ar_workstations
        ORDER BY workstation_id
    """)
    rows = cur.fetchall()
    con.close()
    return [row_to_dict(r) for r in rows]

def fetch_one(workstation_id: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT workstation_id, name, location, status, ui_mode, supported_devices, required_inputs
        FROM ar_workstations
        WHERE workstation_id = ?
    """, (workstation_id,))
    row = cur.fetchone()
    con.close()
    return row_to_dict(row) if row else None

@app.get("/api/ar/workstations")
def list_workstations():
    return {"workstations": fetch_all()}

@app.get("/api/ar/workstations/{workstation_id}")
def get_workstation(workstation_id: str):
    data = fetch_one(workstation_id)
    if not data:
        raise HTTPException(status_code=404, detail="Workstation not found")
    return data