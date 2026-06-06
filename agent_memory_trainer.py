import pandas as pd


def generate_memory_training_plan(analysis=None, failure_summary_df=None, failed_prompt_details_df=None):
    recommendations = []

    memory_score = 0
    context_score = 0
    hallucination_risk = 0
    bad_count = 0

    if analysis:
        memory_score = int(analysis.get("memory", 0))
        context_score = int(analysis.get("context", 0))
        hallucination_risk = int(analysis.get("hallucination_risk", 0))
        bad_count = int(analysis.get("bad_count", 0))

    if memory_score < 70:
        recommendations.append({
            "Priority": "HIGH",
            "Training Area": "Memory Recall",
            "Detected Issue": f"Memory score is {memory_score}/100",
            "Recommended Rule": "Before answering, retrieve and apply known user, customer, product, or policy facts that are relevant to the prompt.",
            "Expected Impact": "+15 to +25 memory score"
        })

    if context_score < 70:
        recommendations.append({
            "Priority": "HIGH",
            "Training Area": "Context Retention",
            "Detected Issue": f"Context score is {context_score}/100",
            "Recommended Rule": "Before final output, verify that the response directly addresses the original prompt and includes the most relevant context.",
            "Expected Impact": "+10 to +20 context score"
        })

    if hallucination_risk > 30:
        recommendations.append({
            "Priority": "HIGH",
            "Training Area": "Grounding",
            "Detected Issue": f"Hallucination risk is {hallucination_risk}/100",
            "Recommended Rule": "Do not make factual claims unless they are supported by trusted evidence or existing memory.",
            "Expected Impact": "-15 to -30 hallucination risk"
        })

    if bad_count > 0:
        recommendations.append({
            "Priority": "CRITICAL",
            "Training Area": "Failure Prevention",
            "Detected Issue": f"{bad_count} critical low-score response(s) detected",
            "Recommended Rule": "Block deployment when any critical response fails quality, memory, contradiction, or hallucination checks.",
            "Expected Impact": "Higher deployment safety"
        })

    if failure_summary_df is not None and not failure_summary_df.empty:
        for _, row in failure_summary_df.iterrows():
            issue = str(row.get("Issue", "")).lower()

            if "hallucination" in issue:
                recommendations.append({
                    "Priority": "HIGH",
                    "Training Area": "Evidence Alignment",
                    "Detected Issue": row.get("Issue", "High hallucination risk"),
                    "Recommended Rule": "Compare every claim against expected facts before returning the answer.",
                    "Expected Impact": "Lower unsupported-claim rate"
                })

            if "context" in issue:
                recommendations.append({
                    "Priority": "MEDIUM",
                    "Training Area": "Prompt Alignment",
                    "Detected Issue": row.get("Issue", "Weak context retention"),
                    "Recommended Rule": "Check whether the response mentions the key entities and requirements from the prompt.",
                    "Expected Impact": "Better prompt-response alignment"
                })

            if "memory" in issue:
                recommendations.append({
                    "Priority": "MEDIUM",
                    "Training Area": "Memory Use",
                    "Detected Issue": row.get("Issue", "Low memory usage"),
                    "Recommended Rule": "Use remembered facts when they are relevant; do not ignore stored preferences or known facts.",
                    "Expected Impact": "Stronger memory recall"
                })

    if not recommendations:
        recommendations.append({
            "Priority": "LOW",
            "Training Area": "Monitoring",
            "Detected Issue": "No major memory training issue detected",
            "Recommended Rule": "Continue collecting more real-world benchmark data before changing memory policy.",
            "Expected Impact": "More reliable long-term evaluation"
        })

    df = pd.DataFrame(recommendations)
    df = df.drop_duplicates(subset=["Training Area", "Recommended Rule"], keep="first")
    return df


def generate_memory_rules_text(training_plan_df):
    if training_plan_df is None or training_plan_df.empty:
        return "No memory rules generated yet."

    lines = []
    lines.append("MindGuard AI Recommended Memory Rules")
    lines.append("")

    for _, row in training_plan_df.iterrows():
        lines.append(f"- [{row['Priority']}] {row['Training Area']}")
        lines.append(f"  Issue: {row['Detected Issue']}")
        lines.append(f"  Rule: {row['Recommended Rule']}")
        lines.append(f"  Expected Impact: {row['Expected Impact']}")
        lines.append("")

    return "\n".join(lines)


def generate_deployment_policy(training_plan_df):
    if training_plan_df is None or training_plan_df.empty:
        return {
            "Deployment Status": "NEEDS MORE DATA",
            "Reason": "No training recommendations available.",
            "Policy": "Collect more benchmark and memory recall data."
        }

    critical_count = len(training_plan_df[training_plan_df["Priority"] == "CRITICAL"])
    high_count = len(training_plan_df[training_plan_df["Priority"] == "HIGH"])

    if critical_count > 0:
        return {
            "Deployment Status": "BLOCK DEPLOYMENT",
            "Reason": "Critical failure-prevention issues detected.",
            "Policy": "Do not deploy until critical failures are fixed and benchmark is rerun."
        }

    if high_count >= 2:
        return {
            "Deployment Status": "CONTROLLED TESTING ONLY",
            "Reason": "Multiple high-priority memory or grounding issues detected.",
            "Policy": "Allow only limited testing with monitoring enabled."
        }

    if high_count == 1:
        return {
            "Deployment Status": "LIMITED PILOT",
            "Reason": "One high-priority issue remains.",
            "Policy": "Run a pilot with extra review and rollback criteria."
        }

    return {
        "Deployment Status": "READY FOR PILOT",
        "Reason": "No critical or high-priority blocker detected.",
        "Policy": "Proceed with monitored pilot and weekly benchmark review."
    }
