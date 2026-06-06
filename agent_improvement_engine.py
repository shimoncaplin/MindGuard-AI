import pandas as pd


def get_improvement_plan(
    quality,
    accuracy,
    context,
    memory,
    hallucination_risk,
    contradictions
):
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


def calculate_deployment_readiness(
    quality,
    accuracy,
    context,
    memory,
    hallucination_risk,
    contradictions
):
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
