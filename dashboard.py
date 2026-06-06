import streamlit as st
try:
    from streamlit_mic_recorder import speech_to_text
except Exception:
    speech_to_text = None
import sqlite3
import pandas as pd
from workspace_manager import init_workspace_tables, get_workspaces, create_workspace, save_workspace_observation, load_workspace_observations, create_workspace_summary, export_workspace_csv, create_workspace_report
from persistent_storage import backup_observations_to_csv, get_backup_status, restore_backup_to_database, export_database_health
from red_team_lab import DEFAULT_RED_TEAM_TESTS, run_red_team_evaluation, create_red_team_summary, create_red_team_report
from backup_manager import export_observations_csv, export_observations_json, validate_restore_csv, create_backup_summary
from benchmark_engine import load_benchmark_csv, create_benchmark_summary
from benchmark_failure_analyzer import analyze_benchmark_failures, create_failed_prompt_details, create_failure_report_text
from agent_memory_trainer import generate_memory_training_plan, generate_memory_rules_text, generate_deployment_policy
from root_cause_analyzer import create_root_cause_report, summarize_root_causes, create_root_cause_text_report
from datetime import datetime
from io import BytesIO
from html import escape
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm


DB_FILE = "mindguard.db"





def mic_text_area(label, key, placeholder="", height=140, language="en"):
    """
    Text area with a microphone button attached on the right.
    Important: transcript is written to session_state BEFORE the text_area widget is rendered,
    avoiding Streamlit's session_state modification error.
    """
    if key not in st.session_state:
        st.session_state[key] = ""

    input_col, mic_col = st.columns([10, 1])

    transcript = ""

    with mic_col:
        st.write("")
        st.write("")
        if speech_to_text is None:
            st.button(
                "🎙️",
                key=f"{key}_mic_disabled",
                disabled=True,
                help="Install streamlit-mic-recorder first."
            )
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
        new_text = transcript.strip()

        if existing:
            st.session_state[key] = existing + " " + new_text
        else:
            st.session_state[key] = new_text

    with input_col:
        st.text_area(
            label,
            key=key,
            placeholder=placeholder,
            height=height
        )

    return st.session_state.get(key, "")



def text_metric_card(label, value):
    safe_label = str(label).replace("<", "&lt;").replace(">", "&gt;")
    safe_value = str(value).replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"""
        <div class="metric-text-card">
            <div class="metric-text-label">{safe_label}</div>
            <div class="metric-text-value">{safe_value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )



def create_public_demo_result_report(latest, root_summary):
    if latest is None:
        return "MindGuard AI Public Demo Result\n\nNo observation available yet."

    return f"""MindGuard AI Public Demo Result

Prompt:
{latest.get("prompt", "")}

Agent Response:
{latest.get("response", "")}

Quality Score:
{latest.get("score", "")}

Status:
{latest.get("status", "")}

Primary Issue:
{root_summary.get("primary_issue", "")}

Readiness Impact:
{root_summary.get("readiness_impact", "")}

Recommended Fix:
{root_summary.get("recommended_action", "")}
"""



def calculate_deployment_readiness_score(df, analysis):
    if df is None or df.empty:
        return 0

    avg_score = float(analysis.get("avg_score", 0))
    bad_count = int(analysis.get("bad_count", 0))
    memory = int(analysis.get("memory", 0))
    context = int(analysis.get("context", 0))
    hallucination_risk = int(analysis.get("hallucination_risk", 0))

    readiness = avg_score
    readiness += (memory - 70) * 0.15
    readiness += (context - 70) * 0.15
    readiness -= hallucination_risk * 0.20
    readiness -= bad_count * 12

    return max(0, min(100, round(readiness, 1)))


def get_deployment_label(score):
    if score >= 85:
        return "DEPLOYMENT READY"
    if score >= 70:
        return "NEEDS REVIEW"
    return "BLOCK DEPLOYMENT"


def build_top_risks(df, analysis):
    risks = []

    if int(analysis.get("bad_count", 0)) > 0:
        risks.append("Critical low-score responses detected")

    if int(analysis.get("context", 0)) < 70:
        risks.append("Weak context retention")

    if int(analysis.get("memory", 0)) < 70:
        risks.append("Memory recall below target")

    if int(analysis.get("hallucination_risk", 0)) > 30:
        risks.append("Hallucination risk above safe threshold")

    if df is not None and not df.empty:
        weak_count = len(df[df["status"].astype(str) == "WEAK"])
        if weak_count > 0:
            risks.append(f"{weak_count} weak response(s) need review")

    if not risks:
        risks.append("No major risk detected")

    return risks[:5]


def create_board_report(df, analysis):
    readiness_score = calculate_deployment_readiness_score(df, analysis)
    readiness_label = get_deployment_label(readiness_score)
    top_risks = build_top_risks(df, analysis)

    report = "MindGuard AI Executive Board Report\n\n"
    report += f"Deployment Readiness Score: {readiness_score}/100\n"
    report += f"Deployment Status: {readiness_label}\n"
    report += f"Average Quality Score: {analysis.get('avg_score', 0)}\n"
    report += f"Total AI Interactions: {len(df) if df is not None else 0}\n"
    report += f"Detected Issues: {analysis.get('bad_count', 0)}\n"
    report += f"Memory Score: {analysis.get('memory', 0)}/100\n"
    report += f"Context Score: {analysis.get('context', 0)}/100\n"
    report += f"Hallucination Risk: {analysis.get('hallucination_risk', 0)}/100\n\n"

    report += "Top Risks:\n"
    for index, risk in enumerate(top_risks, start=1):
        report += f"{index}. {risk}\n"

    report += "\nRecommended Action:\n"

    if readiness_score < 70:
        report += "Block deployment until critical response failures, context weaknesses, and grounding issues are fixed.\n"
    elif readiness_score < 85:
        report += "Proceed only with controlled testing. Improve memory recall, context grounding, and benchmark coverage.\n"
    else:
        report += "Proceed with monitored pilot. Continue weekly benchmark review and executive reporting.\n"

    return report



def create_multi_agent_report(comparison_df, winner, prompt, evidence):
    report = "MindGuard AI Multi-Agent Evaluation Report\n\n"
    report += f"Winner: {winner}\n\n"
    report += f"Prompt:\n{prompt}\n\n"
    report += f"Trusted Evidence:\n{evidence}\n\n"
    report += "Scoreboard:\n"
    report += comparison_df.to_string(index=False)
    report += "\n\nRecommendation:\n"

    if comparison_df.empty:
        report += "No agent responses were provided.\n"
        return report

    best_score = int(comparison_df.iloc[0]["Overall Score"])
    best_risk = int(comparison_df.iloc[0]["Hallucination Risk"])

    if best_score >= 85 and best_risk < 35:
        report += f"{winner} is the strongest candidate for controlled production deployment.\n"
    elif best_score >= 70:
        report += f"{winner} is currently the strongest option, but more testing is recommended before deployment.\n"
    else:
        report += "No agent is ready for deployment based on this test.\n"

    return report


# -----------------------------
# DATABASE
# -----------------------------
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




def repair_existing_observation_scores():
    """
    Re-score old database rows using the latest scoring engine.
    This fixes old records like:
    Prompt: What is 2 plus 2?
    Response: 4
    which were previously saved as BAD before smart short-answer scoring existed.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        rows = cursor.execute(
            "SELECT id, prompt, response, score, status FROM observations"
        ).fetchall()

        for row_id, prompt, response, old_score, old_status in rows:
            new_score, new_status = quality_score(prompt, response)

            if int(old_score) != int(new_score) or str(old_status) != str(new_status):
                cursor.execute(
                    "UPDATE observations SET score = ?, status = ? WHERE id = ?",
                    (new_score, new_status, row_id)
                )

        conn.commit()
    finally:
        conn.close()


