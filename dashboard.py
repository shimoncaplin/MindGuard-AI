import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from html import escape

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


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, int(value)))


def normalize_words(text):
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "your",
        "you", "are", "was", "were", "will", "can", "could", "should", "would",
        "have", "has", "had", "about", "what", "when", "where", "which", "who",
        "why", "how", "does", "did", "doing", "make", "made", "using", "use"
    }

    words = []
    for raw in str(text).lower().replace("\n", " ").split():
        cleaned = raw.strip(".,?!:;()[]{}\"'`")
        if len(cleaned) > 3 and cleaned not in stopwords:
            words.append(cleaned)

    return words


def quality_score(prompt, response):
    prompt = str(prompt).strip()
    response = str(response).strip()

    if len(response) < 10:
        return 20, "BAD"

    score = 55

    if len(response) >= 40:
        score += 15
    if len(response) >= 100:
        score += 10
    if len(response) >= 220:
        score += 5

    prompt_words = normalize_words(prompt)
    response_lower = response.lower()

    overlap = 0
    for word in prompt_words[:10]:
        if word in response_lower:
            overlap += 1

    if prompt_words:
        relevance_ratio = overlap / min(len(prompt_words), 10)
        score += int(relevance_ratio * 15)

    risk_phrases = [
        "i don't know",
        "i cannot answer",
        "not sure",
        "random",
        "maybe",
        "probably",
        "as an ai language model",
        "i am unable"
    ]

    if any(phrase in response_lower for phrase in risk_phrases):
        score -= 15

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


def estimate_accuracy_score(prompt, response):
    response = str(response).strip()
    prompt = str(prompt).strip()

    if not response:
        return 0

    score = 70

    if len(response) < 30:
        score -= 25
    if len(response) > 80:
        score += 10

    prompt_words = normalize_words(prompt)
    response_lower = response.lower()

    if prompt_words:
        matches = sum(1 for w in prompt_words[:10] if w in response_lower)
        score += int((matches / min(len(prompt_words), 10)) * 15)

    uncertainty_terms = ["not sure", "maybe", "probably", "guess", "random"]
    if any(term in response_lower for term in uncertainty_terms):
        score -= 20

    return clamp(score)


def estimate_consistency_score(df):
    if len(df) < 2:
        return 70

    statuses = df["status"].astype(str).tolist()
    good_rate = statuses.count("GOOD") / len(statuses)
    bad_rate = statuses.count("BAD") / len(statuses)

    score = 60 + int(good_rate * 35) - int(bad_rate * 35)

    response_lengths = df["response"].astype(str).str.len()
    if len(response_lengths) > 1:
        avg = response_lengths.mean()
        std = response_lengths.std()
        if avg > 0:
            variation = std / avg
            if variation > 1.0:
                score -= 15
            elif variation < 0.5:
                score += 10

    return clamp(score)


def estimate_memory_score(df):
    if len(df) == 0:
        return 0

    text = " ".join(df["response"].astype(str).tolist()).lower()

    memory_signals = [
        "as mentioned",
        "previous",
        "earlier",
        "again",
        "context",
        "based on",
        "remember",
        "continue",
        "same",
        "before",
        "you told me",
        "from earlier"
    ]

    hits = sum(1 for signal in memory_signals if signal in text)

    if hits == 0:
        return 45
    if hits <= 2:
        return 60
    if hits <= 4:
        return 75
    return 90


def estimate_context_retention_score(df):
    if len(df) == 0:
        return 0

    scores = []

    for _, row in df.iterrows():
        prompt = str(row["prompt"]).lower()
        response = str(row["response"]).lower()

        prompt_words = set(normalize_words(prompt))

        if not prompt_words:
            scores.append(60)
            continue

        matches = sum(1 for word in prompt_words if word in response)
        ratio = matches / len(prompt_words)

        scores.append(clamp(45 + ratio * 55))

    return clamp(sum(scores) / len(scores))


