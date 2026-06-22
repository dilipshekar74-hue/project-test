from __future__ import annotations

import os


def fallback_reply(message: str, summary: dict | None = None) -> str:
    text = message.lower().strip()
    summary = summary or {}

    if any(word in text for word in ["maintenance", "service", "repair"]):
        return (
            "I can help with maintenance planning. Based on the current data, "
            f"the recommended action is: {summary.get('maintenance_tip', 'review telemetry and schedule a preventive inspection')}."
        )
    if any(word in text for word in ["report", "excel", "download"]):
        return "Use the Reports tab to export the latest workbook in Excel format."
    if any(word in text for word in ["login", "role", "permission", "admin", "user"]):
        return "Admin users can manage accounts and model settings. Standard users can view data, add telemetry, and create maintenance logs."
    if any(word in text for word in ["analysis", "machine", "risk", "anomaly"]):
        return (
            "The analysis engine scores telemetry for risk and anomalies. "
            f"Current records: {summary.get('records', 0)}. High-risk items: {summary.get('high_risk', 0)}."
        )

    return (
        "I can help you review machine health, explain the model output, "
        "prepare maintenance actions, and export reports. Ask me about a machine, a risk level, or an Excel export."
    )


def get_assistant_reply(message: str, summary: dict | None = None) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return fallback_reply(message, summary)

    try:
        from openai import OpenAI

        client = OpenAI()
        prompt = (
            "You are the AI assistant inside a machine-analysis dashboard. "
            "Answer briefly, help the user interpret machine health, maintenance, access roles, and reports. "
            f"Context summary: {summary or {}}"
        )
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.2,
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return fallback_reply(message, summary)