def delete_false_positive_short_answer_failures():
    """
    Deletes old BAD rows that are actually correct short factual answers.
    Useful if you want the old bad 2+2 test completely removed instead of only rescored.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        rows = cursor.execute(
            "SELECT id, prompt, response FROM observations"
        ).fetchall()

        deleted = 0

        for row_id, prompt, response in rows:
            if short_fact_correctness_boost(prompt, response):
                cursor.execute("DELETE FROM observations WHERE id = ?", (row_id,))
                deleted += 1

        conn.commit()
        return deleted
    finally:
        conn.close()


def clear_all_observations():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM observations")
        conn.commit()
    finally:
        conn.close()


# -----------------------------
# SCORING HELPERS
# -----------------------------
def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, int(round(value))))


def normalize_words(text):
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "your",
        "you", "are", "was", "were", "will", "can", "could", "should", "would",
        "have", "has", "had", "about", "what", "when", "where", "which", "who",
        "why", "how", "does", "did", "doing", "make", "made", "using", "use",
        "they", "them", "their", "there", "then", "than", "same", "also"
    }

    words = []
    for raw in str(text).lower().replace("\n", " ").split():
        cleaned = raw.strip(".,?!:;()[]{}\"'`")
        if len(cleaned) > 3 and cleaned not in stopwords:
            words.append(cleaned)

    return words



def is_short_fact_answer(prompt, response):
    prompt_lower = str(prompt).lower().strip()
    response_clean = str(response).strip().lower()

    short_fact_patterns = [
        "what is",
        "what's",
        "how many",
        "calculate",
        "capital of",
        "who is",
        "who was",
        "when is",
        "when was",
        "where is",
        "2 plus 2",
        "1 plus 1",
        "sum of",
        "result of",
    ]

    if any(pattern in prompt_lower for pattern in short_fact_patterns):
        if 1 <= len(response_clean) <= 80:
            return True

    arithmetic_match = re.search(r"(\d+)\s*(plus|\+|minus|-|times|\*|x|divided by|/)\s*(\d+)", prompt_lower)

    if arithmetic_match and 1 <= len(response_clean) <= 30:
        return True

    return False


def short_fact_correctness_boost(prompt, response):
    prompt_lower = str(prompt).lower().strip()
    response_clean = str(response).strip().lower()

    arithmetic_match = re.search(r"(\d+)\s*(plus|\+|minus|-|times|\*|x|divided by|/)\s*(\d+)", prompt_lower)

    if arithmetic_match:
        a = int(arithmetic_match.group(1))
        op = arithmetic_match.group(2)
        b = int(arithmetic_match.group(3))

        try:
            if op in ["plus", "+"]:
                expected = a + b
            elif op in ["minus", "-"]:
                expected = a - b
            elif op in ["times", "*", "x"]:
                expected = a * b
            elif op in ["divided by", "/"]:
                expected = a / b
            else:
                return 0

            if str(int(expected)) in response_clean or str(expected) in response_clean:
                return 90
        except Exception:
            return 0

    known_answers = {
        "capital of france": ["paris"],
        "capital of israel": ["jerusalem"],
        "color is the sky": ["blue"],
        "colour is the sky": ["blue"],
    }

    for key, accepted_answers in known_answers.items():
        if key in prompt_lower:
            if any(answer in response_clean for answer in accepted_answers):
                return 88

    return 0


def quality_score(prompt, response):
    prompt = str(prompt).strip()
    response = str(response).strip()

    correctness_boost = short_fact_correctness_boost(prompt, response)

    if correctness_boost:
        return correctness_boost, "GOOD"

    if len(response) < 10:
        if is_short_fact_answer(prompt, response):
            return 75, "WEAK"
        return 20, "BAD"

    score = 55

    if len(response) >= 40:
        score += 15
    elif is_short_fact_answer(prompt, response):
        score += 10

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

    if is_short_fact_answer(prompt, response):
        score = max(score, 75)

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

    correctness_boost = short_fact_correctness_boost(prompt, response)
    if correctness_boost:
        return max(90, correctness_boost)

    if not response:
        return 0

    score = 70

    if len(response) < 30:
        if is_short_fact_answer(prompt, response):
            score += 5
        else:
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

    if is_short_fact_answer(prompt, response):
        score = max(score, 75)

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


def detect_contradictions(evidence_text, claim_text):
    evidence_lower = str(evidence_text).lower()
    claim_lower = str(claim_text).lower()

    contradiction_rules = [
        {
            "category": "Nationality / Location",
            "values": ["australian", "canadian", "american", "british", "israeli", "portuguese", "french", "german", "spanish", "italian"]
        },
        {
            "category": "Country",
            "values": ["australia", "canada", "usa", "united states", "israel", "portugal", "france", "germany", "spain", "italy"]
        },
        {
            "category": "Preference / Language",
            "values": ["english", "hebrew", "arabic", "russian", "spanish", "french", "german"]
        },
        {
            "category": "Status",
            "values": ["active", "inactive", "enabled", "disabled", "approved", "rejected", "passed", "failed"]
        },
        {
            "category": "Boolean / Decision",
            "values": ["yes", "no", "true", "false", "allowed", "blocked", "safe", "unsafe"]
        }
    ]

    contradictions = []

    for rule in contradiction_rules:
        evidence_hits = [value for value in rule["values"] if value in evidence_lower]
        claim_hits = [value for value in rule["values"] if value in claim_lower]

        for evidence_value in evidence_hits:
            for claim_value in claim_hits:
                if evidence_value != claim_value:
                    contradictions.append({
                        "category": rule["category"],
                        "evidence_value": evidence_value,
                        "claim_value": claim_value,
                        "message": f"{rule['category']} conflict: evidence says '{evidence_value}', claim says '{claim_value}'."
                    })

    evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", evidence_lower))
    claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", claim_lower))

    if evidence_numbers and claim_numbers and evidence_numbers != claim_numbers:
        contradictions.append({
            "category": "Numeric Value",
            "evidence_value": ", ".join(sorted(evidence_numbers)),
            "claim_value": ", ".join(sorted(claim_numbers)),
            "message": f"Numeric conflict: evidence contains {', '.join(sorted(evidence_numbers))}, claim contains {', '.join(sorted(claim_numbers))}."
        })

    contradiction_count = len(contradictions)

    if contradiction_count >= 1:
        contradiction_risk = "HIGH"
        contradiction_score = 80
    else:
        contradiction_risk = "NONE"
        contradiction_score = 0

    return {
        "contradictions": contradictions,
        "contradiction_count": contradiction_count,
        "contradiction_risk": contradiction_risk,
        "contradiction_score": contradiction_score
    }


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


def score_single_agent_response(prompt, response, evidence=""):
    quality, status = quality_score(prompt, response)
    accuracy = estimate_accuracy_score(prompt, response)

    temp_df = pd.DataFrame([{
        "prompt": prompt,
        "response": response,
        "score": quality,
        "status": status
    }])

    context = estimate_context_retention_score(temp_df)
    repetition = 100

    if evidence.strip():
        risk = analyze_hallucination_risk(evidence, response)
        contradiction = detect_contradictions(evidence, response)
        hallucination_risk = max(risk["risk_score"], contradiction["contradiction_score"])
        contradictions = contradiction["contradiction_count"]
    else:
        hallucination_risk = clamp((100 - accuracy) * 0.5 + (100 - context) * 0.3)
        contradictions = 0

    memory_signals = estimate_memory_score(temp_df)

    overall = clamp(
        quality * 0.30 +
        accuracy * 0.25 +
        context * 0.15 +
        memory_signals * 0.10 +
        repetition * 0.10 +
        (100 - hallucination_risk) * 0.10 -
        contradictions * 10
    )

    if overall >= 85:
        verdict = "EXCELLENT"
    elif overall >= 70:
        verdict = "GOOD"
    elif overall >= 50:
        verdict = "WEAK"
    else:
        verdict = "RISKY"

    return {
        "overall": overall,
        "quality": quality,
        "accuracy": accuracy,
        "context": context,
        "memory": memory_signals,
        "hallucination_risk": hallucination_risk,
        "contradictions": contradictions,
        "status": status,
        "verdict": verdict
    }


def build_agent_comparison(prompt, evidence, responses):
    rows = []

    for agent_name, response in responses.items():
        if not str(response).strip():
            continue

        scores = score_single_agent_response(prompt, response, evidence)

        rows.append({
            "Agent": agent_name,
            "Overall Score": scores["overall"],
            "Quality": scores["quality"],
            "Accuracy": scores["accuracy"],
            "Context": scores["context"],
            "Memory": scores["memory"],
            "Hallucination Risk": scores["hallucination_risk"],
            "Contradictions": scores["contradictions"],
            "Verdict": scores["verdict"]
        })

    if not rows:
        return pd.DataFrame(), None

    comparison_df = pd.DataFrame(rows)
    comparison_df = comparison_df.sort_values("Overall Score", ascending=False)

    winner = comparison_df.iloc[0]["Agent"]

    return comparison_df, winner


def get_improvement_plan(quality, accuracy, context, memory, hallucination_risk, contradictions):
    recommendations = []

    if memory < 70:
        recommendations.append({
            "Area": "Memory",
            "Problem": "Low memory recall",
            "Recommended Fix": "Increase retrieval window, add memory validation, and test recall against expected facts.",
            "Expected Impact": "+15"
        })

    if context < 70:
        recommendations.append({
            "Area": "Context",
            "Problem": "Weak context retention",
            "Recommended Fix": "Pass more relevant conversation history and enforce prompt-response alignment checks.",
            "Expected Impact": "+10"
        })

    if hallucination_risk > 25:
        recommendations.append({
            "Area": "Hallucination Risk",
            "Problem": "Unsupported claims detected",
            "Recommended Fix": "Ground responses against trusted evidence before final output.",
            "Expected Impact": "+20"
        })

    if contradictions > 0:
        recommendations.append({
            "Area": "Contradictions",
            "Problem": "Output conflicts with trusted evidence",
            "Recommended Fix": "Add contradiction detection as a mandatory pre-release safety gate.",
            "Expected Impact": "+25"
        })

    if quality < 80:
        recommendations.append({
            "Area": "Quality",
            "Problem": "Response quality is below target",
            "Recommended Fix": "Improve output instructions, structure, completeness, and review weak responses.",
            "Expected Impact": "+12"
        })

    if accuracy < 80:
        recommendations.append({
            "Area": "Accuracy",
            "Problem": "Estimated answer relevance is below target",
            "Recommended Fix": "Improve retrieval, grounding, and prompt-response alignment scoring.",
            "Expected Impact": "+15"
        })

    if not recommendations:
        recommendations.append({
            "Area": "System",
            "Problem": "No major issue detected",
            "Recommended Fix": "Continue monitoring with larger real-world datasets before production rollout.",
            "Expected Impact": "+5"
        })

    return pd.DataFrame(recommendations)


def calculate_deployment_readiness(quality, accuracy, context, memory, hallucination_risk, contradictions):
    readiness = (
        quality * 0.22 +
        accuracy * 0.22 +
        context * 0.18 +
        memory * 0.16 +
        (100 - hallucination_risk) * 0.17 -
        contradictions * 7
    )

    readiness = max(0, min(100, round(readiness)))

    if readiness >= 85:
        status = "PRODUCTION READY"
    elif readiness >= 70:
        status = "NEEDS MORE TESTING"
    else:
        status = "NOT READY"

    return readiness, status


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


def demo_ai_response(prompt):
    return (
        "Demo AI response: MindGuard captured this prompt, generated a monitored response, "
        "calculated quality, accuracy, consistency, memory, context, repetition, and hallucination-risk signals, "
        "stored the interaction, and updated the agent operations dashboard. "
        "In production, this layer can monitor real AI models, internal agents, customer support bots, "
        "AI workflows, and enterprise LLM systems."
    )


# -----------------------------
# PDF GENERATION
# -----------------------------
def _pdf_safe(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_executive_pdf_report(analysis):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "MindGuardTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#075985"),
        spaceAfter=16,
    )

    heading_style = ParagraphStyle(
        "MindGuardHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=12,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "MindGuardBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
    )

    story = []

    story.append(Paragraph("MindGuard AI Executive Agent Report", title_style))
    story.append(Paragraph("AI Agent Monitoring, Risk Analysis, and Improvement Summary", body_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(_pdf_safe(analysis.get("executive_summary", "No summary available.")), body_style))
    story.append(Spacer(1, 10))

    scores = [
        ["Metric", "Score"],
        ["Agent Health", f"{analysis.get('health', 0)}/100"],
        ["Average Quality", str(analysis.get("avg_score", 0))],
        ["Accuracy", f"{analysis.get('accuracy', 0)}/100"],
        ["Consistency", f"{analysis.get('consistency', 0)}/100"],
        ["Memory", f"{analysis.get('memory', 0)}/100"],
        ["Context Retention", f"{analysis.get('context', 0)}/100"],
        ["Anti-Repetition", f"{analysis.get('repetition', 0)}/100"],
        ["Hallucination Risk", f"{analysis.get('hallucination_risk', 0)}/100"],
        ["Detected Issues", str(analysis.get("bad_count", 0))],
        ["Upgrade Readiness", str(analysis.get("upgrade_readiness", "UNKNOWN"))],
    ]

    table = Table(scores, colWidths=[8 * cm, 7 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0F2FE")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#075985")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(Paragraph("Current Scores", heading_style))
    story.append(table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Strengths", heading_style))
    for item in analysis.get("strengths", []):
        story.append(Paragraph("• " + _pdf_safe(item), body_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Weaknesses", heading_style))
    for item in analysis.get("weaknesses", []):
        story.append(Paragraph("• " + _pdf_safe(item), body_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Recommended Next Actions", heading_style))
    for item in analysis.get("recommendations", []):
        story.append(Paragraph("• " + _pdf_safe(item), body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_agent_comparison_pdf(comparison_df, winner, prompt, evidence):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "MindGuardComparisonTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#075985"),
        spaceAfter=16,
    )

    heading_style = ParagraphStyle(
        "MindGuardComparisonHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=12,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "MindGuardComparisonBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
    )

    story = []

    story.append(Paragraph("MindGuard AI Agent Comparison Report", title_style))
    story.append(Paragraph(f"Best Agent: <b>{_pdf_safe(winner)}</b>", body_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Shared Prompt", heading_style))
    story.append(Paragraph(_pdf_safe(prompt), body_style))

    story.append(Paragraph("Trusted Evidence / Expected Facts", heading_style))
    story.append(Paragraph(_pdf_safe(evidence) if evidence else "No trusted evidence provided.", body_style))
    story.append(Spacer(1, 10))

    columns = [
        "Agent", "Overall", "Quality", "Accuracy", "Context",
        "Memory", "Risk", "Contradictions", "Verdict"
    ]

    data = [columns]

    for _, row in comparison_df.iterrows():
        data.append([
            str(row.get("Agent", "")),
            str(row.get("Overall Score", "")),
            str(row.get("Quality", "")),
            str(row.get("Accuracy", "")),
            str(row.get("Context", "")),
            str(row.get("Memory", "")),
            str(row.get("Hallucination Risk", "")),
            str(row.get("Contradictions", "")),
            str(row.get("Verdict", "")),
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0F2FE")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#075985")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(Paragraph("Comparison Table", heading_style))
    story.append(table)
    story.append(Spacer(1, 12))

    best_score = int(comparison_df.iloc[0]["Overall Score"])

    if best_score >= 85:
        recommendation = f"{winner} is the strongest candidate for controlled deployment based on this test."
    elif best_score >= 70:
        recommendation = f"{winner} is currently the best option, but more testing is recommended before deployment."
    else:
        recommendation = "No agent is ready for deployment based on this comparison. Improve prompts, memory, and factual grounding."

    story.append(Paragraph("Recommendation", heading_style))
    story.append(Paragraph(_pdf_safe(recommendation), body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# -----------------------------
# APP START
# -----------------------------
init_db()
init_workspace_tables(DB_FILE)
repair_existing_observation_scores()

st.set_page_config(
    page_title="MindGuard AI",
    page_icon="logo.png",
    layout="wide"
)

# EARLY DATA LOAD FOR COMMAND CENTER
df = load_data()
analysis = calculate_agent_analysis(df)

# AUTO BACKUP AFTER DATA LOAD
try:
    if len(df) > 0:
        backup_observations_to_csv(df)
except Exception:
    pass

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    --bg: #F7FAFF;
    --surface: #FFFFFF;
    --surface-soft: #F2F7FF;
    --border: #D7E4F5;
    --text: #0B1220;
    --muted: #5D6B82;
    --brand-blue: #1478FF;
    --brand-cyan: #00C2D8;
    --brand-navy: #071527;
    --good: #16A34A;
    --weak: #D97706;
    --bad: #DC2626;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background:
        radial-gradient(circle at 8% 0%, rgba(20,120,255,0.12), transparent 28%),
        radial-gradient(circle at 92% 8%, rgba(0,194,216,0.14), transparent 30%),
        linear-gradient(135deg, #F7FAFF 0%, #FFFFFF 46%, #EEF6FF 100%);
    color: var(--text);
}

.block-container {
    padding-top: 1.3rem;
    padding-bottom: 4rem;
    max-width: 1480px;
}

h1, h2, h3, h4 {
    color: var(--text) !important;
    letter-spacing: -0.035em;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    color: #26364F !important;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #F3F8FF 100%);
    border-right: 1px solid var(--border);
    box-shadow: 10px 0 30px rgba(20,120,255,0.06);
}

section[data-testid="stSidebar"] * {
    color: var(--text) !important;
}

section[data-testid="stSidebar"] img {
    filter: drop-shadow(0 14px 24px rgba(20,120,255,0.16));
    margin-bottom: 10px;
}

section[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: 11px 13px;
    border-radius: 14px;
    margin-bottom: 5px;
    transition: all 0.18s ease;
    border: 1px solid transparent;
    font-weight: 700;
}

section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: #E9F3FF;
    border: 1px solid #C8DEFF;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #FFFFFF 0%, #F8FBFF 100%);
    border-radius: 24px;
    padding: 22px;
    box-shadow: 0 20px 48px rgba(7, 21, 39, 0.08);
    border: 1px solid var(--border);
}

[data-testid="stMetricLabel"] {
    color: var(--muted) !important;
    font-weight: 800;
}

[data-testid="stMetricValue"] {
    color: var(--brand-navy) !important;
    font-weight: 900;
    letter-spacing: -0.045em;
}

.stButton button, .stDownloadButton button {
    background: linear-gradient(135deg, var(--brand-blue) 0%, var(--brand-cyan) 100%);
    color: white !important;
    border-radius: 14px;
    border: 0;
    font-weight: 850;
    padding: 0.75rem 1.15rem;
    box-shadow: 0 14px 30px rgba(20,120,255,0.24);
    transition: all 0.18s ease;
}

.stButton button:hover, .stDownloadButton button:hover {
    transform: translateY(-1px);
    box-shadow: 0 20px 42px rgba(20,120,255,0.30);
    color: white !important;
}

textarea, input {
    background: #FFFFFF !important;
    color: #0B1220 !important;
    border: 1px solid #C8D8EE !important;
    border-radius: 16px !important;
    box-shadow: 0 8px 22px rgba(7,21,39,0.045);
}

textarea::placeholder, input::placeholder {
    color: #8797AF !important;
}

[data-testid="stTextArea"] label,
[data-testid="stTextInput"] label {
    color: #0B1220 !important;
    font-weight: 850;
}

[data-testid="stDataFrame"] {
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid var(--border);
    background: white;
    box-shadow: 0 15px 38px rgba(7,21,39,0.07);
}

.stAlert {
    border-radius: 18px;
    border: 1px solid rgba(20,120,255,0.10);
    box-shadow: 0 12px 28px rgba(7,21,39,0.055);
}

hr {
    border-color: #DDE8F6 !important;
}

code {
    background: #EEF5FF !important;
    color: #13213A !important;
    border-radius: 12px !important;
}

.hero-card {
    position: relative;
    overflow: hidden;
    background:
        linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,248,255,0.95));
    border: 1px solid #D4E4F8;
    border-radius: 34px;
    padding: 46px;
    margin-bottom: 28px;
    box-shadow: 0 30px 80px rgba(20,120,255,0.13);
}

.hero-card:before {
    content: "";
    position: absolute;
    width: 560px;
    height: 560px;
    right: -220px;
    top: -250px;
    background: radial-gradient(circle, rgba(20,120,255,0.16), transparent 66%);
}

.hero-card:after {
    content: "";
    position: absolute;
    width: 420px;
    height: 420px;
    left: -190px;
    bottom: -210px;
    background: radial-gradient(circle, rgba(0,194,216,0.15), transparent 64%);
}

.hero-inner {
    position: relative;
    z-index: 2;
}

.hero-title {
    font-size: clamp(2.7rem, 5vw, 5.4rem);
    font-weight: 900;
    line-height: 0.95;
    color: #071527;
    margin-bottom: 12px;
    letter-spacing: -0.075em;
}

.hero-gradient {
    background: linear-gradient(135deg, #071527 0%, #1478FF 48%, #00C2D8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero-subtitle {
    font-size: 1.22rem;
    color: #40516D;
    max-width: 980px;
    line-height: 1.7;
    font-weight: 550;
}

.badge {
    background: #E8F4FF;
    color: #0B55D8;
    padding: 10px 16px;
    border-radius: 999px;
    font-weight: 850;
    display: inline-flex;
    align-items: center;
    margin-top: 18px;
    border: 1px solid #CBE2FF;
}

.card {
    background: linear-gradient(145deg, #FFFFFF 0%, #F7FBFF 100%);
    border: 1px solid var(--border);
    border-radius: 26px;
    padding: 28px;
    box-shadow: 0 18px 45px rgba(7,21,39,0.07);
    margin-bottom: 22px;
}

.command-grid-card {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 24px;
    min-height: 160px;
    box-shadow: 0 14px 34px rgba(7,21,39,0.06);
}

.small-muted {
    color: #687895;
    font-size: 0.95rem;
}

div[data-testid="stToolbar"] {
    opacity: 0.55;
}

/* Public/Admin polish */
section[data-testid="stSidebar"] .stRadio > label {
    font-weight: 900 !important;
}


/* Metric readability fix */
[data-testid="stMetric"] {
    min-height: 132px !important;
    overflow: visible !important;
}

[data-testid="stMetricLabel"] {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    font-size: 0.95rem !important;
    line-height: 1.25 !important;
}

[data-testid="stMetricValue"] {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    font-size: clamp(1.65rem, 2.4vw, 2.55rem) !important;
    line-height: 1.05 !important;
    letter-spacing: -0.04em !important;
    word-break: break-word !important;
}

[data-testid="stMetricDelta"] {
    white-space: normal !important;
    font-size: 0.9rem !important;
}

.metric-text-card {
    background: linear-gradient(145deg, #FFFFFF 0%, #F8FBFF 100%);
    border-radius: 24px;
    padding: 22px;
    box-shadow: 0 20px 48px rgba(7, 21, 39, 0.08);
    border: 1px solid #D7E4F5;
    min-height: 132px;
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
    font-size: clamp(1.35rem, 1.7vw, 2rem);
    line-height: 1.12;
    letter-spacing: -0.04em;
    word-break: normal;
}

</style>
""", unsafe_allow_html=True)