def estimate_repetition_score(df):
    if len(df) == 0:
        return 100

    responses = df["response"].astype(str).str.lower().tolist()

    repeated_pairs = 0
    checked = 0

    for i in range(len(responses)):
        for j in range(i + 1, len(responses)):
            words_a = set(normalize_words(responses[i]))
            words_b = set(normalize_words(responses[j]))

            if not words_a or not words_b:
                continue

            overlap = len(words_a.intersection(words_b)) / max(1, len(words_a.union(words_b)))
            checked += 1

            if overlap > 0.65:
                repeated_pairs += 1

    if checked == 0:
        return 100

    repetition_rate = repeated_pairs / checked
    return clamp(100 - repetition_rate * 70)


def demo_ai_response(prompt):
    return (
        "Demo AI response: MindGuard captured this prompt, generated a monitored response, "
        "calculated quality, accuracy, consistency, memory, context, repetition, and hallucination-risk signals, "
        "stored the interaction, and updated the agent operations dashboard. "
        "In production, this layer can monitor real AI models, internal agents, customer support bots, "
        "AI workflows, and enterprise LLM systems."
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


def split_memory_facts(memory_text):
    facts = []

    for line in str(memory_text).splitlines():
        cleaned = line.strip(" -•\t")
        if cleaned:
            facts.append(cleaned)

    if not facts and str(memory_text).strip():
        facts = [part.strip() for part in str(memory_text).split(".") if part.strip()]

    return facts


def analyze_memory_recall(memory_text, agent_response):
    facts = split_memory_facts(memory_text)
    response_lower = str(agent_response).lower()

    remembered = []
    missing = []

    for fact in facts:
        fact_words = normalize_words(fact)
        if not fact_words:
            missing.append(fact)
            continue

        matches = sum(1 for word in fact_words if word in response_lower)
        ratio = matches / len(fact_words)

        if ratio >= 0.45:
            remembered.append(fact)
        else:
            missing.append(fact)

    if not facts:
        score = 0
    else:
        score = clamp((len(remembered) / len(facts)) * 100)

    if score >= 80:
        status = "STRONG"
    elif score >= 50:
        status = "PARTIAL"
    else:
        status = "WEAK"

    return {
        "score": score,
        "status": status,
        "remembered": remembered,
        "missing": missing,
        "total": len(facts)
    }


def analyze_hallucination_risk(evidence_text, claim_text):
    evidence_words = set(normalize_words(evidence_text))
    claim_words = set(normalize_words(claim_text))

    if not claim_words:
        return {
            "risk_score": 0,
            "risk_level": "LOW",
            "supported_terms": [],
            "unsupported_terms": [],
            "summary": "No claim text was provided."
        }

    supported_terms = sorted(list(claim_words.intersection(evidence_words)))
    unsupported_terms = sorted(list(claim_words.difference(evidence_words)))

    unsupported_ratio = len(unsupported_terms) / max(1, len(claim_words))

    risk_score = clamp(unsupported_ratio * 100)

    if risk_score >= 70:
        risk_level = "HIGH"
    elif risk_score >= 40:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    summary = (
        f"Hallucination risk is {risk_level}. "
        f"{len(supported_terms)} terms appear supported by the evidence and "
        f"{len(unsupported_terms)} important terms were not found in the evidence."
    )

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "supported_terms": supported_terms,
        "unsupported_terms": unsupported_terms,
        "summary": summary
    }


