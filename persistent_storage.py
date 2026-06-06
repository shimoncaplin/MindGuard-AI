import os
import sqlite3
import pandas as pd
from datetime import datetime


BACKUP_DIR = "backups"
AUTO_BACKUP_FILE = os.path.join(BACKUP_DIR, "mindguard_observations_autobackup.csv")
LAST_BACKUP_FILE = os.path.join(BACKUP_DIR, "last_backup.txt")


def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def backup_observations_to_csv(df):
    ensure_backup_dir()

    if df is None or df.empty:
        empty_df = pd.DataFrame(columns=["id", "timestamp", "prompt", "response", "score", "status"])
        empty_df.to_csv(AUTO_BACKUP_FILE, index=False)
    else:
        df.to_csv(AUTO_BACKUP_FILE, index=False)

    timestamp = datetime.now().isoformat(timespec="seconds")

    with open(LAST_BACKUP_FILE, "w", encoding="utf-8") as f:
        f.write(timestamp)

    return {
        "backup_file": AUTO_BACKUP_FILE,
        "timestamp": timestamp,
        "records": 0 if df is None else len(df)
    }


def get_backup_status():
    ensure_backup_dir()

    exists = os.path.exists(AUTO_BACKUP_FILE)
    last_backup = "Never"

    if os.path.exists(LAST_BACKUP_FILE):
        with open(LAST_BACKUP_FILE, "r", encoding="utf-8") as f:
            last_backup = f.read().strip() or "Never"

    records = 0

    if exists:
        try:
            backup_df = pd.read_csv(AUTO_BACKUP_FILE)
            records = len(backup_df)
        except Exception:
            records = 0

    return {
        "exists": exists,
        "last_backup": last_backup,
        "records": records,
        "backup_file": AUTO_BACKUP_FILE
    }


def restore_backup_to_database(db_file, save_function=None):
    ensure_backup_dir()

    if not os.path.exists(AUTO_BACKUP_FILE):
        return {
            "restored": 0,
            "status": "NO BACKUP FOUND"
        }

    backup_df = pd.read_csv(AUTO_BACKUP_FILE)

    required = ["prompt", "response"]
    missing = [col for col in required if col not in backup_df.columns]

    if missing:
        raise ValueError("Backup CSV is missing required columns: " + ", ".join(missing))

    restored = 0

    if save_function is not None:
        for _, row in backup_df.iterrows():
            prompt = str(row["prompt"])
            response = str(row["response"])

            if prompt.strip() and response.strip():
                save_function(prompt, response)
                restored += 1

        return {
            "restored": restored,
            "status": "RESTORED USING SAVE FUNCTION"
        }

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        for _, row in backup_df.iterrows():
            prompt = str(row["prompt"])
            response = str(row["response"])

            if prompt.strip() and response.strip():
                timestamp = str(row.get("timestamp", datetime.now().isoformat()))
                score = int(row.get("score", 0))
                status = str(row.get("status", "UNKNOWN"))

                cursor.execute(
                    """
                    INSERT INTO observations (timestamp, prompt, response, score, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (timestamp, prompt, response, score, status)
                )

                restored += 1

        conn.commit()
    finally:
        conn.close()

    return {
        "restored": restored,
        "status": "RESTORED DIRECTLY"
    }


def export_database_health(df):
    if df is None or df.empty:
        return {
            "database_status": "EMPTY",
            "total_records": 0,
            "good": 0,
            "weak": 0,
            "bad": 0,
            "recommendation": "Restore from backup or run new tests."
        }

    statuses = df["status"].astype(str).tolist() if "status" in df.columns else []

    bad_count = statuses.count("BAD")
    weak_count = statuses.count("WEAK")
    good_count = statuses.count("GOOD")

    if bad_count > 0:
        db_status = "HAS CRITICAL RECORDS"
        recommendation = "Review Root Cause Analysis before deployment."
    elif weak_count > 0:
        db_status = "HAS WEAK RECORDS"
        recommendation = "Review weak responses and continue monitoring."
    else:
        db_status = "HEALTHY"
        recommendation = "Create a backup before the next update."

    return {
        "database_status": db_status,
        "total_records": len(df),
        "good": good_count,
        "weak": weak_count,
        "bad": bad_count,
        "recommendation": recommendation
    }