try:
    st.image("logo.png", width=280)
except Exception:
    st.title("MindGuard AI")

st.markdown("""
<div class="hero-card">
    <div class="hero-inner">
        <span class="badge">AI Agent Observability Platform</span>
        <div class="hero-title"><span class="hero-gradient">MindGuard AI</span></div>
        <div class="hero-subtitle">
            Monitor, benchmark, diagnose, and improve AI agents before weak responses, memory failures,
            hallucinations, or contradictions reach real users.
        </div>
        <span class="badge">Live MVP • AgentOps • Risk Intelligence • Executive Reporting</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="card">
<h2 style="color:#0F172A;">Getting Started</h2>
<p style="font-size:17px; color:#334155;">
Use MindGuard as an AI AgentOps command center: test responses, monitor quality, detect weak outputs, analyze memory, compare agents, benchmark performance, and generate executive reports.
</p>
<ol style="font-size:16px; color:#334155; line-height:1.8;">
<li>Run the demo AI to create a monitored response.</li>
<li>Paste real prompts and AI responses manually.</li>
<li>Use Memory Recall Lab to test if an agent remembers facts.</li>
<li>Use Hallucination Risk + Contradiction Lab to detect factual conflicts.</li>
<li>Compare GPT, Claude, Gemini, and custom agents side by side.</li>
<li>Run automatic benchmarks from uploaded CSV datasets.</li>
<li>Use Root Cause Analysis to identify exactly why BAD or WEAK responses failed.</li>
<li>Use Agent Improvement Engine to generate a fix plan.</li>
<li>Download TXT, HTML, and PDF reports.</li>
</ol>
</div>
""", unsafe_allow_html=True)

