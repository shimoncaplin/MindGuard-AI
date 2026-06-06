import pandas as pd


def load_benchmark_csv(uploaded_file):
    df = pd.read_csv(uploaded_file)

    required_columns = ["category", "prompt", "expected_facts"]

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(
            "Benchmark CSV is missing required columns: " + ", ".join(missing)
        )

    return df


def score_benchmark_response(prompt, expected_facts, response, scoring_function):
    scores = scoring_function(prompt, response, expected_facts)

    return {
        "Prompt": prompt,
        "Expected Facts": expected_facts,
        "Response": response,
        "Overall Score": scores["overall"],
        "Quality": scores["quality"],
        "Accuracy": scores["accuracy"],
        "Context": scores["context"],
        "Memory": scores["memory"],
        "Hallucination Risk": scores["hallucination_risk"],
        "Contradictions": scores["contradictions"],
        "Verdict": scores["verdict"],
    }


def create_benchmark_summary(results_df):
    if results_df.empty:
        return {
            "average_score": 0,
            "average_quality": 0,
            "average_accuracy": 0,
            "average_context": 0,
            "average_memory": 0,
            "average_risk": 0,
            "total_tests": 0,
            "failed_tests": 0,
            "readiness": "NO DATA",
        }

    average_score = round(results_df["Overall Score"].mean(), 1)
    average_quality = round(results_df["Quality"].mean(), 1)
    average_accuracy = round(results_df["Accuracy"].mean(), 1)
    average_context = round(results_df["Context"].mean(), 1)
    average_memory = round(results_df["Memory"].mean(), 1)
    average_risk = round(results_df["Hallucination Risk"].mean(), 1)
    total_tests = len(results_df)
    failed_tests = len(results_df[results_df["Overall Score"] < 60])

    if average_score >= 85 and average_risk < 30 and failed_tests == 0:
        readiness = "PRODUCTION READY"
    elif average_score >= 70 and average_risk < 60:
        readiness = "NEEDS MORE TESTING"
    else:
        readiness = "NOT READY"

    return {
        "average_score": average_score,
        "average_quality": average_quality,
        "average_accuracy": average_accuracy,
        "average_context": average_context,
        "average_memory": average_memory,
        "average_risk": average_risk,
        "total_tests": total_tests,
        "failed_tests": failed_tests,
        "readiness": readiness,
    }
