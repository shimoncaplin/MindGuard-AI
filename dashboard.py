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
    prompt = prompt.strip()

    if len(response) < 10:
        return 20, "BAD"
    if len(response) < 40:
        return 55, "WEAK"

    score = 70

    if len(response) >= 80:
        score += 10
    if len(response) >= 160:
        score += 5
    if len(prompt) > 0 and any(word.lower() in response.lower() for word in prompt.split()[:5]):
        score += 5
    if "i don't know" in response.lower() or "cannot answer" in response.lower():
        score -= 15
    if response.count(".") >= 2:
        score += 5

    score = max(0, min(score, 100))

    if score >= 80:
        status = "GOOD"
    elif score >= 50:
        status = "WEAK"
    else:
        status = "BAD"

    return score, status


def demo_ai_response(prompt):
    return (
        "Demo AI response: MindGuard captured this prompt, generated a monitored response, "
        "calculated a quality score, stored the interaction, and updated the dashboard. "
        "In production, this layer can monitor real AI models such as OpenAI, Gemini, Claude, "
        "or custom enterprise AI agents."
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


def load_data():
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query(
        "SELECT id,timestamp,prompt,response,score,status FROM observations ORDER BY id DESC",
        conn
    )

    conn.close()
    return df


def calculate_agent_analysis(df):
    if len(df) == 0:
        return {
            "health": 0,
            "avg_score": 0,
            "bad_count": 0,
            "weak_count": 0,
            "good_count": 0,
            "avg_response_length": 0,
            "strengths": ["No data yet"],
            "weaknesses": ["Add observations to begin analysis"],
            "recommendations": ["Run demo AI or upload test data"],
            "upgrade_readiness": "LOW"
        }

    avg_score = round(df["score"].mean(), 1)
    bad_count = len(df[df["score"] < 50])
    weak_count = len(df[(df["score"] >= 50) & (df["score"] < 80)])
    good_count = len(df[df["score"] >= 80])
    avg_response_length = round(df["response"].astype(str).str.len().mean(), 1)

    issue_penalty = bad_count * 8 + weak_count * 3
    health = int(max(0, min(100, avg_score - issue_penalty + min(good_count * 2, 10))))

    strengths = []
    weaknesses = []
    recommendations = []

    if avg_score >= 80:
        strengths.append("Strong average response quality")
    else:
        weaknesses.append("Average response quality needs improvement")
        recommendations.append("Improve answer completeness and relevance")

    if bad_count == 0:
        strengths.append("No critical low-score responses detected")
    else:
        weaknesses.append(f"{bad_count} problematic responses detected")
        recommendations.append("Review low-scoring responses and identify repeated failure patterns")

    if avg_response_length >= 80:
        strengths.append("Responses contain enough detail for useful analysis")
    else:
        weaknesses.append("Responses are often too short")
        recommendations.append("Increase response detail and context retention")

    if weak_count > 0:
        weaknesses.append(f"{weak_count} responses are weak or incomplete")
        recommendations.append("Add clearer instructions and stronger response quality criteria")

    if health >= 80:
        upgrade_readiness = "HIGH"
    elif health >= 60:
        upgrade_readiness = "MEDIUM"
    else:
        upgrade_readiness = "LOW"

    if not strengths:
        strengths.append("System is collecting data successfully")

    if not recommendations:
        recommendations.append("Continue monitoring and add more test cases")

    return {
        "health": health,
        "avg_score": avg_score,
        "bad_count": bad_count,
        "weak_count": weak_count,
        "good_count": good_count,
        "avg_response_length": avg_response_length,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "upgrade_readiness": upgrade_readiness
    }


def score_badge(status):
    if status == "GOOD":
        return "🟢 GOOD"
    if status == "WEAK":
        return "🟡 WEAK"
    return "🔴 BAD"


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

.card {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 6px 22px rgba(15, 23, 42, 0.06);
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

try:
    st.image("logo.png", width=520)
except Exception:
    st.title("🧠 MindGuard AI")

st.markdown("""
<div class="hero-card">
    <div class="hero-title">MindGuard AI</div>
    <div class="hero-subtitle">AI Agent Monitoring & Optimization Platform</div>
    <p>
    MindGuard AI monitors prompts, responses, quality scores, degradation alerts, and agent behavior.
    It helps teams understand how their AI agents perform, where they fail, and what should be improved next.
    </p>
    <span class="badge">🚀 LIVE MVP • Agent Monitoring • Quality Scoring • Upgrade Recommendations</span>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="card">
<h2 style="color:#0F172A;">Getting Started</h2>
<p style="font-size:17px; color:#334155;">
Use MindGuard to test AI responses, monitor quality, detect weak outputs, and analyze agent behavior.
</p>
<ol style="font-size:16px; color:#334155; line-height:1.8;">
<li>Run the demo AI to create a monitored response.</li>
<li>Paste real prompts and AI responses manually.</li>
<li>Upload a CSV dataset of prompts and responses.</li>
<li>Review health scores, weaknesses, recommendations, and upgrade readiness.</li>
</ol>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "Run Tests",
    "Agent Analysis",
    "Dataset Upload",
    "Voice Capture"
])

with tab1:
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

df = load_data()
analysis = calculate_agent_analysis(df)

with tab2:
    st.subheader("🤖 Agent Analysis")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Agent Health Score", f"{analysis['health']}/100")

    with col2:
        st.metric("Average Quality Score", analysis["avg_score"])

    with col3:
        st.metric("Detected Issues", analysis["bad_count"])

    with col4:
        st.metric("Upgrade Readiness", analysis["upgrade_readiness"])

    if analysis["health"] >= 80:
        st.success("🟢 Agent health is strong.")
    elif analysis["health"] >= 60:
        st.warning("🟡 Agent health is acceptable but improvement is recommended.")
    else:
        st.error("🔴 Agent health is weak. Review issues before scaling.")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.markdown("### Strengths")
        for item in analysis["strengths"]:
            st.success(f"✓ {item}")

    with right:
        st.markdown("### Weaknesses")
        for item in analysis["weaknesses"]:
            st.warning(f"• {item}")

    st.divider()

    st.markdown("### Recommended Improvements")
    for item in analysis["recommendations"]:
        st.info(f"→ {item}")

    st.divider()

    st.markdown("### Upgrade Safety Gate")

    safety_pass = analysis["bad_count"] == 0
    quality_pass = analysis["avg_score"] >= 70 if len(df) > 0 else False
    consistency_pass = analysis["weak_count"] <= max(1, len(df) * 0.4) if len(df) > 0 else False

    gate_col1, gate_col2, gate_col3 = st.columns(3)

    with gate_col1:
        st.metric("Safety Check", "PASS" if safety_pass else "FAIL")

    with gate_col2:
        st.metric("Quality Check", "PASS" if quality_pass else "FAIL")

    with gate_col3:
        st.metric("Consistency Check", "PASS" if consistency_pass else "FAIL")

    if safety_pass and quality_pass and consistency_pass:
        st.success("Upgrade Candidate: Approved for controlled testing.")
    else:
        st.warning("Upgrade Candidate: Not ready. Improve weak areas first.")

    st.divider()

    st.markdown("### Quality Trend")

    if len(df) >= 2:
        trend_df = df.sort_values("id")[["id", "score"]]
        st.line_chart(trend_df.set_index("id"))
    else:
        st.info("Add at least 2 observations to show a quality trend.")

with tab3:
    st.subheader("📂 Upload Prompt / Response Dataset")

    st.write("Upload a CSV file with two columns: `prompt` and `response`.")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

    if uploaded_file is not None:
        try:
            uploaded_df = pd.read_csv(uploaded_file)

            if "prompt" not in uploaded_df.columns or "response" not in uploaded_df.columns:
                st.error("CSV must include columns named: prompt, response")
            else:
                st.dataframe(uploaded_df, width="stretch")

                if st.button("Analyze + Save Dataset"):
                    saved_count = 0

                    for _, row in uploaded_df.iterrows():
                        prompt_value = str(row["prompt"])
                        response_value = str(row["response"])

                        if prompt_value.strip() and response_value.strip():
                            save_observation(prompt_value, response_value)
                            saved_count += 1

                    st.success(f"{saved_count} observations saved and analyzed.")

        except Exception as e:
            st.error("CSV upload failed.")
            st.code(str(e))

with tab4:
    st.subheader("🎙 Voice Capture")

    st.write(
        "Record voice notes, lyrics, spoken prompts, or agent feedback. "
        "This demo stores audio for download. Transcription can be connected later."
    )

    audio_value = st.audio_input("Record your voice")

    if audio_value is not None:
        st.audio(audio_value)

        audio_bytes = audio_value.getvalue()

        st.success("Voice recording captured.")

        st.download_button(
            label="Download voice recording",
            data=audio_bytes,
            file_name="mindguard_voice_recording.wav",
            mime="audio/wav"
        )

st.divider()

st.subheader("System Health")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total AI Interactions", len(df))

with col2:
    st.metric("Average Quality Score", analysis["avg_score"])

with col3:
    st.metric("Detected Issues", analysis["bad_count"])

with col4:
    st.metric("Healthy Responses", analysis["good_count"])

if len(df) > 0 and analysis["bad_count"] > 0:
    st.error(f"🚨 AI DEGRADATION DETECTED: {analysis['bad_count']} responses scored under 50")
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
    visible_df = df.copy()
    visible_df["status"] = visible_df["status"].apply(score_badge)
    st.dataframe(visible_df, width="stretch")

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
    st.code(score_badge(latest["status"]))

st.divider()

st.caption(
    "MindGuard AI MVP — agent monitoring, quality scoring, degradation detection, dataset analysis, and upgrade readiness."
)