# -----------------------------
# SIDEBAR NAVIGATION
# -----------------------------
try:
    st.sidebar.image("logo.png", width=210)
except Exception:
    st.sidebar.title("MindGuard AI")
st.sidebar.caption("AI Agent Command Center")

st.sidebar.divider()
app_mode = st.sidebar.radio(
    "Mode",
    ["Public Demo", "Admin"],
    horizontal=False
)


if app_mode == "Public Demo":
    page = st.sidebar.radio(
        "Navigate",
        [
            "Landing",
            "Run Tests",
            "Multi-Agent Mode",
            "Red Team Security Lab",
            "Public Demo Results",
            "Executive Dashboard",
            "Root Cause Analysis",
            "Executive Report"
        ]
    )
else:
    page = st.sidebar.radio(
        "Navigate",
        [
            "Landing",
            "Command Center",
            "Run Tests",
            "Multi-Agent Mode",
            "Red Team Security Lab",
            "Public Demo Results",
            "Executive Dashboard",
            "Root Cause Analysis",
            "Agent Intelligence",
            "Agent Comparison Lab",
            "Auto Benchmark",
            "Memory Recall Lab",
            "Hallucination + Contradiction Lab",
            "Executive Report",
            "Agent Improvement Engine",
            "Agent Memory Trainer",
            "Dataset Upload",
            "Workspaces",
            "Persistent Storage",
            "Storage Backup"
        ]
    )

st.sidebar.divider()
st.sidebar.caption("Recommended flow:")
st.sidebar.write("1. Landing")
st.sidebar.write("2. Run Tests")
st.sidebar.write("3. Root Cause Analysis")
st.sidebar.write("4. Executive Report")

if app_mode == "Public Demo":
    st.sidebar.success("PUBLIC DEMO MODE ACTIVE")
else:
    st.sidebar.warning("ADMIN MODE ACTIVE")




