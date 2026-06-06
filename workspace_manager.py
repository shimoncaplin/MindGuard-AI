import sqlite3
from datetime import datetime
import pandas as pd


def init_workspace_tables(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            notes TEXT DEFAULT ''
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspace_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'UNKNOWN'
        )
    """)

    default_workspaces = [
        ("Demo Mode", "Public testing workspace"),
        ("Internal Testing", "Internal MindGuard testing workspace"),
        ("Client A", "Example client workspace")
    ]

    for name, notes in default_workspaces:
        cursor.execute(
            """
            INSERT OR IGNORE INTO workspaces (name, created_at, notes)
            VALUES (?, ?, ?)
            """,
            (name, datetime.now().isoformat(timespec="seconds"), notes)
        )

    conn.commit()
    conn.close()


def get_workspaces(db_file):
    init_workspace_tables(db_file)

    conn = sqlite3.connect(db_file)

    try:
        df = pd.read_sql_query(
            "SELECT name, created_at, notes FROM workspaces ORDER BY name ASC",
            conn
        )
    finally:
        conn.close()

    if df.empty:
        return ["Demo Mode"]

    return df["name"].astype(str).tolist()


def create_workspace(db_file, name, notes=""):
    cleaned_name = str(name).strip()

    if not cleaned_name:
        raise ValueError("Workspace name cannot be empty.")

    init_workspace_tables(db_file)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO workspaces (name, created_at, notes)
            VALUES (?, ?, ?)
            """,
            (cleaned_name, datetime.now().isoformat(timespec="seconds"), str(notes).strip())
        )
        conn.commit()
    finally:
        conn.close()

    return cleaned_name


def save_workspace_observation(db_file, workspace_name, prompt, response, score, status):
    init_workspace_tables(db_file)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO workspace_observations
            (workspace_name, timestamp, prompt, response, score, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_name,
                datetime.now().isoformat(timespec="seconds"),
                prompt,
                response,
                int(score),
                status
            )
        )

        conn.commit()
    finally:
        conn.close()


def load_workspace_observations(db_file, workspace_name):
    init_workspace_tables(db_file)

    conn = sqlite3.connect(db_file)

    try:
        df = pd.read_sql_query(
            """
            SELECT id, workspace_name, timestamp, prompt, response, score, status
            FROM workspace_observations
            WHERE workspace_name = ?
            ORDER BY id DESC
            """,
            conn,
            params=(workspace_name,)
        )
    finally:
        conn.close()

    return df


def create_workspace_summary(df):
    if df is None or df.empty:
        return {
            "total": 0,
            "average_score": 0,
            "good": 0,
            "weak": 0,
            "bad": 0,
            "readiness": "NO DATA"
        }

    statuses = df["status"].astype(str).tolist()
    average_score = round(df["score"].mean(), 1)

    good = statuses.count("GOOD")
    weak = statuses.count("WEAK")
    bad = statuses.count("BAD")

    if bad > 0:
        readiness = "BLOCK DEPLOYMENT"
    elif average_score >= 85:
        readiness = "READY"
    elif average_score >= 70:
        readiness = "NEEDS REVIEW"
    else:
        readiness = "NOT READY"

    return {
        "total": len(df),
        "average_score": average_score,
        "good": good,
        "weak": weak,
        "bad": bad,
        "readiness": readiness
    }


def export_workspace_csv(df):
    if df is None or df.empty:
        return "id,workspace_name,timestamp,prompt,response,score,status\n"

    return df.to_csv(index=False)


def create_workspace_report(workspace_name, summary, df):
    report = f"MindGuard AI Workspace Report\n\n"
    report += f"Workspace: {workspace_name}\n"
    report += f"Total Observations: {summary['total']}\n"
    report += f"Average Score: {summary['average_score']}\n"
    report += f"GOOD: {summary['good']}\n"
    report += f"WEAK: {summary['weak']}\n"
    report += f"BAD: {summary['bad']}\n"
    report += f"Readiness: {summary['readiness']}\n\n"

    report += "Observations:\n"

    if df is not None and not df.empty:
        for _, row in df.iterrows():
            report += f"\nID: {row.get('id', '')}\n"
            report += f"Prompt: {row.get('prompt', '')}\n"
            report += f"Response: {row.get('response', '')}\n"
            report += f"Score: {row.get('score', '')}\n"
            report += f"Status: {row.get('status', '')}\n"

    return report
