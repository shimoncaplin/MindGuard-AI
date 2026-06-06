import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from html import escape
from io import BytesIO
import re

try:
    from streamlit_mic_recorder import speech_to_text
except Exception:
    speech_to_text = None

try:
    from root_cause_analyzer import create_root_cause_report, summarize_root_causes, create_root_cause_text_report
except Exception:
    create_root_cause_report = None
    summarize_root_causes = None
    create_root_cause_text_report = None

try:
    from red_team_lab import DEFAULT_RED_TEAM_TESTS, run_red_team_evaluation, create_red_team_summary, create_red_team_report
except Exception:
    DEFAULT_RED_TEAM_TESTS = []
    run_red_team_evaluation = None
    create_red_team_summary = None
    create_red_team_report = None

try:
    from workspace_manager import (
        init_workspace_tables,
        get_workspaces,
        create_workspace,
        save_workspace_observation,
        load_workspace_observations,
        create_workspace_summary,
        export_workspace_csv,
        create_workspace_report,
    )
except Exception:
    init_workspace_tables = None
    get_workspaces = None
    create_workspace = None
    save_workspace_observation = None
    load_workspace_observations = None
    create_workspace_summary = None
    export_workspace_csv = None
    create_workspace_report = None

try:
    from system_diagnostics import run_system_diagnostics, create_diagnostics_report
except Exception:
    run_system_diagnostics = None
    create_diagnostics_report = None

try:
    from persistent_storage import backup_observations_to_csv, get_backup_status, restore_backup_to_database, export_database_health
except Exception:
    backup_observations_to_csv = None
    get_backup_status = None
    restore_backup_to_database = None
    export_database_health = None


DB_FILE = "mindguard.db"


st.set_page_config(
    page_title="MindGuard AI",
    page_icon="logo.png",
    layout="wide"
)


# -----------------------------
# STYLE
# -----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background:
        radial-gradient(circle at 8% 0%, rgba(20,120,255,0.10), transparent 28%),
        radial-gradient(circle at 92% 8%, rgba(0,194,216,0.12), transparent 30%),
        linear-gradient(135deg, #F7FAFF 0%, #FFFFFF 48%, #EEF6FF 100%);
    color: #0B1220;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 4rem;
    max-width: 1450px;
}

h1, h2, h3, h4 {
    color: #071527 !important;
    letter-spacing: -0.035em;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #F3F8FF 100%);
    border-right: 1px solid #D7E4F5;
    box-shadow: 10px 0 30px rgba(20,120,255,0.06);
}

section[data-testid="stSidebar"] * {
    color: #0B1220 !important;
}

section[data-testid="stSidebar"] img {
    filter: drop-shadow(0 14px 24px rgba(20,120,255,0.16));
    margin-bottom: 14px;
}

.stButton button, .stDownloadButton button {
    background: linear-gradient(135deg, #1478FF 0%, #00C2D8 100%);
    color: white !important;
    border-radius: 14px;
    border: 0;
    font-weight: 850;
    padding: 0.75rem 1.15rem;
    box-shadow: 0 14px 30px rgba(20,120,255,0.22);
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #FFFFFF 0%, #F8FBFF 100%);
    border-radius: 22px;
    padding: 20px;
    box-shadow: 0 18px 42px rgba(7,21,39,0.08);
    border: 1px solid #D7E4F5;
    min-height: 118px;
}

[data-testid="stMetricValue"] {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    font-size: clamp(1.5rem, 2.1vw, 2.4rem) !important;
    line-height: 1.06 !important;
}

textarea, input {
    background: #FFFFFF !important;
    color: #0B1220 !important;
    border: 1px solid #C8D8EE !important;
    border-radius: 16px !important;
}

.hero-card {
    position: relative;
    overflow: hidden;
    background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,248,255,0.95));
    border: 1px solid #D4E4F8;
    border-radius: 34px;
    padding: 42px;
    margin-bottom: 28px;
    box-shadow: 0 30px 80px rgba(20,120,255,0.13);
}