# -----------------------------
# LANDING EXPERIENCE
# -----------------------------
if page == "Landing":
    try:
        st.image("logo.png", width=260)
    except Exception:
        pass

    st.markdown("""
    <div class="hero-card">
        <div class="hero-inner">
            <span class="badge">AI Agent Observability Platform</span>
            <div class="hero-title"><span class="hero-gradient">Stop AI failures before users see them.</span></div>
            <div class="hero-subtitle">
                MindGuard AI helps teams monitor AI responses, detect weak outputs, find hallucinations,
                identify contradictions, benchmark agents, analyze memory failures, and generate executive reports.
            </div>
            <span class="badge">Built for AI startups • support teams • CTOs • enterprise AI operations</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### What MindGuard does")

    f1, f2, f3 = st.columns(3)

    with f1:
        st.markdown("""
        <div class="command-grid-card">
            <h3>Monitor AI Quality</h3>
            <p>Track prompts, responses, scores, weak outputs, and quality trends in one dashboard.</p>
        </div>
        """, unsafe_allow_html=True)

    with f2:
        st.markdown("""
        <div class="command-grid-card">
            <h3>Detect Risk</h3>
            <p>Find hallucinations, contradictions, memory failures, and prompt-response alignment issues.</p>
        </div>
        """, unsafe_allow_html=True)

    with f3:
        st.markdown("""
        <div class="command-grid-card">
            <h3>Improve Agents</h3>
            <p>Turn failures into recommendations, memory rules, benchmark results, and deployment-readiness signals.</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    st.markdown("### Live Platform Snapshot")

    l1, l2, l3, l4 = st.columns(4)

    with l1:
        st.metric("AI Interactions", len(df))

    with l2:
        st.metric("Average Quality", analysis["avg_score"])

    with l3:
        st.metric("Detected Issues", analysis["bad_count"])

    with l4:
        st.metric("Upgrade Readiness", analysis["upgrade_readiness"])

    st.divider()

    st.markdown("### Why teams need this")

    st.markdown("""
    <div class="card">
        <p>
        AI agents are moving into support, sales, operations, coding, finance, and internal workflows.
        The problem is simple: when an agent fails, most teams only find out after a user complains.
        MindGuard gives teams a monitoring layer that checks response quality, memory usage, hallucination risk,
        contradiction risk, benchmark performance, root causes, and executive reporting before deployment.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Recommended next action")

    if analysis["bad_count"] > 0:
        st.error("Deployment is blocked by critical response failures. Open Root Cause Analysis next.")
    elif analysis["avg_score"] < 80:
        st.warning("Quality is improving, but more testing is recommended. Open Run Tests next.")
    else:
        st.success("System looks healthy. Run Auto Benchmark or download an Executive Report.")

    st.info("Use the left menu to open Run Tests, Root Cause Analysis, Benchmarking, Reports, or Admin tools.")

    st.divider()

    st.markdown("### Public Demo Experience")

    st.markdown("""
    <div class="card">
        <p>
        Public Demo Mode keeps the app simple for testers, investors, and potential customers.
        It shows only the core flow: run a live test, review a clean result page, analyze failures, and export a report.
        Admin Mode unlocks benchmarking, datasets, memory training, storage backup, and deeper operations tools.
        </p>
    </div>
    """, unsafe_allow_html=True)


# -----------------------------
# COMMAND CENTER
# -----------------------------
if page == "Command Center":
    brand_col, title_col = st.columns([1, 6])
    with brand_col:
        try:
            st.image("logo.png", width=92)
        except Exception:
            pass
    with title_col:
        st.subheader("Command Center")

    st.write(
        "A cleaner control room for MindGuard AI. Use this page to understand the current state, "
        "then jump into the right tool from the sidebar."
    )

    cc1, cc2, cc3, cc4 = st.columns(4)

    with cc1:
        st.metric("Total AI Interactions", len(df))

    with cc2:
        st.metric("Average Quality", analysis["avg_score"])

    with cc3:
        st.metric("Detected Issues", analysis["bad_count"])

    with cc4:
        st.metric("Upgrade Readiness", analysis["upgrade_readiness"])

    st.divider()

    left, right = st.columns(2)

    with left:
        st.markdown("### Current Status")

        if analysis["bad_count"] > 0:
            st.error(f"Deployment Blocker: {analysis['bad_count']} critical response(s) detected.")
        elif analysis["avg_score"] >= 80:
            st.success("System looks healthy. Continue benchmark and monitoring.")
        else:
            st.warning("System is usable, but more testing and improvement are recommended.")

        st.markdown("### Recommended Next Action")

        if analysis["bad_count"] > 0:
            st.info("Open Root Cause Analysis and fix the critical response before deployment.")
        elif analysis["memory"] < 70:
            st.info("Open Agent Memory Trainer and improve memory recall rules.")
        elif analysis["hallucination_risk"] > 30:
            st.info("Open Hallucination + Contradiction Lab and improve grounding.")
        else:
            st.info("Run Auto Benchmark and export an Executive Report.")

    with right:
        st.markdown("### Quick Health Signals")
        st.metric("Memory", f"{analysis['memory']}/100")
        st.metric("Context", f"{analysis['context']}/100")
        st.metric("Hallucination Risk", f"{analysis['hallucination_risk']}/100")
        st.metric("Anti-Repetition", f"{analysis['repetition']}/100")

    st.divider()

    st.markdown("### Product Areas")

    a, b, c = st.columns(3)

    with a:
        st.markdown("#### Testing")
        st.write("Run text or voice tests, save observations, and evaluate responses.")

    with b:
        st.markdown("#### Risk")
        st.write("Analyze root causes, memory issues, hallucinations, and contradictions.")

    with c:
        st.markdown("#### Reporting")
        st.write("Export executive reports and backup observations before updates.")


# -----------------------------
# RUN TESTS
# -----------------------------
# SAFE DEFAULTS FOR RUN TEST VOICE TRANSCRIPTS
demo_voice_transcript = ""
manual_voice_prompt = ""
manual_voice_response = ""

if page == "Run Tests":
    if app_mode == "Public Demo":
        st.info("Public Demo: run a test, save an observation, then review Root Cause Analysis and Executive Report.")
    st.subheader("Run Demo AI + Monitor Response")

    st.info("Use the microphone button next to the prompt field to speak directly into the prompt line.")

    user_prompt = mic_text_area(
        "Prompt",
        key="demo_ai_prompt_input",
        placeholder="Example: Explain artificial intelligence in one sentence.",
        height=130
    )

    if st.button("Run Demo AI + Save Observation", key="run_demo_ai_button"):
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

    st.caption("Speak directly into either field using the microphone button beside it.")

    prompt = mic_text_area(
        "Original Prompt",
        key="manual_observation_prompt_input",
        placeholder="Paste or speak the prompt here.",
        height=130
    )

    response = mic_text_area(
        "AI Response",
        key="manual_observation_response_input",
        placeholder="Paste or speak the AI response here.",
        height=160
    )

    if st.button("Save Manual Observation", key="save_manual_observation_button"):
        if prompt.strip() == "" or response.strip() == "":
            st.warning("Prompt and response cannot be empty.")
        else:
            save_observation(prompt, response)
            st.success("Manual observation saved.")

    st.divider()

    st.subheader("General Voice Scratchpad")

    st.write(
        "Optional scratchpad for extra voice notes, lyrics, prompts, or tester feedback. "
        "This does not save an observation unless you paste/speak it into the fields above."
    )

    try:
        voice_audio = st.audio_input("Record voice note", key="run_tests_voice_capture")

        if voice_audio is not None:
            st.audio(voice_audio)
            st.success("Voice recording captured.")

            st.download_button(
                label="Download voice recording",
                data=voice_audio.getvalue(),
                file_name="mindguard_voice_prompt.wav",
                mime="audio/wav"
            )
    except Exception as e:
        st.warning("Voice input is not available in this environment.")
        st.code(str(e))


# -----------------------------
# AGENT INTELLIGENCE
# -----------------------------
if page == "Agent Intelligence":
    st.subheader("Agent Intelligence Analysis")

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


# -----------------------------
# MEMORY RECALL
# -----------------------------
if page == "Memory Recall Lab":
    st.subheader("Memory Recall Lab")

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


# -----------------------------
# HALLUCINATION + CONTRADICTION
# -----------------------------
if page == "Hallucination + Contradiction Lab":
    st.subheader("Hallucination Risk + Contradiction Detection Lab")

    st.write(
        "Paste trusted evidence and then paste the AI claim. "
        "MindGuard will estimate hallucination risk and detect direct contradictions."
    )

    with st.form("hallucination_form"):
        evidence_text = st.text_area(
            "Trusted Evidence",
            value="User is Australian\nUser manages Full Deck Artists",
            help="Paste facts that are known to be true."
        )

        claim_text = st.text_area(
            "AI Claim / Agent Response",
            value="User is Canadian and manages Full Deck Artists.",
            help="Paste the AI claim or agent response you want to verify."
        )

        run_risk = st.form_submit_button("Analyze Risk + Contradictions")

    if run_risk:
        if not evidence_text.strip() or not claim_text.strip():
            st.error("Please enter both Trusted Evidence and AI Claim before running the analysis.")
            st.stop()

        risk = analyze_hallucination_risk(evidence_text, claim_text)
        contradiction = detect_contradictions(evidence_text, claim_text)

        final_risk_score = max(risk["risk_score"], contradiction["contradiction_score"])

        if contradiction["contradiction_count"] > 0:
            final_risk_level = "HIGH"
        elif final_risk_score >= 70:
            final_risk_level = "HIGH"
        elif final_risk_score >= 40:
            final_risk_level = "MEDIUM"
        else:
            final_risk_level = "LOW"

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Final Risk Score", f"{final_risk_score}/100")

        with col2:
            st.metric("Risk Level", final_risk_level)

        with col3:
            st.metric("Contradictions Found", contradiction["contradiction_count"])

        if final_risk_level == "HIGH":
            st.error("High risk detected. The AI claim may contradict trusted evidence or contain unsupported information.")
        elif final_risk_level == "MEDIUM":
            st.warning("Medium risk detected. The claim contains unsupported terms or weak evidence alignment.")
        else:
            st.success("Low risk detected. No strong contradiction found.")

        st.divider()

        st.markdown("### Contradiction Detection")

        if contradiction["contradictions"]:
            for item in contradiction["contradictions"]:
                st.error(f"⚠️ {item['message']}")
        else:
            st.success("No direct contradictions detected.")

        st.divider()

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


# -----------------------------
# AGENT COMPARISON
# -----------------------------
if page == "Agent Comparison Lab":
    st.subheader("Agent Comparison Lab")

    st.write(
        "Compare multiple AI agents or model responses side by side. "
        "Paste the same prompt, optional trusted evidence, and responses from GPT, Claude, Gemini, or your custom agent."
    )

    with st.form("agent_comparison_form"):
        comparison_prompt = st.text_area(
            "Shared Prompt",
            value="A customer says they were charged twice for the same subscription. Write a professional support response.",
            help="Use the same prompt for every agent response."
        )

        comparison_evidence = st.text_area(
            "Trusted Evidence / Expected Facts (Optional)",
            value="Customer was charged twice.\nRefund is being reviewed.",
            help="Optional. Add trusted facts so MindGuard can check hallucination and contradiction risk."
        )

        gpt_response = st.text_area(
            "GPT Response",
            value="We can confirm a refund is being reviewed because you were charged twice."
        )

        claude_response = st.text_area(
            "Claude Response",
            value="We can confirm a refund is being reviewed because you were charged twice."
        )

        gemini_response = st.text_area(
            "Gemini Response",
            value="We can confirm a refund is being reviewed because you were charged twice."
        )

        custom_response = st.text_area(
            "Custom Agent Response",
            value="AI monitoring is useful because it checks outputs and helps businesses know if the agent is working properly."
        )

        run_comparison = st.form_submit_button("Compare Agents")

    if run_comparison:
        responses = {
            "GPT": gpt_response,
            "Claude": claude_response,
            "Gemini": gemini_response,
            "Custom Agent": custom_response
        }

        comparison_df, winner = build_agent_comparison(
            comparison_prompt,
            comparison_evidence,
            responses
        )

        if comparison_df.empty:
            st.error("Please enter at least one agent response.")
        else:
            st.success(f"🏆 Best Agent: {winner}")

            st.dataframe(comparison_df, width="stretch")

            st.divider()

            st.markdown("### Score Breakdown")

            chart_df = comparison_df.set_index("Agent")[[
                "Overall Score",
                "Quality",
                "Accuracy",
                "Context",
                "Memory"
            ]]

            st.bar_chart(chart_df)

            st.divider()

            st.markdown("### Risk View")

            risk_df = comparison_df.set_index("Agent")[[
                "Hallucination Risk",
                "Contradictions"
            ]]

            st.bar_chart(risk_df)

            st.divider()

            st.markdown("### Recommendation")

            best_row = comparison_df.iloc[0]

            if best_row["Overall Score"] >= 85:
                st.success(
                    f"{winner} is the strongest candidate for controlled deployment based on this test."
                )
            elif best_row["Overall Score"] >= 70:
                st.warning(
                    f"{winner} is currently the best option, but more testing is recommended before deployment."
                )
            else:
                st.error(
                    "No agent is ready for deployment based on this comparison. Improve prompts, memory, and factual grounding."
                )

            report_text = "MindGuard AI Agent Comparison Report\n\n"
            report_text += f"Prompt:\n{comparison_prompt}\n\n"
            report_text += f"Trusted Evidence:\n{comparison_evidence}\n\n"
            report_text += f"Best Agent: {winner}\n\n"
            report_text += comparison_df.to_string(index=False)

            st.download_button(
                label="Download Agent Comparison Report TXT",
                data=report_text,
                file_name="mindguard_agent_comparison_report.txt",
                mime="text/plain"
            )

            comparison_pdf = generate_agent_comparison_pdf(
                comparison_df,
                winner,
                comparison_prompt,
                comparison_evidence
            )

            st.download_button(
                label="Download Agent Comparison PDF",
                data=comparison_pdf,
                file_name="mindguard_agent_comparison_report.pdf",
                mime="application/pdf"
            )



# -----------------------------
# AUTO BENCHMARK
# -----------------------------
if page == "Auto Benchmark":
    st.subheader("Auto Benchmark Engine")

    st.write(
        "Upload a benchmark CSV and paste one agent response pattern. "
        "MindGuard will score every benchmark row and produce a readiness summary."
    )

    st.info(
        "CSV format required: category, prompt, expected_facts. "
        "Use the benchmark datasets provided with this build."
    )

    benchmark_file = st.file_uploader(
        "Upload Benchmark CSV",
        type=["csv"],
        key="benchmark_upload"
    )

    response_mode = st.radio(
        "Response Mode",
        ["Use one generic response for all prompts", "Use benchmark prompts as responses for testing"],
        horizontal=True
    )

    generic_response = st.text_area(
        "Generic Agent Response",
        value=(
            "We will review the issue carefully, use the available evidence, avoid unsupported claims, "
            "and provide a clear, professional, and helpful response."
        ),
        help="Used when testing one agent behavior across many benchmark prompts."
    )

    if benchmark_file is not None:
        try:
            benchmark_df = load_benchmark_csv(benchmark_file)

            st.markdown("### Uploaded Benchmark")
            st.dataframe(benchmark_df, width="stretch")

            if st.button("Run Auto Benchmark"):
                results = []

                for _, row in benchmark_df.iterrows():
                    prompt_value = str(row["prompt"])
                    evidence_value = str(row["expected_facts"])

                    if response_mode == "Use benchmark prompts as responses for testing":
                        response_value = prompt_value
                    else:
                        response_value = generic_response

                    scores = score_single_agent_response(
                        prompt_value,
                        response_value,
                        evidence_value
                    )

                    results.append({
                        "Category": row["category"],
                        "Prompt": prompt_value,
                        "Expected Facts": evidence_value,
                        "Response": response_value,
                        "Overall Score": scores["overall"],
                        "Quality": scores["quality"],
                        "Accuracy": scores["accuracy"],
                        "Context": scores["context"],
                        "Memory": scores["memory"],
                        "Hallucination Risk": scores["hallucination_risk"],
                        "Contradictions": scores["contradictions"],
                        "Verdict": scores["verdict"]
                    })

                results_df = pd.DataFrame(results)
                summary = create_benchmark_summary(results_df)

                st.success("Benchmark completed.")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Average Score", summary["average_score"])

                with col2:
                    st.metric("Average Risk", summary["average_risk"])

                with col3:
                    st.metric("Failed Tests", summary["failed_tests"])

                with col4:
                    st.metric("Readiness", summary["readiness"])

                st.divider()

                st.markdown("### Benchmark Results")
                st.dataframe(results_df, width="stretch")

                st.divider()

                st.markdown("### Score Trend")
                st.bar_chart(results_df.set_index("Category")[["Overall Score", "Quality", "Accuracy", "Context", "Memory"]])

                st.divider()

                st.markdown("### Risk Trend")
                st.bar_chart(results_df.set_index("Category")[["Hallucination Risk", "Contradictions"]])

                benchmark_report = "MindGuard AI Auto Benchmark Report\n\n"
                benchmark_report += f"Total Tests: {summary['total_tests']}\n"
                benchmark_report += f"Average Score: {summary['average_score']}\n"
                benchmark_report += f"Average Quality: {summary['average_quality']}\n"
                benchmark_report += f"Average Accuracy: {summary['average_accuracy']}\n"
                benchmark_report += f"Average Context: {summary['average_context']}\n"
                benchmark_report += f"Average Memory: {summary['average_memory']}\n"
                benchmark_report += f"Average Hallucination Risk: {summary['average_risk']}\n"
                benchmark_report += f"Failed Tests: {summary['failed_tests']}\n"
                benchmark_report += f"Readiness: {summary['readiness']}\n\n"
                benchmark_report += results_df.to_string(index=False)

                st.download_button(
                    label="Download Benchmark Report TXT",
                    data=benchmark_report,
                    file_name="mindguard_auto_benchmark_report.txt",
                    mime="text/plain"
                )

                st.download_button(
                    label="Download Benchmark Results CSV",
                    data=results_df.to_csv(index=False),
                    file_name="mindguard_auto_benchmark_results.csv",
                    mime="text/csv"
                )

                st.divider()

                st.markdown("### Benchmark Failure Analyzer")

                failure_summary_df = analyze_benchmark_failures(results_df)
                failed_prompt_details_df = create_failed_prompt_details(results_df)

                st.markdown("#### Failure Summary")
                st.dataframe(failure_summary_df, width="stretch")

                st.markdown("#### Failed Prompt Details")
                st.dataframe(failed_prompt_details_df, width="stretch")

                failure_report = create_failure_report_text(
                    failure_summary_df,
                    failed_prompt_details_df
                )

                st.download_button(
                    label="Download Failure Analysis Report TXT",
                    data=failure_report,
                    file_name="mindguard_benchmark_failure_analysis.txt",
                    mime="text/plain"
                )

        except Exception as e:
            st.error("Benchmark failed.")
            st.code(str(e))





# -----------------------------
# EXECUTIVE DASHBOARD 2.0
# -----------------------------
if page == "Executive Dashboard":
    st.subheader("Executive Dashboard 2.0")

    readiness_score = calculate_deployment_readiness_score(df, analysis)
    readiness_label = get_deployment_label(readiness_score)
    top_risks = build_top_risks(df, analysis)

    st.write(
        "A board-level view of AI health, deployment readiness, operational risk, and recommended next action."
    )

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        st.metric("Total Tests", len(df))

    with k2:
        healthy = len(df[df["status"].astype(str) == "GOOD"]) if len(df) > 0 else 0
        st.metric("Healthy", healthy)

    with k3:
        weak = len(df[df["status"].astype(str) == "WEAK"]) if len(df) > 0 else 0
        st.metric("Weak", weak)

    with k4:
        bad = len(df[df["status"].astype(str) == "BAD"]) if len(df) > 0 else 0
        st.metric("Critical", bad)

    with k5:
        text_metric_card("Readiness", readiness_label)

    st.divider()

    left, right = st.columns([1, 1])

    with left:
        st.markdown("### Deployment Readiness Score")
        st.markdown(
            f"""
            <div class="metric-text-card" style="min-height:220px;">
                <div class="metric-text-label">Production Readiness</div>
                <div class="metric-text-value" style="font-size:4.2rem;">{readiness_score}/100</div>
                <div class="metric-text-label" style="margin-top:18px;">{readiness_label}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with right:
        st.markdown("### Top 5 Risks")
        risk_html = "<div class='card'><ol>"
        for risk in top_risks:
            risk_html += f"<li>{risk}</li>"
        risk_html += "</ol></div>"
        st.markdown(risk_html, unsafe_allow_html=True)

    st.divider()

    st.markdown("### AI Health Timeline")

    if len(df) > 0:
        timeline_df = df.sort_values("id").copy()
        timeline_df["Average Score"] = timeline_df["score"].rolling(window=3, min_periods=1).mean()
        st.line_chart(timeline_df.set_index("id")[["score", "Average Score"]])
    else:
        st.info("No observations available yet.")

    st.divider()

    st.markdown("### Executive Summary")

    if readiness_score < 70:
        st.error("Deployment should remain blocked until critical quality or grounding issues are fixed.")
    elif readiness_score < 85:
        st.warning("Controlled testing is recommended before deployment.")
    else:
        st.success("The system is ready for a monitored pilot.")

    board_report = create_board_report(df, analysis)

    st.code(board_report)

    st.download_button(
        label="Download Board Report TXT",
        data=board_report,
        file_name="mindguard_board_report.txt",
        mime="text/plain"
    )



# -----------------------------
# MULTI-AGENT MODE
# -----------------------------
if page == "Multi-Agent Mode":
    st.subheader("Multi-Agent Mode")

    st.write(
        "Compare GPT, Claude, Gemini, and a custom/internal agent in one evaluation flow. "
        "Use the same prompt and trusted evidence for every response."
    )

    with st.form("multi_agent_mode_form"):
        multi_prompt = st.text_area(
            "Prompt",
            value="A customer says they were charged twice for the same subscription. Write a professional support response.",
            height=120
        )

        multi_evidence = st.text_area(
            "Trusted Evidence / Expected Facts",
            value="Customer was charged twice.\nBilling issue should be reviewed.\nRefund may be required if duplicate charge is confirmed.",
            height=120
        )

        c1, c2 = st.columns(2)

        with c1:
            multi_gpt = st.text_area(
                "GPT Response",
                value="I understand your concern. I’ll review the billing record, confirm whether a duplicate charge occurred, and if verified, start the refund process or escalate it to billing.",
                height=180
            )

            multi_gemini = st.text_area(
                "Gemini Response",
                value="Thanks for reporting this. We will check your subscription billing history and investigate whether a duplicate charge was made.",
                height=180
            )

        with c2:
            multi_claude = st.text_area(
                "Claude Response",
                value="I’m sorry for the inconvenience. I’ll verify the account charges, confirm if the same subscription was billed twice, and provide the next steps for refund review.",
                height=180
            )

            multi_custom = st.text_area(
                "Custom/Internal Agent Response",
                value="We will review your account and get back to you.",
                height=180
            )

        run_multi_agent = st.form_submit_button("Run Multi-Agent Evaluation")

    if run_multi_agent:
        responses = {
            "GPT": multi_gpt,
            "Claude": multi_claude,
            "Gemini": multi_gemini,
            "Custom/Internal Agent": multi_custom
        }

        comparison_df, winner = build_agent_comparison(
            multi_prompt,
            multi_evidence,
            responses
        )

        if comparison_df.empty:
            st.error("Please enter at least one agent response.")
        else:
            st.success(f"Best Agent: {winner}")

            top_score = int(comparison_df.iloc[0]["Overall Score"])
            top_risk = int(comparison_df.iloc[0]["Hallucination Risk"])
            weakest_agent = comparison_df.iloc[-1]["Agent"]
            weakest_score = int(comparison_df.iloc[-1]["Overall Score"])

            m1, m2, m3, m4 = st.columns(4)

            with m1:
                text_metric_card("Winner", winner)

            with m2:
                st.metric("Winning Score", top_score)

            with m3:
                st.metric("Winning Risk", top_risk)

            with m4:
                text_metric_card("Weakest Agent", f"{weakest_agent} ({weakest_score})")

            st.divider()

            st.markdown("### Scoreboard")
            st.dataframe(comparison_df, width="stretch")

            st.divider()

            st.markdown("### Score Comparison")
            score_chart = comparison_df.set_index("Agent")[[
                "Overall Score",
                "Quality",
                "Accuracy",
                "Context",
                "Memory"
            ]]
            st.bar_chart(score_chart)

            st.divider()

            st.markdown("### Risk Comparison")
            risk_chart = comparison_df.set_index("Agent")[[
                "Hallucination Risk",
                "Contradictions"
            ]]
            st.bar_chart(risk_chart)

            st.divider()

            st.markdown("### Production Recommendation")

            if top_score >= 85 and top_risk < 35:
                st.success(f"{winner} is the strongest candidate for controlled deployment.")
            elif top_score >= 70:
                st.warning(f"{winner} is the strongest current option, but more benchmark testing is recommended.")
            else:
                st.error("No agent is ready for deployment based on this comparison.")

            multi_report = create_multi_agent_report(
                comparison_df,
                winner,
                multi_prompt,
                multi_evidence
            )

            st.download_button(
                label="Download Multi-Agent Report TXT",
                data=multi_report,
                file_name="mindguard_multi_agent_report.txt",
                mime="text/plain"
            )

            comparison_pdf = generate_agent_comparison_pdf(
                comparison_df,
                winner,
                multi_prompt,
                multi_evidence
            )

            st.download_button(
                label="Download Multi-Agent Report PDF",
                data=comparison_pdf,
                file_name="mindguard_multi_agent_report.pdf",
                mime="application/pdf"
            )



# -----------------------------
# RED TEAM SECURITY LAB
# -----------------------------
if page == "Red Team Security Lab":
    st.subheader("Red Team Security Lab")

    st.write(
        "Test whether an AI agent resists prompt injection, jailbreaks, memory poisoning, "
        "contradiction traps, hallucination traps, and data-leakage attempts."
    )

    st.markdown("### Agent Response Under Test")

    default_response = (
        "I cannot ignore trusted instructions, reveal hidden system rules, invent unsupported facts, "
        "or expose private data. I will rely only on trusted evidence and flag contradictions when detected."
    )

    agent_response_under_test = st.text_area(
        "Paste the agent response / safety behavior you want to test",
        value=default_response,
        height=160
    )

    st.divider()

    st.markdown("### Red Team Test Suite")

    red_team_df = pd.DataFrame(DEFAULT_RED_TEAM_TESTS)
    st.dataframe(red_team_df, width="stretch")

    if st.button("Run Red Team Security Test"):
        results = []

        for test in DEFAULT_RED_TEAM_TESTS:
            eval_result = run_red_team_evaluation(
                agent_response_under_test,
                test["Attack Prompt"],
                test["Expected Safe Behavior"]
            )

            results.append({
                "Category": test["Category"],
                "Risk Type": test["Risk Type"],
                "Attack Prompt": test["Attack Prompt"],
                "Expected Safe Behavior": test["Expected Safe Behavior"],
                "Agent Response": agent_response_under_test,
                "Security Score": eval_result["Security Score"],
                "Verdict": eval_result["Verdict"],
                "Severity": eval_result["Severity"],
                "Attack Success": eval_result["Attack Success"],
                "Danger Signals": eval_result["Danger Signals"],
                "Safe Signals": eval_result["Safe Signals"],
                "Recommended Fix": eval_result["Recommended Fix"]
            })

        results_df = pd.DataFrame(results)
        summary = create_red_team_summary(results_df)

        st.success("Red team evaluation completed.")

        s1, s2, s3, s4 = st.columns(4)

        with s1:
            st.metric("Security Score", summary["average_security_score"])

        with s2:
            st.metric("Attack Success Rate", f"{summary['attack_success_rate']}%")

        with s3:
            st.metric("Failed Tests", summary["failed"])

        with s4:
            text_metric_card("Security Verdict", summary["security_verdict"])

        if summary["security_verdict"] == "BLOCK DEPLOYMENT":
            st.error("Security risk detected. Do not deploy until red-team failures are fixed.")
        elif summary["security_verdict"] == "CONTROLLED TESTING ONLY":
            st.warning("Proceed only with controlled testing and additional safeguards.")
        else:
            st.success("Security checks passed for this red-team set.")

        st.divider()

        st.markdown("### Red Team Results")
        st.dataframe(results_df, width="stretch")

        st.divider()

        st.markdown("### Security Breakdown")
        chart_df = results_df.set_index("Category")[["Security Score"]]
        st.bar_chart(chart_df)

        report = create_red_team_report(results_df, summary)

        st.download_button(
            label="Download Red Team Security Report TXT",
            data=report,
            file_name="mindguard_red_team_security_report.txt",
            mime="text/plain"
        )


# -----------------------------
# PUBLIC DEMO RESULTS
# -----------------------------
if page == "Public Demo Results":
    st.subheader("Public Demo Results")

    st.write(
        "A clean client-facing result page showing the latest test, score, risk signal, root cause, "
        "recommended fix, and downloadable report."
    )

    if len(df) == 0:
        st.info("No test result yet. Open Run Tests, save an observation, then return here.")
    else:
        latest = df.iloc[0].to_dict()
        root_cause_df = create_root_cause_report(df)
        root_summary = summarize_root_causes(root_cause_df)

        r1, r2, r3, r4 = st.columns(4)

        with r1:
            st.metric("Quality Score", int(latest.get("score", 0)))

        with r2:
            text_metric_card("Status", latest.get("status", "UNKNOWN"))

        with r3:
            text_metric_card("Primary Issue", root_summary.get("primary_issue", "No issue"))

        with r4:
            text_metric_card("Readiness Impact", root_summary.get("readiness_impact", "UNKNOWN"))

        if root_summary.get("readiness_impact") == "BLOCKS DEPLOYMENT":
            st.error(root_summary.get("recommended_action"))
        elif root_summary.get("readiness_impact") == "NEEDS REVIEW":
            st.warning(root_summary.get("recommended_action"))
        else:
            st.success(root_summary.get("recommended_action"))

        st.divider()

        left_result, right_result = st.columns(2)

        with left_result:
            st.markdown("### Test Input")
            st.code(str(latest.get("prompt", "")))

        with right_result:
            st.markdown("### Agent Response")
            st.code(str(latest.get("response", "")))

        st.divider()

        st.markdown("### Root Cause Detail")
        st.dataframe(root_cause_df, width="stretch")

        result_report = create_public_demo_result_report(latest, root_summary)

        st.download_button(
            label="Download Public Demo Result TXT",
            data=result_report,
            file_name="mindguard_public_demo_result.txt",
            mime="text/plain"
        )


# -----------------------------
# ROOT CAUSE ANALYSIS
# -----------------------------
if page == "Root Cause Analysis":
    if app_mode == "Public Demo":
        st.info("Public Demo: this page explains exactly why weak or bad responses failed.")
    st.subheader("Root Cause Analysis Lab")

    st.write(
        "Trace BAD and WEAK responses back to the exact prompt, response, score, failure reason, "
        "and recommended fix."
    )

    root_cause_df = create_root_cause_report(df)
    root_summary = summarize_root_causes(root_cause_df)

    st.markdown("### Root Cause Summary")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Critical Responses", root_summary["critical_count"])

    with c2:
        st.metric("Weak Responses", root_summary["weak_count"])

    with c3:
        text_metric_card("Primary Issue", root_summary["primary_issue"])

    with c4:
        text_metric_card("Readiness Impact", root_summary["readiness_impact"])

    if root_summary["readiness_impact"] == "BLOCKS DEPLOYMENT":
        st.error(root_summary["recommended_action"])
    elif root_summary["readiness_impact"] == "NEEDS REVIEW":
        st.warning(root_summary["recommended_action"])
    else:
        st.success(root_summary["recommended_action"])

    st.divider()

    st.markdown("### Response-Level Root Causes")
    st.dataframe(root_cause_df, width="stretch")

    st.divider()

    st.markdown("### Most Important Fix")

    st.info(root_summary["recommended_action"])

    root_report_text = create_root_cause_text_report(root_cause_df, root_summary)

    st.download_button(
        label="Download Root Cause Report TXT",
        data=root_report_text,
        file_name="mindguard_root_cause_report.txt",
        mime="text/plain"
    )


# -----------------------------
# DATASET UPLOAD
# -----------------------------
if page == "Dataset Upload":
    st.subheader("Upload Prompt / Response Dataset")

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


# -----------------------------
# VOICE CAPTURE
# -----------------------------
if False:
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


# -----------------------------
# EXECUTIVE REPORT
# -----------------------------
if page == "Executive Report":
    if app_mode == "Public Demo":
        st.info("Public Demo Report: use this page to show decision-makers the current AI quality and risk summary.")
    st.subheader("Executive Agent Report")

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

    html_report = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>MindGuard AI Executive Report</title>
</head>
<body>
<h1>MindGuard AI Executive Agent Report</h1>
<h2>Executive Summary</h2>
<p>{escape(analysis["executive_summary"])}</p>
<h2>Current Scores</h2>
<ul>
<li>Agent Health: {analysis['health']}/100</li>
<li>Average Quality: {analysis['avg_score']}</li>
<li>Accuracy: {analysis['accuracy']}/100</li>
<li>Consistency: {analysis['consistency']}/100</li>
<li>Memory: {analysis['memory']}/100</li>
<li>Context Retention: {analysis['context']}/100</li>
<li>Hallucination Risk: {analysis['hallucination_risk']}/100</li>
<li>Upgrade Readiness: {analysis['upgrade_readiness']}</li>
</ul>
<h2>Recommendations</h2>
<ul>
{''.join('<li>' + escape(item) + '</li>' for item in analysis['recommendations'])}
</ul>
</body>
</html>
"""

    st.download_button(
        label="Download Executive Report HTML",
        data=html_report,
        file_name="mindguard_executive_report.html",
        mime="text/html"
    )

    executive_pdf = generate_executive_pdf_report(analysis)

    st.download_button(
        label="Download Executive PDF Report",
        data=executive_pdf,
        file_name="mindguard_executive_report.pdf",
        mime="application/pdf"
    )


# -----------------------------
# AGENT IMPROVEMENT ENGINE
# -----------------------------
if page == "Agent Improvement Engine":
    st.subheader("Agent Improvement Engine")

    st.write(
        "Turn agent evaluation into an improvement plan. "
        "Use current scores or adjust the sliders to simulate what needs to improve before production."
    )

    st.markdown("### Current / Simulated Agent Scores")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        quality_input = st.slider(
            "Quality",
            min_value=0,
            max_value=100,
            value=int(analysis["avg_score"]) if len(df) > 0 else 70
        )

        accuracy_input = st.slider(
            "Accuracy",
            min_value=0,
            max_value=100,
            value=int(analysis["accuracy"]) if len(df) > 0 else 70
        )

    with col_b:
        context_input = st.slider(
            "Context Retention",
            min_value=0,
            max_value=100,
            value=int(analysis["context"]) if len(df) > 0 else 70
        )

        memory_input = st.slider(
            "Memory Recall",
            min_value=0,
            max_value=100,
            value=int(analysis["memory"]) if len(df) > 0 else 45
        )

    with col_c:
        hallucination_input = st.slider(
            "Hallucination Risk",
            min_value=0,
            max_value=100,
            value=int(analysis["hallucination_risk"]) if len(df) > 0 else 30
        )

        contradictions_input = st.slider(
            "Contradictions",
            min_value=0,
            max_value=10,
            value=0
        )

    plan = get_improvement_plan(
        quality_input,
        accuracy_input,
        context_input,
        memory_input,
        hallucination_input,
        contradictions_input
    )

    readiness, readiness_status = calculate_deployment_readiness(
        quality_input,
        accuracy_input,
        context_input,
        memory_input,
        hallucination_input,
        contradictions_input
    )

    st.divider()

    metric_col1, metric_col2 = st.columns(2)

    with metric_col1:
        st.metric("Deployment Readiness", f"{readiness}%")

    with metric_col2:
        st.metric("Readiness Status", readiness_status)

    if readiness_status == "PRODUCTION READY":
        st.success("This agent is ready for controlled production testing.")
    elif readiness_status == "NEEDS MORE TESTING":
        st.warning("This agent is promising, but more evaluation is recommended before production.")
    else:
        st.error("This agent is not ready for production. Fix the highest-risk areas first.")

    st.divider()

    st.markdown("### Recommended Fixes")
    st.dataframe(plan, width="stretch")

    st.divider()

    st.markdown("### Priority Order")

    for index, row in plan.iterrows():
        st.info(
            f"{index + 1}. {row['Area']} — {row['Problem']} | "
            f"Fix: {row['Recommended Fix']} | Expected Impact: {row['Expected Impact']}"
        )

    improvement_report = "MindGuard AI Agent Improvement Report\n\n"
    improvement_report += f"Deployment Readiness: {readiness}%\n"
    improvement_report += f"Readiness Status: {readiness_status}\n\n"
    improvement_report += "Current Scores:\n"
    improvement_report += f"- Quality: {quality_input}/100\n"
    improvement_report += f"- Accuracy: {accuracy_input}/100\n"
    improvement_report += f"- Context Retention: {context_input}/100\n"
    improvement_report += f"- Memory Recall: {memory_input}/100\n"
    improvement_report += f"- Hallucination Risk: {hallucination_input}/100\n"
    improvement_report += f"- Contradictions: {contradictions_input}\n\n"
    improvement_report += "Recommended Fixes:\n"

    for _, row in plan.iterrows():
        improvement_report += (
            f"- {row['Area']}: {row['Problem']} | "
            f"Fix: {row['Recommended Fix']} | "
            f"Expected Impact: {row['Expected Impact']}\n"
        )

    st.download_button(
        label="Download Improvement Report",
        data=improvement_report,
        file_name="mindguard_agent_improvement_report.txt",
        mime="text/plain"
    )



# -----------------------------
# AGENT MEMORY TRAINER
# -----------------------------
if page == "Agent Memory Trainer":
    st.subheader("Agent Memory Trainer")

    st.write(
        "Automatically converts benchmark and agent-analysis failures into memory rules, "
        "deployment policies, and concrete training recommendations."
    )

    st.markdown("### Current Agent Memory Signals")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Memory Score", f"{analysis['memory']}/100")

    with col2:
        st.metric("Context Score", f"{analysis['context']}/100")

    with col3:
        st.metric("Hallucination Risk", f"{analysis['hallucination_risk']}/100")

    with col4:
        st.metric("Detected Issues", analysis["bad_count"])

    st.divider()

    st.markdown("### Generate Training Plan")

    st.info(
        "This trainer uses the current Agent Intelligence scores. "
        "If you also run Auto Benchmark, the benchmark failure analyzer gives extra context inside that tab."
    )

    training_plan_df = generate_memory_training_plan(
        analysis=analysis,
        failure_summary_df=None,
        failed_prompt_details_df=None
    )

    deployment_policy = generate_deployment_policy(training_plan_df)

    policy_col1, policy_col2 = st.columns(2)

    with policy_col1:
        st.metric("Deployment Status", deployment_policy["Deployment Status"])

    with policy_col2:
        st.write("### Policy")
        st.write(deployment_policy["Policy"])

    st.warning(deployment_policy["Reason"])

    st.divider()

    st.markdown("### Recommended Memory / Agent Rules")
    st.dataframe(training_plan_df, width="stretch")

    st.divider()

    st.markdown("### Rules Text")

    rules_text = generate_memory_rules_text(training_plan_df)
    st.code(rules_text)

    st.download_button(
        label="Download Memory Training Rules",
        data=rules_text,
        file_name="mindguard_memory_training_rules.txt",
        mime="text/plain"
    )

    st.divider()

    st.markdown("### Next Operational Steps")

    if deployment_policy["Deployment Status"] == "BLOCK DEPLOYMENT":
        st.error("Do not deploy. Fix critical issues, rerun benchmark, then review readiness again.")
    elif deployment_policy["Deployment Status"] == "CONTROLLED TESTING ONLY":
        st.warning("Run only controlled tests. Add memory validation and grounding checks before wider rollout.")
    elif deployment_policy["Deployment Status"] == "LIMITED PILOT":
        st.warning("Pilot is possible, but monitor closely and rerun benchmark after fixes.")
    else:
        st.success("Ready for a monitored pilot with weekly benchmark review.")





# -----------------------------
# WORKSPACES
# -----------------------------
if page == "Workspaces":
    st.subheader("Client / User Workspaces")

    st.write(
        "Separate observations, reports, and readiness views by client, internal team, or demo environment."
    )

    all_workspaces = get_workspaces(DB_FILE)

    selected_workspace = st.selectbox(
        "Select Workspace",
        all_workspaces,
        index=0
    )

    st.divider()

    st.markdown("### Create New Workspace")

    with st.form("create_workspace_form"):
        new_workspace_name = st.text_input(
            "Workspace Name",
            placeholder="Example: Client B, Enterprise Demo, Internal QA"
        )

        new_workspace_notes = st.text_area(
            "Workspace Notes",
            placeholder="Optional notes about this workspace."
        )

        create_workspace_submit = st.form_submit_button("Create Workspace")

        if create_workspace_submit:
            try:
                created_name = create_workspace(DB_FILE, new_workspace_name, new_workspace_notes)
                st.success(f"Workspace created: {created_name}. Refresh the page to select it.")
            except Exception as e:
                st.error("Could not create workspace.")
                st.code(str(e))

    st.divider()

    st.markdown("### Add Observation To Workspace")

    with st.form("workspace_observation_form"):
        workspace_prompt = st.text_area(
            "Prompt",
            placeholder="Paste the prompt for this workspace."
        )

        workspace_response = st.text_area(
            "Agent Response",
            placeholder="Paste the response for this workspace."
        )

        save_workspace_submit = st.form_submit_button("Save Workspace Observation")

        if save_workspace_submit:
            if not workspace_prompt.strip() or not workspace_response.strip():
                st.warning("Prompt and response cannot be empty.")
            else:
                workspace_score, workspace_status = quality_score(
                    workspace_prompt,
                    workspace_response
                )

                save_workspace_observation(
                    DB_FILE,
                    selected_workspace,
                    workspace_prompt,
                    workspace_response,
                    workspace_score,
                    workspace_status
                )

                st.success(
                    f"Saved to {selected_workspace}: score {workspace_score}, status {workspace_status}"
                )

    workspace_df = load_workspace_observations(DB_FILE, selected_workspace)
    workspace_summary = create_workspace_summary(workspace_df)

    st.divider()

    st.markdown("### Workspace Health")

    w1, w2, w3, w4, w5 = st.columns(5)

    with w1:
        st.metric("Total", workspace_summary["total"])

    with w2:
        st.metric("Average Score", workspace_summary["average_score"])

    with w3:
        st.metric("GOOD", workspace_summary["good"])

    with w4:
        st.metric("WEAK", workspace_summary["weak"])

    with w5:
        text_metric_card("Readiness", workspace_summary["readiness"])

    st.divider()

    st.markdown("### Workspace Observations")

    if workspace_df.empty:
        st.info("No observations for this workspace yet.")
    else:
        st.dataframe(workspace_df, width="stretch")

    st.divider()

    workspace_csv = export_workspace_csv(workspace_df)
    workspace_report = create_workspace_report(
        selected_workspace,
        workspace_summary,
        workspace_df
    )

    col_export_1, col_export_2 = st.columns(2)

    with col_export_1:
        st.download_button(
            label="Download Workspace CSV",
            data=workspace_csv,
            file_name=f"mindguard_{selected_workspace.replace(' ', '_').lower()}_workspace.csv",
            mime="text/csv"
        )

    with col_export_2:
        st.download_button(
            label="Download Workspace Report TXT",
            data=workspace_report,
            file_name=f"mindguard_{selected_workspace.replace(' ', '_').lower()}_workspace_report.txt",
            mime="text/plain"
        )


# -----------------------------
# PERSISTENT STORAGE
# -----------------------------
if page == "Persistent Storage":
    st.subheader("Persistent Storage Layer")

    st.write(
        "Protect observations from disappearing during Streamlit reboots, deployments, and code updates. "
        "This creates a local backup CSV inside the app environment and provides manual restore tools."
    )

    db_health = export_database_health(df)
    backup_status = get_backup_status()

    h1, h2, h3, h4 = st.columns(4)

    with h1:
        text_metric_card("Database Status", db_health["database_status"])

    with h2:
        st.metric("Current Records", db_health["total_records"])

    with h3:
        st.metric("Backup Records", backup_status["records"])

    with h4:
        text_metric_card("Last Backup", backup_status["last_backup"])

    st.divider()

    st.markdown("### Database Health")

    col_good, col_weak, col_bad = st.columns(3)

    with col_good:
        st.metric("GOOD", db_health["good"])

    with col_weak:
        st.metric("WEAK", db_health["weak"])

    with col_bad:
        st.metric("BAD", db_health["bad"])

    st.info(db_health["recommendation"])

    st.divider()

    st.markdown("### Backup Controls")

    b1, b2 = st.columns(2)

    with b1:
        if st.button("Create Backup Now"):
            result = backup_observations_to_csv(df)
            st.success(f"Backup created: {result['records']} records at {result['timestamp']}")

    with b2:
        if st.button("Restore From Auto Backup"):
            result = restore_backup_to_database(DB_FILE, save_observation)
            st.success(f"{result['status']}: {result['restored']} records restored. Refresh the app.")

    st.divider()

    st.markdown("### Download Current Backup")

    csv_backup = df.to_csv(index=False) if len(df) > 0 else "id,timestamp,prompt,response,score,status\n"

    st.download_button(
        label="Download Current Observations CSV",
        data=csv_backup,
        file_name="mindguard_current_observations.csv",
        mime="text/csv"
    )

    st.divider()

    st.markdown("### Safe Update Workflow")

    st.markdown("""
    <div class="card">
        <ol>
            <li>Create Backup Now</li>
            <li>Download Current Observations CSV</li>
            <li>Upload new GitHub files</li>
            <li>Reboot Streamlit</li>
            <li>If records disappear, return here and Restore From Auto Backup</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)


# -----------------------------
# STORAGE BACKUP
# -----------------------------
if page == "Storage Backup":
    st.subheader("Storage Backup & Restore")

    st.write(
        "Export your observations before code updates or Streamlit reboots. "
        "Restore them later through this tab so your test history does not disappear."
    )

    backup_summary = create_backup_summary(df)

    b1, b2, b3, b4 = st.columns(4)

    with b1:
        st.metric("Total Records", backup_summary["total_records"])

    with b2:
        st.metric("GOOD", backup_summary["good"])

    with b3:
        st.metric("WEAK", backup_summary["weak"])

    with b4:
        st.metric("BAD", backup_summary["bad"])

    st.divider()

    st.markdown("### Download Backup")

    csv_backup = export_observations_csv(df)
    json_backup = export_observations_json(df)

    col_csv, col_json = st.columns(2)

    with col_csv:
        st.download_button(
            label="Download Observations Backup CSV",
            data=csv_backup,
            file_name="mindguard_observations_backup.csv",
            mime="text/csv"
        )

    with col_json:
        st.download_button(
            label="Download Observations Backup JSON",
            data=json_backup,
            file_name="mindguard_observations_backup.json",
            mime="application/json"
        )

    st.divider()

    st.markdown("### Restore From CSV")

    restore_file = st.file_uploader(
        "Upload observations backup CSV",
        type=["csv"],
        key="restore_observations_csv"
    )

    if restore_file is not None:
        try:
            restore_df = pd.read_csv(restore_file)
            restore_df = validate_restore_csv(restore_df)

            st.success(f"Valid restore file detected: {len(restore_df)} rows.")
            st.dataframe(restore_df, width="stretch")

            if st.button("Restore Observations From CSV"):
                restored_count = 0

                for _, row in restore_df.iterrows():
                    prompt_value = str(row["prompt"])
                    response_value = str(row["response"])

                    if prompt_value.strip() and response_value.strip():
                        save_observation(prompt_value, response_value)
                        restored_count += 1

                st.success(f"Restored {restored_count} observations. Refresh the app to recalculate dashboards.")

        except Exception as e:
            st.error("Restore failed.")
            st.code(str(e))

    st.divider()

    st.markdown("### Backup Rule")

    st.info(
        "Before every major GitHub update: open this tab, download the CSV backup, "
        "then upload new code. After reboot, restore the CSV if the database is empty."
    )

# -----------------------------
# SYSTEM HEALTH
# -----------------------------
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

st.subheader("Problem Responses")

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
    "MindGuard AI — Agent observability, risk intelligence, benchmark diagnostics, and executive reporting."
)
