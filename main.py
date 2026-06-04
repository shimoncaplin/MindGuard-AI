
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import sqlite3

app = FastAPI()
DB_FILE = "mindguard.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'UNKNOWN'
        )
    """)
    conn.commit()
    conn.close()

def quality_score(prompt, response):
    response = response.strip()
    if len(response) < 10:
        return 20, "BAD"
    if len(response) < 40:
        return 55, "WEAK"
    return 85, "GOOD"

init_db()

class Observation(BaseModel):
    prompt: str
    response: str

@app.get("/")
def home():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM observations")
    count = cursor.fetchone()[0]
    conn.close()
    return {"status": "MindGuard AI Running", "observations": count}

@app.post("/observe")
def observe(data: Observation):
    timestamp = datetime.now().isoformat()
    score, status = quality_score(data.prompt, data.response)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO observations (timestamp, prompt, response, score, status) VALUES (?, ?, ?, ?, ?)",
        (timestamp, data.prompt, data.response, score, status)
    )
    conn.commit()
    entry_id = cursor.lastrowid
    conn.close()

    return {
        "success": True,
        "entry": {
            "id": entry_id,
            "timestamp": timestamp,
            "prompt": data.prompt,
            "response": data.response,
            "score": score,
            "status": status
        }
    }

@app.get("/observations")
def observations():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id,timestamp,prompt,response,score,status FROM observations ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "prompt": r[2],
            "response": r[3],
            "score": r[4],
            "status": r[5]
        }
        for r in rows
    ]

@app.get("/stats")
def stats():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM observations")
    count = cursor.fetchone()[0]
    cursor.execute("SELECT AVG(score) FROM observations")
    avg = cursor.fetchone()[0]
    conn.close()
    return {"total_observations": count, "average_score": round(avg, 2) if avg else 0}

@app.delete("/observations")
def delete_observations():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM observations")
    conn.commit()
    conn.close()
    return {"success": True, "message": "All observations deleted"}

@app.get("/health")
def health():
    return {"health": "ok", "database": "connected"}
