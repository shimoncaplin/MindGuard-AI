import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

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


def demo_ai_response(prompt):
    return (
        "Demo AI response: MindGuard captured this prompt, generated a monitored response, "
        "calculated a quality score, stored the interaction, and updated the dashboard. "
        "In production, this layer can monitor real AI models such as OpenAI, Gemini, Claude, or custom LLMs."
    )


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


init_db()

st.set_page_config(
    page_title="MindGuard AI",
    page_icon="🧠",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #F8FAFC;
}

h1, h2, h3 {
    color: #0F172A !important;
}

p, label {
    color: #334155 !important;
}

[data-testid="stMetric"] {
    background: white;
    border-radius: 14px;
    padding: 18px;
    box-shadow: 0 3px 14px rgba(15, 23, 42, 0.08);
    border: 1px solid #E2E8F0;
}

.stButton button {
    background-color: #0EA5E9;
    color: white;
    border-radius: 10px;
    border: none;
    font-weight: bold;
}

.stButton button:hover {
    background-color: #0284C7;
    color: white;
}

textarea {
    background: white !important;
    color: #0F172A !important;
}

.hero-card {
    background: white;
    border: 1px solid #D8EAFE;
    border-radius: 22px;
    padding: 34px;
    margin-bottom: 26px;
    box-shadow: 0 10px 35px rgba(14, 165, 233, 0.12);
}

.hero-title {
    font-size: 3.5rem;
    font-weight: 900;
    color: #075985;
    margin-bottom: 0px;
}

.hero-subtitle {
    font-size: 1.25rem;
    color: #334155;
    margin-top: 4px;
}

.badge {
    background: #E0F2FE;
    color: #075985;
    padding: 10px 16px;
    border-radius: 999px;
    font-weight: 700;
    display: inline-block;
    margin-top: 12px;
}
</style>
""", unsafe_allow_html=True)

st.image("logo.png", width=520)

st.markdown("""
<div class="hero-card">
    <div class="hero-title">MindGuard AI</div>
    <div class="hero-subtitle">Monitor AI Before It Fails</div>
    <p>
    MindGuard AI monitors prompts, responses, quality scores, and degradation alerts.
    Monitor AI behavior, identify weak responses, track quality trends, and detect performance degradation before users notice.
    </p>
    <span class="badge">🚀 LIVE MVP • AI Monitoring • Quality Scoring • Degradation Detection</span>
</div>
""", unsafe_allow_html=True)

st.subheader("Run Demo AI + Monitor Response")

with st.form("demo_ai_form"):
    user_prompt = st.text_area(
        "Prompt",
        placeholder="Example: Explain artificial intelligence in one sentence."
    )

    run_ai = st.form_submit_button("Run Demo AI + Save Observation")

    if run_ai:
        if user_prompt.strip() == "":
            st.warning("Prompt cannot be empty.")
        else:
            ai_response = demo_ai_response(user_prompt)
            save_observation(user_prompt, ai_response)

            st.success("Demo AI response saved and monitored.")
            st.write("### Demo AI Response")
            st.write(ai_response)

st.divider()

st.subheader("Manual Observation")

with st.form("manual_form"):
    prompt = st.text_area(
        "Original Prompt",
        placeholder="Paste the prompt here."
    )

    response = st.text_area(
        "AI Response",
        placeholder="Paste the AI response here."
    )

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

st.divider()

st.subheader("System Health")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total AI Interactions", len(df))

with col2:
    avg_score = round(df["score"].mean(), 1) if len(df) > 0 else 0
    st.metric("Average Quality Score", avg_score)

with col3:
    bad_count = len(df[df["score"] < 50]) if len(df) > 0 else 0
    st.metric("Detected Issues", bad_count)

with col4:
    good_count = len(df[df["score"] >= 80]) if len(df) > 0 else 0
    st.metric("Healthy Responses", good_count)

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
    st.info("No observations found yet.")
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

st.divider()

st.caption("MindGuard AI MVP — built to demonstrate AI quality monitoring, degradation detection, and response observability.")