def calculate_agent_analysis(df):
    if len(df) == 0:
        return {
            "health": 0,
            "avg_score": 0,
            "bad_count": 0,
            "weak_count": 0,
            "good_count": 0,
            "avg_response_length": 0,
            "accuracy": 0,
            "consistency": 0,
            "memory": 0,
            "context": 0,
            "repetition": 100,
            "hallucination_risk": 0,
            "strengths": ["No data yet"],
            "weaknesses": ["Add observations to begin analysis"],
            "recommendations": ["Run demo AI, save manual observations, or upload a dataset"],
            "upgrade_readiness": "LOW",
            "executive_summary": "No observations have been added yet. Add test data to generate an agent health report."
        }

    avg_score = round(df["score"].mean(), 1)
    bad_count = len(df[df["score"] < 50])
    weak_count = len(df[(df["score"] >= 50) & (df["score"] < 80)])
    good_count = len(df[df["score"] >= 80])
    avg_response_length = round(df["response"].astype(str).str.len().mean(), 1)

    accuracy_scores = [
        estimate_accuracy_score(str(row["prompt"]), str(row["response"]))
        for _, row in df.iterrows()
    ]

    accuracy = clamp(sum(accuracy_scores) / len(accuracy_scores))
    consistency = estimate_consistency_score(df)
    memory = estimate_memory_score(df)
    context = estimate_context_retention_score(df)
    repetition = estimate_repetition_score(df)

    hallucination_risk = clamp(
        (100 - accuracy) * 0.45 +
        (100 - context) * 0.35 +
        bad_count * 8 +
        weak_count * 3
    )

    health = clamp(
        avg_score * 0.30 +
        accuracy * 0.20 +
        consistency * 0.12 +
        memory * 0.10 +
        context * 0.10 +
        repetition * 0.10 +
        (100 - hallucination_risk) * 0.08 -
        bad_count * 4
    )

    strengths = []
    weaknesses = []
    recommendations = []

    if avg_score >= 80:
        strengths.append("Strong overall response quality")
    else:
        weaknesses.append("Average response quality needs improvement")
        recommendations.append("Improve answer completeness, relevance, and structure")

    if accuracy >= 80:
        strengths.append("High estimated answer relevance")
    else:
        weaknesses.append("Estimated answer relevance is not strong enough")
        recommendations.append("Add stronger prompt-response alignment checks")

    if consistency >= 80:
        strengths.append("Consistent agent behavior across observations")
    else:
        weaknesses.append("Agent behavior appears inconsistent")
        recommendations.append("Test repeated prompts and compare output stability")

    if memory >= 75:
        strengths.append("Memory/context signals are visible in responses")
    else:
        weaknesses.append("Memory utilization appears low")
        recommendations.append("Add memory recall testing and evaluate whether important facts are remembered")

    if context >= 75:
        strengths.append("Good context retention across prompt-response pairs")
    else:
        weaknesses.append("Context retention needs improvement")
        recommendations.append("Increase context retention and reduce missing prompt intent")

    if repetition >= 85:
        strengths.append("Low repetition risk detected")
    else:
        weaknesses.append("Repetition risk detected across responses")
        recommendations.append("Reduce repeated phrasing and diversify agent responses")

    if hallucination_risk >= 60:
        weaknesses.append("Hallucination risk is elevated")
        recommendations.append("Add evidence checks before allowing factual claims")
    elif hallucination_risk <= 30:
        strengths.append("Low estimated hallucination risk")

    if bad_count > 0:
        weaknesses.append(f"{bad_count} critical low-score responses detected")
        recommendations.append("Review all BAD responses before scaling this agent")

    if weak_count > 0:
        recommendations.append("Review WEAK responses and create stricter output criteria")

    if health >= 85 and hallucination_risk < 35:
        upgrade_readiness = "HIGH"
    elif health >= 65 and hallucination_risk < 60:
        upgrade_readiness = "MEDIUM"
    else:
        upgrade_readiness = "LOW"

    top_strength = strengths[0] if strengths else "System is collecting data successfully"
    top_risk = weaknesses[0] if weaknesses else "No major risk detected"
    top_action = recommendations[0] if recommendations else "Continue monitoring and add more real-world test cases"

    executive_summary = (
        f"Agent Health is {health}/100. "
        f"Top strength: {top_strength}. "
        f"Top risk: {top_risk}. "
        f"Recommended action: {top_action}."
    )

    return {
        "health": health,
        "avg_score": avg_score,
        "bad_count": bad_count,
        "weak_count": weak_count,
        "good_count": good_count,
        "avg_response_length": avg_response_length,
        "accuracy": accuracy,
        "consistency": consistency,
        "memory": memory,
        "context": context,
        "repetition": repetition,
        "hallucination_risk": hallucination_risk,
        "strengths": strengths or ["System is collecting data successfully"],
        "weaknesses": weaknesses or ["No major weakness detected"],
        "recommendations": recommendations or ["Continue monitoring and add more real-world test cases"],
        "upgrade_readiness": upgrade_readiness,
        "executive_summary": executive_summary
    }