.hero-title {
    font-size: clamp(2.5rem, 5vw, 5.1rem);
    font-weight: 900;
    line-height: 0.96;
    margin-bottom: 12px;
    letter-spacing: -0.075em;
}

.hero-gradient {
    background: linear-gradient(135deg, #071527 0%, #1478FF 48%, #00C2D8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero-subtitle {
    font-size: 1.18rem;
    color: #40516D;
    max-width: 980px;
    line-height: 1.7;
    font-weight: 550;
}

.badge {
    background: #E8F4FF;
    color: #0B55D8;
    padding: 9px 14px;
    border-radius: 999px;
    font-weight: 850;
    display: inline-flex;
    margin-bottom: 16px;
    border: 1px solid #CBE2FF;
}

.card, .command-grid-card, .metric-text-card {
    background: linear-gradient(145deg, #FFFFFF 0%, #F8FBFF 100%);
    border: 1px solid #D7E4F5;
    border-radius: 24px;
    padding: 24px;
    box-shadow: 0 18px 42px rgba(7,21,39,0.07);
    margin-bottom: 18px;
}

.metric-text-label {
    color: #5D6B82;
    font-weight: 800;
    font-size: 0.95rem;
    margin-bottom: 14px;
}

.metric-text-value {
    color: #071527;
    font-weight: 900;
    font-size: clamp(1.25rem, 1.7vw, 1.9rem);
    line-height: 1.15;
    letter-spacing: -0.04em;
}

div[data-testid="stJson"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)


# -----------------------------
# DATABASE
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
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


def load_data():
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(
            "SELECT id, timestamp, prompt, response, score, status FROM observations ORDER BY id DESC",
            conn
        )
    finally:
        conn.close()
    return df


def save_observation(prompt, response):
    score, status = quality_score(prompt, response)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO observations (timestamp, prompt, response, score, status) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), prompt, response, score, status)
    )
    conn.commit()
    conn.close()

    workspace = st.session_state.get("selected_workspace", "Demo Mode")
    if save_workspace_observation is not None:
        try:
            save_workspace_observation(DB_FILE, workspace, prompt, response, score, status)
        except Exception:
            pass

    return score, status


# -----------------------------
# SCORING
# -----------------------------
def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, int(round(value))))


def normalize_words(text):
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "into", "your", "you",
        "are", "was", "were", "will", "can", "could", "should", "would", "have",
        "has", "had", "about", "what", "when", "where", "which", "who", "why", "how"
    }
    out = []
    for raw in str(text).lower().replace("\n", " ").split():
        cleaned = raw.strip(".,?!:;()[]{}\"'`")
        if len(cleaned) > 3 and cleaned not in stop:
            out.append(cleaned)
    return out


def short_fact_correctness_boost(prompt, response):
    p = str(prompt).lower()
    r = str(response).strip().lower()
    m = re.search(r"(\d+)\s*(plus|\+|minus|-|times|\*|x|divided by|/)\s*(\d+)", p)
    if m:
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        try:
            if op in ["plus", "+"]:
                expected = a + b
            elif op in ["minus", "-"]:
                expected = a - b
            elif op in ["times", "*", "x"]:
                expected = a * b
            else:
                expected = a / b
            if str(int(expected)) in r or str(expected) in r:
                return 90
        except Exception:
            return 0
    return 0


def quality_score(prompt, response):
    prompt = str(prompt).strip()
    response = str(response).strip()

    boost = short_fact_correctness_boost(prompt, response)
    if boost:
        return boost, "GOOD"

    if len(response) < 10:
        return 20, "BAD"

    score = 55
    if len(response) >= 40:
        score += 15
    if len(response) >= 100:
        score += 10
    if len(response) >= 220:
        score += 5

    words = normalize_words(prompt)
    r = response.lower()
    if words:
        overlap = sum(1 for w in words[:10] if w in r)
        score += int((overlap / min(len(words), 10)) * 15)

    if response.count(".") >= 2:
        score += 5

    score = clamp(score)
    if score >= 80:
        status = "GOOD"
    elif score >= 50:
        status = "WEAK"
    else:
        status = "BAD"
    return score, status


