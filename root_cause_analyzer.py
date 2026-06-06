import pandas as pd


def _safe_text(value, max_len=500):
    text = str(value).strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text



def _is_short_fact_answer(prompt, response):
    prompt_lower = str(prompt).lower().strip()
    response_clean = str(response).strip().lower()

    short_fact_patterns = [
        "what is",
        "what's",
        "how many",
        "calculate",
        "capital of",
        "2 plus 2",
        "1 plus 1",
        "sum of",
        "result of",
    ]

    if any(pattern in prompt_lower for pattern in short_fact_patterns):
        if 1 <= len(response_clean) <= 80:
            return True

    return False


def _short_fact_is_correct(prompt, response):
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
                return False

            return str(int(expected)) in response_clean or str(expected) in response_clean
        except Exception:
            return False

    return False


def classify_failure_reason(row):
    score = int(row.get("score", 0))
    prompt = str(row.get("prompt", ""))
    response = str(row.get("response", ""))

    reasons = []
    fixes = []

    response_len = len(response.strip())

    if _short_fact_is_correct(prompt, response):
        return {
            "Failure Reason": "Correct short factual answer",
            "Recommended Fix": "No fix required. Short factual answers should not block deployment.",
            "Context Match": 100,
            "Response Length": response_len,
        }

    prompt_words = set(
        w.lower().strip(".,?!:;()[]{}\"'")
        for w in prompt.split()
        if len(w) > 4
    )
    response_lower = response.lower()

    matched_words = [w for w in prompt_words if w in response_lower]
    context_ratio = len(matched_words) / max(1, len(prompt_words))

    if score < 50:
        reasons.append("Critical low quality score")
        fixes.append("Rewrite the response with more complete structure, clearer answer, and stronger factual grounding.")

    if response_len < 40:
        reasons.append("Response too short")
        fixes.append("Increase answer detail and include a clear next step.")

    if context_ratio < 0.35 and len(prompt_words) > 0:
        reasons.append("Weak prompt-response alignment")
        fixes.append("Include the key entities and requirements from the original prompt.")

    weak_phrases = [
        "i don't know",
        "not sure",
        "maybe",
        "probably",
        "cannot answer",
        "unable to help",
        "random"
    ]

    if any(phrase in response_lower for phrase in weak_phrases):
        reasons.append("Uncertain or weak language")
        fixes.append("Replace vague wording with clear, evidence-based wording or escalate when evidence is missing.")

    if response_len > 0 and response.count(".") == 0:
        reasons.append("Poor response structure")
        fixes.append("Use complete sentences and separate the answer into clear parts.")

    if not reasons:
        if score < 80:
            reasons.append("Moderate quality weakness")
            fixes.append("Improve clarity, relevance, completeness, and actionability.")
        else:
            reasons.append("No major failure detected")
            fixes.append("Continue monitoring with larger datasets.")

    return {
        "Failure Reason": "; ".join(reasons),
        "Recommended Fix": "; ".join(dict.fromkeys(fixes)),
        "Context Match": round(context_ratio * 100, 1),
        "Response Length": response_len,
    }


def create_root_cause_report(df):
    if df is None or df.empty:
        return pd.DataFrame([{
            "ID": "",
            "Status": "NO DATA",
            "Score": 0,
            "Prompt": "No observations found",
            "Response": "",
            "Failure Reason": "No data available",
            "Recommended Fix": "Add observations, upload a dataset, or run demo tests.",
            "Context Match": 0,
            "Response Length": 0,
        }])

    target_df = df[(df["score"] < 80) | (df["status"].astype(str).isin(["BAD", "WEAK"]))].copy()

    if not target_df.empty:
        target_df = target_df[
            ~target_df.apply(lambda row: _short_fact_is_correct(row.get("prompt", ""), row.get("response", "")), axis=1)
        ]

    if target_df.empty:
        return pd.DataFrame([{
            "ID": "",
            "Status": "HEALTHY",
            "Score": 100,
            "Prompt": "No BAD or WEAK responses detected",
            "Response": "",
            "Failure Reason": "No major response-level failure detected",
            "Recommended Fix": "Continue monitoring and expand benchmark coverage.",
            "Context Match": 100,
            "Response Length": 0,
        }])

    rows = []

    for _, row in target_df.iterrows():
        classification = classify_failure_reason(row)

        rows.append({
            "ID": row.get("id", ""),
            "Status": row.get("status", ""),
            "Score": row.get("score", 0),
            "Prompt": _safe_text(row.get("prompt", ""), 260),
            "Response": _safe_text(row.get("response", ""), 360),
            "Failure Reason": classification["Failure Reason"],
            "Recommended Fix": classification["Recommended Fix"],
            "Context Match": classification["Context Match"],
            "Response Length": classification["Response Length"],
        })

    result_df = pd.DataFrame(rows)
    result_df = result_df.sort_values(["Score", "ID"], ascending=[True, False])
    return result_df