def score_badge(status):
    if status == "GOOD":
        return "🟢 GOOD"
    if status == "WEAK":
        return "🟡 WEAK"
    return "🔴 BAD"


def create_html_report(analysis):
    strengths_html = "".join(f"<li>{escape(item)}</li>" for item in analysis["strengths"])
    weaknesses_html = "".join(f"<li>{escape(item)}</li>" for item in analysis["weaknesses"])
    recommendations_html = "".join(f"<li>{escape(item)}</li>" for item in analysis["recommendations"])

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>MindGuard AI Executive Report</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #F8FAFC;
    color: #0F172A;
    padding: 40px;
}}
.card {{
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
}}
h1 {{
    color: #075985;
}}
.metric {{
    font-size: 28px;
    font-weight: bold;
    color: #0EA5E9;
}}
</style>
</head>
<body>
<h1>MindGuard AI Executive Agent Report</h1>
<div class="card">
<h2>Executive Summary</h2>
<p>{escape(analysis["executive_summary"])}</p>
</div>

<div class="card">
<h2>Current Scores</h2>
<p><b>Agent Health:</b> <span class="metric">{analysis["health"]}/100</span></p>
<p><b>Accuracy:</b> {analysis["accuracy"]}/100</p>
<p><b>Consistency:</b> {analysis["consistency"]}/100</p>
<p><b>Memory:</b> {analysis["memory"]}/100</p>
<p><b>Context Retention:</b> {analysis["context"]}/100</p>
<p><b>Anti-Repetition:</b> {analysis["repetition"]}/100</p>
<p><b>Hallucination Risk:</b> {analysis["hallucination_risk"]}/100</p>
<p><b>Upgrade Readiness:</b> {escape(analysis["upgrade_readiness"])}</p>
</div>

<div class="card">
<h2>Strengths</h2>
<ul>{strengths_html}</ul>
</div>

<div class="card">
<h2>Weaknesses</h2>
<ul>{weaknesses_html}</ul>
</div>