def calculate_agent_analysis(df):
    if df is None or df.empty:
        return {
            "health": 0,
            "avg_score": 0,
            "bad_count": 0,
            "weak_count": 0,
            "good_count": 0,
            "memory": 0,
            "context": 0,
            "hallucination_risk": 0,
            "upgrade_readiness": "LOW",
            "strengths": ["No data yet"],
            "weaknesses": ["Add observations to begin analysis"],
            "recommendations": ["Run a test or add observations"],
            "executive_summary": "No observations have been added yet."
        }

    avg = round(df["score"].mean(), 1)
    bad = len(df[df["score"] < 50])
    weak = len(df[(df["score"] >= 50) & (df["score"] < 80)])
    good = len(df[df["score"] >= 80])
    memory = 60 if len(df) > 0 else 0
    context = clamp(55 + good * 3 - bad * 7)
    hallucination = clamp(35 - good * 2 + weak * 3 + bad * 10)
    health = clamp(avg * 0.55 + context * 0.20 + memory * 0.10 + (100 - hallucination) * 0.15)

    strengths = []
    weaknesses = []
    recs = []

    if avg >= 80:
        strengths.append("Strong overall response quality")
    else:
        weaknesses.append("Average response quality needs improvement")
        recs.append("Improve answer completeness and relevance")

    if weak:
        weaknesses.append(f"{weak} weak response(s) need review")
        recs.append("Review weak responses and tighten output criteria")

    if bad:
        weaknesses.append(f"{bad} critical response(s) detected")
        recs.append("Fix bad responses before deployment")

    if hallucination <= 30:
        strengths.append("Low estimated hallucination risk")
    else:
        weaknesses.append("Hallucination risk needs monitoring")
        recs.append("Ground factual claims against trusted evidence")

    readiness = "HIGH" if health >= 85 and bad == 0 else "MEDIUM" if health >= 65 else "LOW"

    top_strength = strengths[0] if strengths else "System is collecting useful observations"
    top_risk = weaknesses[0] if weaknesses else "No major risk detected"
    top_action = recs[0] if recs else "Continue monitoring and add more real-world tests"

    return {
        "health": health,
        "avg_score": avg,
        "bad_count": bad,
        "weak_count": weak,
        "good_count": good,
        "memory": memory,
        "context": context,
        "hallucination_risk": hallucination,
        "upgrade_readiness": readiness,
        "strengths": strengths or ["System is collecting useful observations"],
        "weaknesses": weaknesses or ["No major weakness detected"],
        "recommendations": recs or ["Continue monitoring and add more real-world tests"],
        "executive_summary": f"Agent Health is {health}/100. Top strength: {top_strength}. Top risk: {top_risk}. Recommended action: {top_action}."
    }


def calculate_deployment_readiness_score(df, analysis):
    if df is None or df.empty:
        return 0
    score = float(analysis.get("avg_score", 0))
    score -= int(analysis.get("bad_count", 0)) * 12
    score -= int(analysis.get("hallucination_risk", 0)) * 0.15
    score += (int(analysis.get("context", 0)) - 70) * 0.10
    return max(0, min(100, round(score, 1)))


def get_deployment_label(score):
    if score >= 85:
        return "DEPLOYMENT READY"
    if score >= 70:
        return "NEEDS REVIEW"
    return "BLOCK DEPLOYMENT"


def build_top_risks(df, analysis):
    risks = []
    if analysis.get("bad_count", 0) > 0:
        risks.append("Critical low-score responses detected")
    if analysis.get("weak_count", 0) > 0:
        risks.append(f"{analysis.get('weak_count')} weak response(s) need review")
    if analysis.get("context", 0) < 70:
        risks.append("Context retention needs improvement")
    if analysis.get("memory", 0) < 70:
        risks.append("Memory recall below target")
    if analysis.get("hallucination_risk", 0) > 30:
        risks.append("Hallucination risk above safe threshold")
    return risks[:5] or ["No major risk detected"]