def summarize_root_causes(root_cause_df):
    if root_cause_df is None or root_cause_df.empty:
        return {
            "critical_count": 0,
            "weak_count": 0,
            "primary_issue": "No data",
            "recommended_action": "Add observations before root cause analysis.",
            "readiness_impact": "UNKNOWN"
        }

    if "Status" in root_cause_df.columns and "NO DATA" in root_cause_df["Status"].astype(str).values:
        return {
            "critical_count": 0,
            "weak_count": 0,
            "primary_issue": "No observations available",
            "recommended_action": "Add observations before root cause analysis.",
            "readiness_impact": "UNKNOWN"
        }

    critical_count = len(root_cause_df[root_cause_df["Score"] < 50]) if "Score" in root_cause_df.columns else 0
    weak_count = len(root_cause_df[(root_cause_df["Score"] >= 50) & (root_cause_df["Score"] < 80)]) if "Score" in root_cause_df.columns else 0

    all_reasons = " ".join(root_cause_df["Failure Reason"].astype(str).tolist()).lower()

    if "weak prompt-response alignment" in all_reasons:
        primary_issue = "Prompt-response alignment"
        recommended_action = "Strengthen response grounding against prompt requirements."
    elif "response too short" in all_reasons:
        primary_issue = "Response completeness"
        recommended_action = "Require fuller responses with clear structure and next steps."
    elif "uncertain" in all_reasons:
        primary_issue = "Uncertainty handling"
        recommended_action = "Replace vague language with evidence-based answers or escalation."
    elif critical_count > 0:
        primary_issue = "Critical low-score responses"
        recommended_action = "Review and fix BAD responses before deployment."
    else:
        primary_issue = "General quality weakness"
        recommended_action = "Improve clarity, structure, and relevance."

    if critical_count > 0:
        readiness_impact = "BLOCKS DEPLOYMENT"
    elif weak_count > 0:
        readiness_impact = "NEEDS REVIEW"
    else:
        readiness_impact = "LOW IMPACT"

    return {
        "critical_count": critical_count,
        "weak_count": weak_count,
        "primary_issue": primary_issue,
        "recommended_action": recommended_action,
        "readiness_impact": readiness_impact
    }


def create_root_cause_text_report(root_cause_df, summary):
    report = "MindGuard AI Root Cause Analysis Report\n\n"

    report += "Summary\n"
    report += f"- Critical Responses: {summary.get('critical_count', 0)}\n"
    report += f"- Weak Responses: {summary.get('weak_count', 0)}\n"
    report += f"- Primary Issue: {summary.get('primary_issue', '')}\n"
    report += f"- Recommended Action: {summary.get('recommended_action', '')}\n"
    report += f"- Readiness Impact: {summary.get('readiness_impact', '')}\n\n"

    report += "Response-Level Findings\n"

    for _, row in root_cause_df.iterrows():
        report += f"\nID: {row.get('ID', '')}\n"
        report += f"Status: {row.get('Status', '')}\n"
        report += f"Score: {row.get('Score', '')}\n"
        report += f"Prompt: {row.get('Prompt', '')}\n"
        report += f"Response: {row.get('Response', '')}\n"
        report += f"Failure Reason: {row.get('Failure Reason', '')}\n"
        report += f"Recommended Fix: {row.get('Recommended Fix', '')}\n"
        report += f"Context Match: {row.get('Context Match', '')}\n"
        report += f"Response Length: {row.get('Response Length', '')}\n"

    return report