<div class="card">
<h2>Recommendations</h2>
<ul>{recommendations_html}</ul>
</div>
</body>
</html>
"""


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
    <div class="hero-subtitle">AI Agent Monitoring, Memory Evaluation & Risk Analysis</div>
    <p>
    MindGuard AI monitors prompts, responses, quality scores, memory behavior, consistency, context retention,
    repetition risk, hallucination risk, degradation alerts, and upgrade readiness.
    </p>
    <span class="badge">🚀 LIVE MVP • Agent Health • Memory Recall • Hallucination Risk • Executive Reports</span>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="card">
<h2 style="color:#0F172A;">Getting Started</h2>
<p style="font-size:17px; color:#334155;">
Use MindGuard to test AI responses, monitor quality, detect weak outputs, analyze memory recall, detect hallucination risk, and understand where an AI agent can improve.
</p>
<ol style="font-size:16px; color:#334155; line-height:1.8;">
<li>Run the demo AI to create a monitored response.</li>
<li>Paste real prompts and AI responses manually.</li>
<li>Upload a CSV dataset of prompts and responses.</li>
<li>Use Memory Recall Lab to test whether an agent remembers important facts.</li>
<li>Use Hallucination Risk Lab to compare claims against evidence.</li>
<li>Download an executive report for stakeholders.</li>
</ol>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Run Tests",
    "Agent Intelligence",
    "Memory Recall Lab",
    "Hallucination Risk Lab",
    "Dataset Upload",
    "Voice Capture",
    "Executive Report"
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
    st.subheader("🤖 Agent Intelligence Analysis")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Agent Health Score", f"{analysis['health']}/100")

    with col2:
        st.metric("Average Quality Score", analysis["avg_score"])

    with col3:
        st.metric("Detected Issues", analysis["bad_count"])

    with col4:
        st.metric("Upgrade Readiness", analysis["upgrade_readiness"])

    if analysis["health"] >= 85:
        st.success("🟢 Agent health is strong and ready for deeper testing.")
    elif analysis["health"] >= 65:
        st.warning("🟡 Agent health is acceptable but improvements are recommended.")
    else:
        st.error("🔴 Agent health is weak. Do not scale this agent before improving it.")

    st.divider()

    st.markdown("### Intelligence Signals")

    s1, s2, s3, s4, s5, s6 = st.columns(6)

    with s1:
        st.metric("Accuracy", f"{analysis['accuracy']}/100")

    with s2:
        st.metric("Consistency", f"{analysis['consistency']}/100")

    with s3:
        st.metric("Memory", f"{analysis['memory']}/100")

    with s4:
        st.metric("Context", f"{analysis['context']}/100")

    with s5:
        st.metric("Anti-Repetition", f"{analysis['repetition']}/100")

    with s6:
        st.metric("Hallucination Risk", f"{analysis['hallucination_risk']}/100")

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
    consistency_pass = analysis["consistency"] >= 65 if len(df) > 0 else False
    memory_pass = analysis["memory"] >= 55 if len(df) > 0 else False
    context_pass = analysis["context"] >= 60 if len(df) > 0 else False
    hallucination_pass = analysis["hallucination_risk"] < 60 if len(df) > 0 else False

    gate_col1, gate_col2, gate_col3, gate_col4, gate_col5, gate_col6 = st.columns(6)

    with gate_col1:
        st.metric("Safety", "PASS" if safety_pass else "FAIL")

    with gate_col2:
        st.metric("Quality", "PASS" if quality_pass else "FAIL")

    with gate_col3:
        st.metric("Consistency", "PASS" if consistency_pass else "FAIL")

    with gate_col4:
        st.metric("Memory", "PASS" if memory_pass else "FAIL")

    with gate_col5:
        st.metric("Context", "PASS" if context_pass else "FAIL")

    with gate_col6:
        st.metric("Risk", "PASS" if hallucination_pass else "FAIL")

    if safety_pass and quality_pass and consistency_pass and memory_pass and context_pass and hallucination_pass:
        st.success("Upgrade Candidate: Approved for controlled testing.")
    else:
        st.warning("Upgrade Candidate: Not ready. Improve failed gates first.")

    st.divider()

    st.markdown("### Quality Trend")

    if len(df) >= 2:
        trend_df = df.sort_values("id")[["id", "score"]]
        st.line_chart(trend_df.set_index("id"))
    else:
        st.info("Add at least 2 observations to show a quality trend.")

with tab3:
    st.subheader("🧠 Memory Recall Lab")

    st.write(
        "Paste the facts the agent should remember, then paste the agent response. "
        "MindGuard will estimate what was remembered and what was missed."
    )

    with st.form("memory_recall_form"):
        memory_text = st.text_area(
            "Expected Memory Facts",
            value="User is Australian\nUser manages Full Deck Artists\nUser prefers English for coding conversations",
            help="One fact per line. These are the facts the agent should remember."
        )

        agent_response = st.text_area(
            "Agent Response",
            value="The user manages Full Deck Artists and prefers English for coding conversations.",
            help="Paste the agent response you want to test against the expected memory facts."
        )

        run_memory = st.form_submit_button("Analyze Memory Recall")

    if run_memory:
        if not memory_text.strip() or not agent_response.strip():
            st.error("Please enter both Expected Memory Facts and Agent Response before running the analysis.")
            st.stop()

        result = analyze_memory_recall(memory_text, agent_response)

        st.metric("Memory Recall Accuracy", f"{result['score']}/100")
        st.metric("Recall Status", result["status"])

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("### Remembered Facts")
            if result["remembered"]:
                for item in result["remembered"]:
                    st.success(f"✓ {item}")
            else:
                st.warning("No memory facts were detected in the response.")

        with col_b:
            st.markdown("### Missing Facts")
            if result["missing"]:
                for item in result["missing"]:
                    st.error(f"• {item}")
            else:
                st.success("No missing memory facts detected.")

with tab4:
    st.subheader("⚠️ Hallucination Risk Lab")

    st.write(
        "Paste trusted evidence and then paste the AI claim. "
        "MindGuard will estimate whether the claim is supported by the evidence."
    )

    with st.form("hallucination_form"):
        evidence_text = st.text_area(
            "Trusted Evidence",
            placeholder="Example: The customer is located in Australia. The customer manages Full Deck Artists."
        )

        claim_text = st.text_area(
            "AI Claim / Agent Response",
            placeholder="Example: The customer is located in Canada and manages Full Deck Artists."
        )

        run_risk = st.form_submit_button("Analyze Hallucination Risk")

    if run_risk:
        risk = analyze_hallucination_risk(evidence_text, claim_text)

        st.metric("Hallucination Risk Score", f"{risk['risk_score']}/100")
        st.metric("Risk Level", risk["risk_level"])

        if risk["risk_level"] == "HIGH":
            st.error(risk["summary"])
        elif risk["risk_level"] == "MEDIUM":
            st.warning(risk["summary"])
        else:
            st.success(risk["summary"])

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("### Supported Terms")
            if risk["supported_terms"]:
                st.write(", ".join(risk["supported_terms"][:40]))
            else:
                st.warning("No supported terms detected.")

        with col_b:
            st.markdown("### Unsupported Terms")
            if risk["unsupported_terms"]:
                st.write(", ".join(risk["unsupported_terms"][:40]))
            else:
                st.success("No unsupported terms detected.")

with tab5:
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

with tab6:
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

with tab7:
    st.subheader("📄 Executive Agent Report")

    st.markdown("### Summary")
    st.info(analysis["executive_summary"])

    st.markdown("### Current Scores")

    report_col1, report_col2, report_col3 = st.columns(3)

    with report_col1:
        st.metric("Agent Health", f"{analysis['health']}/100")
        st.metric("Accuracy", f"{analysis['accuracy']}/100")

    with report_col2:
        st.metric("Consistency", f"{analysis['consistency']}/100")
        st.metric("Memory", f"{analysis['memory']}/100")

    with report_col3:
        st.metric("Context Retention", f"{analysis['context']}/100")
        st.metric("Hallucination Risk", f"{analysis['hallucination_risk']}/100")

    st.markdown("### Recommended Next Actions")
    for item in analysis["recommendations"]:
        st.write(f"- {item}")

    report_text = f"""
