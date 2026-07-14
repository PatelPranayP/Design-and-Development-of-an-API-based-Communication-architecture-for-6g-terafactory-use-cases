import os
import sqlite3
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = os.getenv("SAP_DB_PATH", "sap_material.db")
TABLE_NAME = os.getenv("SAP_TABLE_NAME", "MaterialTracking")

app = FastAPI(title="SAP Material Tracking REST API (SQLite)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def table_columns():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({TABLE_NAME})")
        cols = [r["name"] for r in cur.fetchall()]
    return cols

def build_where(filters: dict, existing_cols: list[str]):
    clauses = []
    values = []
    for k, v in filters.items():
        if v is None or v == "":
            continue
        if k in existing_cols:
            clauses.append(f'"{k}" = ?')
            values.append(str(v))
    if clauses:
        return " WHERE " + " AND ".join(clauses), values
    return "", values

@app.get("/api/MaterialTracking")
def list_materials(
    MaterialNumber: str | None = Query(default=None),
    Plant: str | None = Query(default=None),
    StorageLocation: str | None = Query(default=None),
    Batch: str | None = Query(default=None),
    DeliveryNumber: str | None = Query(default=None),
    limit: int = 200,
    offset: int = 0,
):
    existing = table_columns()

    filters = {
        "MaterialNumber": MaterialNumber,
        "Plant": Plant,
        "StorageLocation": StorageLocation,
        "Batch": Batch,
        "DeliveryNumber": DeliveryNumber,
    }

    where_sql, values = build_where(filters, existing)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as c FROM {TABLE_NAME}{where_sql}", values)
        total = int(cur.fetchone()["c"])

        cur.execute(
            f"SELECT rowid as row_id, * FROM {TABLE_NAME}{where_sql} LIMIT ? OFFSET ?",
            values + [int(limit), int(offset)],
        )
        rows = [dict(r) for r in cur.fetchall()]

    return {"total": total, "limit": limit, "offset": offset, "data": rows}

@app.get("/api/MaterialTracking/{material_number}")
def get_material_by_number(material_number: str):
    existing = table_columns()

    if "MaterialNumber" not in existing:
        raise HTTPException(status_code=500, detail="Column 'MaterialNumber' not found in table")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f'SELECT rowid as row_id, * FROM {TABLE_NAME} WHERE "MaterialNumber" = ?',
            (material_number,),
        )
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Material with MaterialNumber {material_number} not found"
        )

    return {
        "material_number": material_number,
        "count": len(rows),
        "data": rows
    }