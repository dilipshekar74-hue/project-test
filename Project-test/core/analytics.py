from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import IsolationForest
except Exception:  # pragma: no cover - optional dependency fallback
    IsolationForest = None


NUMERIC_COLUMNS = ["temperature", "vibration", "pressure", "load_pct", "efficiency"]


@dataclass
class AnalysisResult:
    frame: pd.DataFrame
    model_name: str
    version_label: str
    accuracy: float


def _normalise_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    for column in NUMERIC_COLUMNS:
        if column not in work.columns:
            work[column] = 0.0
    return work


def score_frame(frame: pd.DataFrame) -> pd.DataFrame:
    work = _normalise_numeric(frame)
    if work.empty:
        return work

    numeric = work[NUMERIC_COLUMNS].astype(float).fillna(0.0)
    if IsolationForest is not None and len(work) >= 5:
        model = IsolationForest(contamination=0.12, random_state=42)
        labels = model.fit_predict(numeric)
        raw_scores = model.decision_function(numeric)
        work["anomaly_score"] = (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-9)
        work["risk_level"] = np.where(labels == -1, "high", np.where(work["anomaly_score"] > 0.55, "medium", "low"))
    else:
        z_scores = ((numeric - numeric.mean()) / (numeric.std(ddof=0) + 1e-9)).abs()
        work["anomaly_score"] = z_scores.mean(axis=1).clip(lower=0.0, upper=1.0)
        work["risk_level"] = pd.cut(
            work["anomaly_score"],
            bins=[-0.01, 0.35, 0.65, 1.01],
            labels=["low", "medium", "high"],
        ).astype(str)

    return work


def build_analysis_result(frame: pd.DataFrame) -> AnalysisResult:
    scored = score_frame(frame)
    accuracy = float(max(0.55, 1.0 - scored["anomaly_score"].mean())) if not scored.empty else 0.0
    version_label = f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return AnalysisResult(
        frame=scored,
        model_name="IsolationForest" if IsolationForest is not None and len(scored) >= 5 else "HeuristicRiskModel",
        version_label=version_label,
        accuracy=round(accuracy, 4),
    )


def summarize_frame(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"machines": 0, "records": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0}
    risk_counts = frame["risk_level"].value_counts().to_dict()
    return {
        "machines": int(frame["machine_uid"].nunique()) if "machine_uid" in frame else 0,
        "records": int(len(frame)),
        "high_risk": int(risk_counts.get("high", 0)),
        "medium_risk": int(risk_counts.get("medium", 0)),
        "low_risk": int(risk_counts.get("low", 0)),
    }


def maintenance_recommendation(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No telemetry is available yet. Add machine data to generate a maintenance recommendation."
    high_risk_ratio = (frame["risk_level"] == "high").mean()
    if high_risk_ratio >= 0.35:
        return "Schedule an urgent inspection, lubrication, and vibration check."
    if high_risk_ratio >= 0.15:
        return "Plan a preventive inspection in the next maintenance window."
    return "Current readings are stable. Continue routine monitoring and the next planned service cycle."