MindGuard AI Executive Agent Report

Agent Health: {analysis['health']}/100
Average Quality Score: {analysis['avg_score']}
Accuracy: {analysis['accuracy']}/100
Consistency: {analysis['consistency']}/100
Memory: {analysis['memory']}/100
Context Retention: {analysis['context']}/100
Anti-Repetition: {analysis['repetition']}/100
Hallucination Risk: {analysis['hallucination_risk']}/100
Detected Issues: {analysis['bad_count']}
Upgrade Readiness: {analysis['upgrade_readiness']}

Executive Summary:
{analysis['executive_summary']}

Strengths:
{chr(10).join("- " + item for item in analysis["strengths"])}

Weaknesses:
{chr(10).join("- " + item for item in analysis["weaknesses"])}

Recommendations:
{chr(10).join("- " + item for item in analysis["recommendations"])}
"""

    st.download_button(
        label="Download Executive Report TXT",
        data=report_text,
        file_name="mindguard_executive_report.txt",
        mime="text/plain"
    )

    html_report = create_html_report(analysis)

    st.download_button(
        label="Download Executive Report HTML",
        data=html_report,
        file_name="mindguard_executive_report.html",
        mime="text/html"
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
    "MindGuard AI MVP — agent intelligence analysis, memory recall, hallucination-risk detection, dataset analysis, degradation alerts, and executive reporting."
)