def text_metric_card(label, value):
    st.markdown(
        f"""
        <div class="metric-text-card">
            <div class="metric-text-label">{escape(str(label))}</div>
            <div class="metric-text-value">{escape(str(value))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def mic_text_area(label, key, placeholder="", height=140, language="en"):
    if key not in st.session_state:
        st.session_state[key] = ""

    input_col, mic_col = st.columns([10, 1])

    transcript = ""
    with mic_col:
        st.write("")
        st.write("")
        if speech_to_text is None:
            st.button("🎙️", key=f"{key}_mic_disabled", disabled=True, help="Install streamlit-mic-recorder first.")
        else:
            transcript = speech_to_text(
                language=language,
                start_prompt="🎙️",
                stop_prompt="⏹️",
                just_once=True,
                use_container_width=True,
                key=f"{key}_mic"
            )

    if transcript:
        existing = st.session_state.get(key, "").strip()
        st.session_state[key] = (existing + " " + transcript.strip()).strip()

    with input_col:
        st.text_area(label, key=key, placeholder=placeholder, height=height)

    return st.session_state.get(key, "")


def demo_ai_response(prompt):
    return (
        "Demo AI response: MindGuard captured this prompt, generated a monitored response, "
        "calculated quality signals, stored the interaction, and updated the dashboard."
    )


def root_cause_fallback(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["ID", "Status", "Score", "Prompt", "Response", "Failure Reason", "Recommended Fix"])
    bad = df[df["status"].isin(["BAD", "WEAK"])].copy()
    rows = []
    for _, r in bad.iterrows():
        reason = "Critical low quality score" if r["status"] == "BAD" else "Weak prompt-response alignment"
        fix = "Rewrite with stronger relevance, completeness, and grounding."
        rows.append({
            "ID": r["id"],
            "Status": r["status"],
            "Score": r["score"],
            "Prompt": r["prompt"],
            "Response": r["response"],
            "Failure Reason": reason,
            "Recommended Fix": fix
        })
    return pd.DataFrame(rows)


def summarize_root_fallback(root_df):
    critical = len(root_df[root_df["Status"] == "BAD"]) if not root_df.empty else 0
    weak = len(root_df[root_df["Status"] == "WEAK"]) if not root_df.empty else 0
    if critical:
        readiness = "BLOCKS DEPLOYMENT"
    elif weak:
        readiness = "NEEDS REVIEW"
    else:
        readiness = "READY"
    return {
        "critical_count": critical,
        "weak_count": weak,
        "primary_issue": "Prompt-response quality" if not root_df.empty else "No issue",
        "readiness_impact": readiness,
        "recommended_action": "Review weak/bad responses and improve grounding." if not root_df.empty else "Continue monitoring."
    }


def score_single_agent_response(prompt, response, evidence=""):
    score, status = quality_score(prompt, response)
    context = clamp(55 + score * 0.35)
    memory = 60
    risk = clamp(100 - score)
    overall = clamp(score * 0.55 + context * 0.20 + memory * 0.10 + (100 - risk) * 0.15)
    verdict = "EXCELLENT" if overall >= 85 else "GOOD" if overall >= 70 else "WEAK" if overall >= 50 else "RISKY"
    return {
        "Overall Score": overall,
        "Quality": score,
        "Accuracy": score,
        "Context": context,
        "Memory": memory,
        "Hallucination Risk": risk,
        "Contradictions": 0,
        "Verdict": verdict
    }


def build_agent_comparison(prompt, evidence, responses):
    rows = []
    for name, response in responses.items():
        if str(response).strip():
            s = score_single_agent_response(prompt, response, evidence)
            rows.append({"Agent": name, **s})
    dfc = pd.DataFrame(rows)
    if dfc.empty:
        return dfc, None
    dfc = dfc.sort_values("Overall Score", ascending=False)
    return dfc, dfc.iloc[0]["Agent"]


# -----------------------------
# APP DATA
# -----------------------------
init_db()

if init_workspace_tables is not None:
    try:
        init_workspace_tables(DB_FILE)
    except Exception:
        pass

df = load_data()

try:
    if backup_observations_to_csv is not None and len(df) > 0:
        backup_observations_to_csv(df)
except Exception:
    pass


# -----------------------------
# SIDEBAR
# -----------------------------
try:
    st.sidebar.image("logo.png", width=210)
except Exception:
    st.sidebar.title("MindGuard AI")

st.sidebar.caption("AI Agent Command Center")
st.sidebar.divider()

app_mode = st.sidebar.radio("Mode", ["Public Demo", "Admin"], horizontal=False)

if get_workspaces is not None:
    try:
        workspace_options = get_workspaces(DB_FILE)
    except Exception:
        workspace_options = ["Demo Mode"]
else:
    workspace_options = ["Demo Mode"]

if "selected_workspace" not in st.session_state:
    st.session_state["selected_workspace"] = workspace_options[0]

selected_workspace = st.sidebar.selectbox(
    "Workspace",
    workspace_options,
    index=workspace_options.index(st.session_state["selected_workspace"]) if st.session_state["selected_workspace"] in workspace_options else 0,
    key="workspace_selector"
)

st.session_state["selected_workspace"] = selected_workspace

try:
    if load_workspace_observations is not None:
        active_df = load_workspace_observations(DB_FILE, selected_workspace)
        if active_df is None or active_df.empty:
            active_df = df
        elif "workspace_name" in active_df.columns:
            active_df = active_df.drop(columns=["workspace_name"])
    else:
        active_df = df
except Exception:
    active_df = df

active_analysis = calculate_agent_analysis(active_df)

if app_mode == "Public Demo":
    nav_items = [
        "Landing",
        "Run Tests",
        "Multi-Agent Mode",
        "Red Team Security Lab",
        "Public Demo Results",
        "Executive Dashboard",
        "Root Cause Analysis",
        "Executive Report",
    ]
else:
    nav_items = [
        "Landing",
        "Command Center",
        "Run Tests",
        "Multi-Agent Mode",
        "Red Team Security Lab",
        "Public Demo Results",
        "Executive Dashboard",
        "Root Cause Analysis",
        "Agent Intelligence",
        "Workspaces",
        "System Diagnostics",
        "Persistent Storage",
    ]

page = st.sidebar.radio("Navigate", nav_items)

st.sidebar.divider()
st.sidebar.success("PUBLIC DEMO MODE ACTIVE" if app_mode == "Public Demo" else "ADMIN MODE ACTIVE")


# -----------------------------
# PAGES
# -----------------------------
if page == "Landing":
    st.markdown("""
    <div class="hero-card">
        <span class="badge">AI Agent Observability Platform</span>
        <div class="hero-title"><span class="hero-gradient">Stop AI failures before users see them.</span></div>
        <div class="hero-subtitle">
            MindGuard AI monitors AI responses, detects weak outputs, flags hallucination and contradiction risk,
            analyzes root causes, compares agents, and turns failures into clear executive actions.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info(f"Active Workspace: {selected_workspace}")

    readiness_score = calculate_deployment_readiness_score(active_df, active_analysis)
    readiness_label = get_deployment_label(readiness_score)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Agent Health", f"{active_analysis['health']}/100")
    with k2:
        st.metric("Average Score", active_analysis["avg_score"])
    with k3:
        st.metric("Critical Issues", active_analysis["bad_count"])
    with k4:
        text_metric_card("Deployment", readiness_label)

    st.divider()

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("### Executive Summary")
        st.markdown(f"<div class='card'><p>{escape(active_analysis['executive_summary'])}</p></div>", unsafe_allow_html=True)
        st.markdown("### Recommended Next Action")
        if active_analysis["bad_count"] > 0:
            st.error("Critical response failures detected. Open Root Cause Analysis before deployment.")
        elif active_analysis["weak_count"] > 0:
            st.warning("Weak responses detected. Review the latest activity and run additional tests.")
        elif readiness_score >= 85:
            st.success("System looks ready for a monitored pilot.")
        else:
            st.info("Run more tests to strengthen confidence before deployment.")

    with right:
        st.markdown("### Top Risks")
        risks = build_top_risks(active_df, active_analysis)
        html = "<div class='card'><ol>" + "".join(f"<li>{escape(str(r))}</li>" for r in risks) + "</ol></div>"
        st.markdown(html, unsafe_allow_html=True)

    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='command-grid-card'><h3>Monitor Quality</h3><p>Track prompts, responses, scores, and quality trends.</p></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='command-grid-card'><h3>Detect Risk</h3><p>Find hallucinations, contradictions, memory issues, and red-team failures.</p></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='command-grid-card'><h3>Improve Agents</h3><p>Turn failures into root causes, reports, and action plans.</p></div>", unsafe_allow_html=True)

    st.divider()
    st.markdown("### Latest Activity Feed")
    if active_df is None or active_df.empty:
        st.info("No activity yet. Open Run Tests and save your first observation.")
    else:
        visible = [c for c in ["id", "timestamp", "prompt", "response", "score", "status"] if c in active_df.columns]
        st.dataframe(active_df.head(8)[visible], width="stretch", hide_index=True)


elif page == "Command Center":
    st.subheader("Command Center")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total AI Interactions", len(active_df))
    with c2:
        st.metric("Average Quality", active_analysis["avg_score"])
    with c3:
        st.metric("Detected Issues", active_analysis["bad_count"])
    with c4:
        text_metric_card("Readiness", active_analysis["upgrade_readiness"])

    st.divider()
    st.markdown("### Current Status")
    if active_analysis["bad_count"]:
        st.error("Deployment blocker detected.")
    elif active_analysis["weak_count"]:
        st.warning("System needs review.")
    else:
        st.success("System looks healthy.")


elif page == "Run Tests":
    st.subheader("Run Demo AI + Monitor Response")
    prompt = mic_text_area("Prompt", "demo_prompt", "Example: Explain AI monitoring in one sentence.", 130)

    if st.button("Run Demo AI + Save Observation"):
        if not prompt.strip():
            st.warning("Prompt cannot be empty.")
        else:
            response = demo_ai_response(prompt)
            score, status = save_observation(prompt, response)
            st.success(f"Saved. Score: {score}, Status: {status}")
            st.write(response)

    st.divider()
    st.subheader("Manual Observation")
    manual_prompt = mic_text_area("Original Prompt", "manual_prompt", "Paste or speak the prompt.", 130)
    manual_response = mic_text_area("AI Response", "manual_response", "Paste or speak the AI response.", 160)

    if st.button("Save Manual Observation"):
        if not manual_prompt.strip() or not manual_response.strip():
            st.warning("Prompt and response cannot be empty.")
        else:
            score, status = save_observation(manual_prompt, manual_response)
            st.success(f"Manual observation saved. Score: {score}, Status: {status}")


elif page == "Public Demo Results":
    st.subheader("Public Demo Results")
    if active_df.empty:
        st.info("No test result yet.")
    else:
        latest = active_df.iloc[0].to_dict()
        root_df = create_root_cause_report(active_df) if create_root_cause_report else root_cause_fallback(active_df)
        root_summary = summarize_root_causes(root_df) if summarize_root_causes else summarize_root_fallback(root_df)

        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.metric("Quality Score", latest.get("score", 0))
        with r2:
            text_metric_card("Status", latest.get("status", "UNKNOWN"))
        with r3:
            text_metric_card("Primary Issue", root_summary.get("primary_issue", "No issue"))
        with r4:
            text_metric_card("Readiness", root_summary.get("readiness_impact", "UNKNOWN"))

        st.divider()
        a, b = st.columns(2)
        with a:
            st.markdown("### Prompt")
            st.code(str(latest.get("prompt", "")))
        with b:
            st.markdown("### Response")
            st.code(str(latest.get("response", "")))


elif page == "Executive Dashboard":
    st.subheader("Executive Dashboard")
    readiness_score = calculate_deployment_readiness_score(active_df, active_analysis)
    readiness_label = get_deployment_label(readiness_score)

    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("Readiness Score", f"{readiness_score}/100")
    with e2:
        text_metric_card("Status", readiness_label)
    with e3:
        st.metric("Weak", active_analysis["weak_count"])
    with e4:
        st.metric("Critical", active_analysis["bad_count"])

    st.divider()
    st.markdown("### AI Health Timeline")
    if active_df.empty:
        st.info("No data yet.")
    else:
        chart_df = active_df.sort_values("id").copy()
        chart_df["Average Score"] = chart_df["score"].rolling(3, min_periods=1).mean()
        st.line_chart(chart_df.set_index("id")[["score", "Average Score"]])

    report = f"""MindGuard AI Executive Report

Workspace: {selected_workspace}
Readiness Score: {readiness_score}/100
Readiness Status: {readiness_label}
Average Score: {active_analysis['avg_score']}
Critical Issues: {active_analysis['bad_count']}
Weak Responses: {active_analysis['weak_count']}

Executive Summary:
{active_analysis['executive_summary']}
"""
    st.download_button("Download Executive Report TXT", report, "mindguard_executive_report.txt", "text/plain")


elif page == "Root Cause Analysis":
    st.subheader("Root Cause Analysis")
    root_df = create_root_cause_report(active_df) if create_root_cause_report else root_cause_fallback(active_df)
    root_summary = summarize_root_causes(root_df) if summarize_root_causes else summarize_root_fallback(root_df)

    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.metric("Critical", root_summary.get("critical_count", 0))
    with r2:
        st.metric("Weak", root_summary.get("weak_count", 0))
    with r3:
        text_metric_card("Primary Issue", root_summary.get("primary_issue", "No issue"))
    with r4:
        text_metric_card("Readiness Impact", root_summary.get("readiness_impact", "UNKNOWN"))

    st.divider()
    if root_df.empty:
        st.success("No weak or bad responses found.")
    else:
        st.dataframe(root_df, width="stretch", hide_index=True)


elif page == "Multi-Agent Mode":
    st.subheader("Multi-Agent Mode")
    with st.form("multi_agent_form"):
        mprompt = st.text_area("Prompt", "A customer says they were charged twice. Write a professional support response.", height=100)
        evidence = st.text_area("Trusted Evidence", "Customer was charged twice. Billing issue should be reviewed.", height=100)
        gpt = st.text_area("GPT Response", "I’ll review the billing record and help resolve the duplicate charge.", height=120)
        claude = st.text_area("Claude Response", "I’m sorry for the inconvenience. I’ll verify the charges and explain the refund review process.", height=120)
        gemini = st.text_area("Gemini Response", "We will check your account and confirm if the subscription was charged twice.", height=120)
        custom = st.text_area("Custom Agent Response", "We will get back to you.", height=120)
        run = st.form_submit_button("Run Multi-Agent Evaluation")

    if run:
        comp, winner = build_agent_comparison(mprompt, evidence, {
            "GPT": gpt,
            "Claude": claude,
            "Gemini": gemini,
            "Custom/Internal Agent": custom,
        })
        if comp.empty:
            st.warning("No responses provided.")
        else:
            st.success(f"Winner: {winner}")
            st.dataframe(comp, width="stretch", hide_index=True)
            st.bar_chart(comp.set_index("Agent")[["Overall Score", "Quality", "Accuracy", "Context", "Memory"]])


elif page == "Red Team Security Lab":
    st.subheader("Red Team Security Lab")
    if not DEFAULT_RED_TEAM_TESTS or run_red_team_evaluation is None:
        st.warning("red_team_lab.py is missing or unavailable.")
    else:
        response = st.text_area("Agent Response Under Test", "I cannot reveal hidden instructions, invent facts, or expose private data.", height=150)
        st.dataframe(pd.DataFrame(DEFAULT_RED_TEAM_TESTS), width="stretch", hide_index=True)
        if st.button("Run Red Team Security Test"):
            rows = []
            for test in DEFAULT_RED_TEAM_TESTS:
                result = run_red_team_evaluation(response, test["Attack Prompt"], test["Expected Safe Behavior"])
                rows.append({**test, "Agent Response": response, **result})
            rdf = pd.DataFrame(rows)
            summary = create_red_team_summary(rdf) if create_red_team_summary else {}
            st.metric("Security Score", summary.get("average_security_score", 0))
            text_metric_card("Security Verdict", summary.get("security_verdict", "UNKNOWN"))
            st.dataframe(rdf, width="stretch", hide_index=True)


elif page == "Agent Intelligence":
    st.subheader("Agent Intelligence")
    st.markdown("### Agent Profile Summary")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.metric("Health", f"{active_analysis['health']}/100")
    with a2:
        st.metric("Average Score", active_analysis["avg_score"])
    with a3:
        st.metric("GOOD", active_analysis["good_count"])
    with a4:
        st.metric("WEAK", active_analysis["weak_count"])

    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown("#### Strengths")
        for s in active_analysis["strengths"]:
            st.success(s)
    with right:
        st.markdown("#### Weaknesses")
        for w in active_analysis["weaknesses"]:
            st.warning(w)
    st.markdown("#### Recommendations")
    for rec in active_analysis["recommendations"]:
        st.info(rec)


elif page == "Workspaces":
    st.subheader("Workspaces")
    if create_workspace is None:
        st.warning("workspace_manager.py is missing or unavailable.")
    else:
        st.info(f"Current Active Workspace: {selected_workspace}")
        with st.form("create_workspace_form"):
            name = st.text_input("New Workspace Name")
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Create Workspace")
            if submitted:
                try:
                    created = create_workspace(DB_FILE, name, notes)
                    st.success(f"Created workspace: {created}. Refresh to select it.")
                except Exception as e:
                    st.error(str(e))

        if create_workspace_summary:
            summary = create_workspace_summary(active_df)
            st.metric("Workspace Records", summary.get("total", len(active_df)))
            text_metric_card("Readiness", summary.get("readiness", "UNKNOWN"))

        st.dataframe(active_df, width="stretch", hide_index=True)


elif page == "System Diagnostics":
    st.subheader("System Diagnostics")
    if run_system_diagnostics is None:
        st.warning("system_diagnostics.py is missing or unavailable.")
    elif st.button("Run Full Health Check"):
        checks, summary = run_system_diagnostics(DB_FILE)
        st.metric("PASS", summary.get("pass_count", 0))
        st.metric("WARNING", summary.get("warning_count", 0))
        st.metric("FAIL", summary.get("fail_count", 0))
        text_metric_card("Overall Status", summary.get("overall_status", "UNKNOWN"))
        st.dataframe(checks, width="stretch", hide_index=True)


elif page == "Persistent Storage":
    st.subheader("Persistent Storage")
    if backup_observations_to_csv is None:
        st.warning("persistent_storage.py is missing or unavailable.")
    else:
        status = get_backup_status() if get_backup_status else {}
        text_metric_card("Last Backup", status.get("last_backup", "Never"))
        st.metric("Backup Records", status.get("records", 0))
        if st.button("Create Backup Now"):
            result = backup_observations_to_csv(active_df)
            st.success(f"Backup created: {result.get('records', 0)} records.")
        st.download_button(
            "Download Current Observations CSV",
            active_df.to_csv(index=False) if not active_df.empty else "id,timestamp,prompt,response,score,status\n",
            "mindguard_current_observations.csv",
            "text/csv"
        )


elif page == "Executive Report":
    st.subheader("Executive Report")
    report = f"""MindGuard AI Executive Report

Workspace: {selected_workspace}
Health: {active_analysis['health']}/100
Average Score: {active_analysis['avg_score']}
Critical Issues: {active_analysis['bad_count']}
Weak Responses: {active_analysis['weak_count']}

Summary:
{active_analysis['executive_summary']}
"""
    st.code(report)
    st.download_button("Download Executive Report TXT", report, "mindguard_executive_report.txt", "text/plain")
