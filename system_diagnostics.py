import os
import sqlite3
import importlib
from datetime import datetime
import pandas as pd


def check_dependency(module_name):
    try:
        importlib.import_module(module_name)
        return "PASS", "Installed"
    except Exception as e:
        return "FAIL", str(e)


def check_file_exists(file_path):
    if os.path.exists(file_path):
        return "PASS", "Found"
    return "WARNING", "Missing"


def check_sqlite_connection(db_file):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return "PASS", "SQLite connection works"
    except Exception as e:
        return "FAIL", str(e)


def check_table_exists(db_file, table_name):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        result = cursor.fetchone()
        conn.close()

        if result:
            return "PASS", f"Table exists: {table_name}"

        return "WARNING", f"Table missing: {table_name}"
    except Exception as e:
        return "FAIL", str(e)


def check_observation_count(db_file):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='observations'"
        )

        if not cursor.fetchone():
            conn.close()
            return "WARNING", "observations table missing", 0

        cursor.execute("SELECT COUNT(*) FROM observations")
        count = cursor.fetchone()[0]
        conn.close()

        if count == 0:
            return "WARNING", "No observations found", count

        return "PASS", f"{count} observations found", count
    except Exception as e:
        return "FAIL", str(e), 0


def check_backup_folder():
    if os.path.exists("backups"):
        return "PASS", "Backup folder exists"
    return "WARNING", "Backup folder missing"


def run_system_diagnostics(db_file):
    checks = []

    def add(area, check, status, detail):
        checks.append({
            "Area": area,
            "Check": check,
            "Status": status,
            "Detail": detail
        })

    status, detail = check_sqlite_connection(db_file)
    add("Database", "SQLite Connection", status, detail)

    for table in ["observations", "workspaces", "workspace_observations"]:
        status, detail = check_table_exists(db_file, table)
        add("Database", f"Table: {table}", status, detail)

    status, detail, count = check_observation_count(db_file)
    add("Database", "Observation Count", status, detail)

    status, detail = check_backup_folder()
    add("Storage", "Backup Folder", status, detail)

    for file_path in [
        "dashboard.py",
        "requirements.txt",
        "logo.png",
        "workspace_manager.py",
        "persistent_storage.py",
        "red_team_lab.py",
        "root_cause_analyzer.py",
        "backup_manager.py",
    ]:
        status, detail = check_file_exists(file_path)
        add("Files", file_path, status, detail)

    dependency_map = {
        "streamlit": "streamlit",
        "pandas": "pandas",
        "reportlab": "reportlab",
        "streamlit-mic-recorder": "streamlit_mic_recorder",
        "google-generativeai": "google.generativeai",
    }

    for package_name, module_name in dependency_map.items():
        status, detail = check_dependency(module_name)
        add("Dependencies", package_name, status, detail)

    df = pd.DataFrame(checks)

    fail_count = len(df[df["Status"] == "FAIL"])
    warning_count = len(df[df["Status"] == "WARNING"])
    pass_count = len(df[df["Status"] == "PASS"])

    if fail_count > 0:
        overall = "FAIL"
    elif warning_count > 0:
        overall = "WARNING"
    else:
        overall = "PASS"

    summary = {
        "overall_status": overall,
        "pass_count": pass_count,
        "warning_count": warning_count,
        "fail_count": fail_count,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "observation_count": count
    }

    return df, summary


def create_diagnostics_report(checks_df, summary):
    report = "MindGuard AI System Diagnostics Report\n\n"
    report += f"Checked At: {summary['checked_at']}\n"
    report += f"Overall Status: {summary['overall_status']}\n"
    report += f"PASS: {summary['pass_count']}\n"
    report += f"WARNING: {summary['warning_count']}\n"
    report += f"FAIL: {summary['fail_count']}\n"
    report += f"Observation Count: {summary['observation_count']}\n\n"

    report += "Checks:\n"

    for _, row in checks_df.iterrows():
        report += f"- [{row['Status']}] {row['Area']} / {row['Check']}: {row['Detail']}\n"

    return report
