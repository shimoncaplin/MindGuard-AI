import pandas as pd


def analyze_benchmark_failures(results_df):
    if results_df is None or results_df.empty:
        return pd.DataFrame([{
            "Priority": "HIGH",
            "Issue": "No benchmark results available",
            "Affected Tests": 0,
            "Reason": "Run a benchmark before analyzing failures.",
            "Recommended Fix": "Upload a benchmark CSV and click Run Auto Benchmark."
        }])

    issues = []

    low_score_df = results_df[results_df["Overall Score"] < 70]
    high_risk_df = results_df[results_df["Hallucination Risk"] >= 60]
    low_context_df = results_df[results_df["Context"] < 70]
    low_memory_df = results_df[results_df["Memory"] < 70]
    contradiction_df = results_df[results_df["Contradictions"] > 0]

    if len(low_score_df) > 0:
        issues.append({
            "Priority": "HIGH",
            "Issue": "Low overall benchmark scores",
            "Affected Tests": len(low_score_df),
            "Reason": "Some responses scored below 70, which means they may not be reliable enough for production.",
            "Recommended Fix": "Improve response completeness, structure, relevance, and expected-fact coverage."
        })

    if len(high_risk_df) > 0:
        issues.append({
            "Priority": "HIGH",
            "Issue": "High hallucination risk",
            "Affected Tests": len(high_risk_df),
            "Reason": "Responses contain terms or claims that are not strongly supported by the expected facts.",
            "Recommended Fix": "Ground responses against trusted evidence and reduce unsupported factual claims."
        })

    if len(low_context_df) > 0:
        issues.append({
            "Priority": "MEDIUM",
            "Issue": "Weak context retention",
            "Affected Tests": len(low_context_df),
            "Reason": "Responses did not reflect enough of the original prompt or expected context.",
            "Recommended Fix": "Pass more relevant context into the agent and enforce prompt-response alignment."
        })

    if len(low_memory_df) > 0:
        issues.append({
            "Priority": "MEDIUM",
            "Issue": "Low memory usage",
            "Affected Tests": len(low_memory_df),
            "Reason": "Responses did not show enough memory or recall signals.",
            "Recommended Fix": "Add memory recall checks, retrieval validation, and post-response memory verification."
        })

    if len(contradiction_df) > 0:
        issues.append({
            "Priority": "CRITICAL",
            "Issue": "Contradictions detected",
            "Affected Tests": len(contradiction_df),
            "Reason": "At least one response conflicted with trusted evidence.",
            "Recommended Fix": "Block deployment until contradiction checks are added before final output."
        })

    if not issues:
        issues.append({
            "Priority": "LOW",
            "Issue": "No major benchmark failure detected",
            "Affected Tests": 0,
            "Reason": "The benchmark did not identify critical failures.",
            "Recommended Fix": "Run a larger benchmark dataset before production rollout."
        })

    return pd.DataFrame(issues)


def create_failed_prompt_details(results_df):
    if results_df is None or results_df.empty:
        return pd.DataFrame()

    failed_rows = results_df[
        (results_df["Overall Score"] < 70) |
        (results_df["Hallucination Risk"] >= 60) |
        (results_df["Context"] < 70) |
        (results_df["Memory"] < 70) |
        (results_df["Contradictions"] > 0)
    ].copy()

    if failed_rows.empty:
        return pd.DataFrame([{
            "Category": "All",
            "Prompt": "No failed prompts detected",
            "Failure Reason": "No critical benchmark failure detected",
            "Recommended Fix": "Continue testing with larger datasets."
        }])

    details = []

    for _, row in failed_rows.iterrows():
        reasons = []
        fixes = []

        if row["Overall Score"] < 70:
            reasons.append("Overall score below target")
            fixes.append("Improve completeness and relevance")

        if row["Hallucination Risk"] >= 60:
            reasons.append("High hallucination risk")
            fixes.append("Ground answer in expected facts")

        if row["Context"] < 70:
            reasons.append("Weak context retention")
            fixes.append("Include more prompt context in answer")

        if row["Memory"] < 70:
            reasons.append("Low memory signal")
            fixes.append("Add memory recall validation")

        if row["Contradictions"] > 0:
            reasons.append("Contradiction detected")
            fixes.append("Block output when evidence conflicts")

        details.append({
            "Category": row.get("Category", "Unknown"),
            "Prompt": row.get("Prompt", ""),
            "Failure Reason": "; ".join(reasons),
            "Recommended Fix": "; ".join(fixes),
            "Overall Score": row.get("Overall Score", 0),
            "Hallucination Risk": row.get("Hallucination Risk", 0),
            "Context": row.get("Context", 0),
            "Memory": row.get("Memory", 0),
            "Contradictions": row.get("Contradictions", 0),
        })

    return pd.DataFrame(details)


def create_failure_report_text(summary_df, details_df):
    report = "MindGuard AI Benchmark Failure Analysis Report\n\n"

    report += "Failure Summary:\n"
    for _, row in summary_df.iterrows():
        report += f"- [{row['Priority']}] {row['Issue']} | Affected Tests: {row['Affected Tests']}\n"
        report += f"  Reason: {row['Reason']}\n"
        report += f"  Recommended Fix: {row['Recommended Fix']}\n\n"

    report += "\nFailed Prompt Details:\n"
    for _, row in details_df.iterrows():
        report += f"- Category: {row.get('Category', '')}\n"
        report += f"  Prompt: {row.get('Prompt', '')}\n"
        report += f"  Failure Reason: {row.get('Failure Reason', '')}\n"
        report += f"  Recommended Fix: {row.get('Recommended Fix', '')}\n"
        report += f"  Overall Score: {row.get('Overall Score', '')}\n"
        report += f"  Hallucination Risk: {row.get('Hallucination Risk', '')}\n"
        report += f"  Context: {row.get('Context', '')}\n"
        report += f"  Memory: {row.get('Memory', '')}\n"
        report += f"  Contradictions: {row.get('Contradictions', '')}\n\n"

    return report
