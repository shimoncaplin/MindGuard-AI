import pandas as pd
from datetime import datetime


def export_observations_csv(df):
    if df is None or df.empty:
        return "id,timestamp,prompt,response,score,status\n"

    export_df = df.copy()
    return export_df.to_csv(index=False)


def export_observations_json(df):
    if df is None or df.empty:
        return "[]"

    export_df = df.copy()
    return export_df.to_json(orient="records", indent=2)


def validate_restore_csv(uploaded_df):
    required = ["prompt", "response"]
    missing = [col for col in required if col not in uploaded_df.columns]

    if missing:
        raise ValueError("Restore CSV must include columns: prompt, response")

    cleaned = uploaded_df.copy()
    cleaned["prompt"] = cleaned["prompt"].astype(str)
    cleaned["response"] = cleaned["response"].astype(str)

    cleaned = cleaned[
        (cleaned["prompt"].str.strip() != "") &
        (cleaned["response"].str.strip() != "")
    ]

    return cleaned


def create_backup_summary(df):
    if df is None or df.empty:
        return {
            "total_records": 0,
            "good": 0,
            "weak": 0,
            "bad": 0,
            "latest_backup_time": datetime.now().isoformat(timespec="seconds"),
            "status": "NO DATA"
        }

    statuses = df["status"].astype(str).tolist() if "status" in df.columns else []

    return {
        "total_records": len(df),
        "good": statuses.count("GOOD"),
        "weak": statuses.count("WEAK"),
        "bad": statuses.count("BAD"),
        "latest_backup_time": datetime.now().isoformat(timespec="seconds"),
        "status": "READY"
    }
