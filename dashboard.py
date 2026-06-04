import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import google.generativeai as genai

DB_FILE = "mindguard.db"

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])


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


def save_observation(prompt, response):
    score, status = quality_score(prompt, response)
    timestamp = datetime.now().isoformat()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO observations (timestamp, prompt, response, score, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (timestamp, prompt, response, score, status)
    )

    conn.commit()
    conn.close()


def ask_gemini(prompt):
    model = genai.GenerativeModel("gemini-2.0-flash")
    result = model.generate_content(prompt)
    return result.text


init_db()

st.set_page_config(page_title="MindGuard AI", layout="wide")

st.title("🧠 MindGuard AI Monitoring Platform")

st.subheader("Ask Gemini + Monitor Response")

with st.form("gemini_form"):
    user_prompt = st.text_area("Prompt to send to Gemini")
    run_ai = st.form_submit_button("Run Gemini + Save Observation")

    if run_ai:
        if user_prompt.strip() == "":
            st.warning("Prompt cannot be empty.")
        else:
            try:
                with st.spinner("Calling Gemini..."):
                    ai_response = ask_gemini(user_prompt)

                save_observation(user_prompt, ai_response)
                st.success("Gemini response saved and monitored.")
                st.write("### Gemini Response")
                st.write(ai_response)

            except Exception as e:
                st.error("Gemini request failed.")
                st.code(str(e))

st.divider()

st.subheader("Manual Observation")

with st.form("manual_form"):
    prompt = st.text_area("Prompt")
    response = st.text_area("AI Response")
    submitted = st.form_submit_button("Save Manual Observation")

    if submitted:
        if prompt.strip() == "" or response.strip() == "":
            st.warning("Prompt and response cannot be empty.")
        else:
            save_observation(prompt, response)
            st.success("Manual observation saved.")

conn = sqlite3.connect(DB_FILE)

df = pd.read_sql_query(
    "SELECT id,timestamp,prompt,response,score,status FROM observations ORDER BY id DESC",
    conn
)

conn.close()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Observations", len(df))

with col2:
    avg_score = round(df["score"].mean(), 1) if len(df) > 0 else 0
    st.metric("Average Score", avg_score)

with col3:
    bad_count = len(df[df["score"] < 50]) if len(df) > 0 else 0
    st.metric("Bad Responses", bad_count)

with col4:
    good_count = len(df[df["score"] >= 80]) if len(df) > 0 else 0
    st.metric("Good Responses", good_count)

if len(df) > 0 and bad_count > 0:
    st.error(f"🚨 AI DEGRADATION DETECTED: {bad_count} responses scored under 50")
else:
    st.success("✅ System Stable - No responses under score 50")

st.divider()

st.subheader("🚨 Problem Responses")

bad_responses = df[df["score"] < 50] if len(df) > 0 else df

if len(bad_responses) > 0:
    st.dataframe(bad_responses, width="stretch")
else:
    st.success("No bad responses found")

st.divider()

st.subheader("Recent AI Activity")

if len(df) == 0:
    st.info("No observations found")
else:
    st.dataframe(df, width="stretch")

st.divider()

st.subheader("Latest Observation")

if len(df) > 0:
    latest = df.iloc[0]

    st.write("### Prompt")
    st.code(latest["prompt"])

    st.write("### Response")
    st.code(latest["response"])

    st.metric("Latest Score", int(latest["score"]))

    st.write("### Status")
    st.code(latest["status"])
