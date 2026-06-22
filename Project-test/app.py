from __future__ import annotations

from datetime import date, datetime, timedelta
import random
import traceback
from types import SimpleNamespace

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

CORE_IMPORT_ERROR = None
CORE_IMPORT_TRACE = ""

try:
    from core.analytics import build_analysis_result, maintenance_recommendation, score_frame, summarize_frame
    from core.assistant import get_assistant_reply
    from core.config import APP_SUBTITLE, APP_TITLE, ensure_directories
    from core.reports import build_excel_report
    from core.security import verify_password
    from core.storage import get_storage
except Exception as exc:  # pragma: no cover - startup diagnostics for cloud deploys
    CORE_IMPORT_ERROR = exc
    CORE_IMPORT_TRACE = traceback.format_exc()

    APP_TITLE = "Machine Insight MML Studio"
    APP_SUBTITLE = "Startup diagnostics mode"

    def ensure_directories() -> None:
        return

    def verify_password(password: str, password_hash: str) -> bool:
        return False

    def get_storage():
        raise RuntimeError("Core storage module failed to import.")

    def get_assistant_reply(message: str, summary: dict | None = None) -> str:
        return "Assistant is unavailable because core modules failed to load."

    def summarize_frame(frame: pd.DataFrame) -> dict:
        return {"machines": 0, "records": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0}

    def maintenance_recommendation(frame: pd.DataFrame) -> str:
        return "Maintenance recommendation is unavailable because core modules failed to load."

    def score_frame(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.copy()

    def build_analysis_result(frame: pd.DataFrame):
        return SimpleNamespace(frame=frame.copy(), model_name="Unavailable", version_label="n/a", accuracy=0.0)

    def build_excel_report(sheets: dict[str, pd.DataFrame]) -> bytes:
        return b""


st.set_page_config(page_title=APP_TITLE, page_icon="", layout="wide")


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(circle at top left, #17315d 0, #081120 56%, #050b14 100%);
            color: #f5f7fb;
        }
        .hero {
            padding: 1.25rem 1.5rem;
            background: linear-gradient(135deg, rgba(82, 211, 170, 0.22), rgba(20, 36, 67, 0.94));
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.24);
        }
        .pill {
            display: inline-block;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: rgba(82, 211, 170, 0.14);
            color: #52d3aa;
            font-size: 0.78rem;
            margin-right: 0.45rem;
        }
        div[data-testid="metric-container"] {
            background: rgba(15, 27, 48, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 0.75rem;
        }
        section[data-testid="stSidebar"] {
            background: rgba(10, 17, 32, 0.92);
            border-right: 1px solid rgba(255, 255, 255, 0.05);
        }
        .small-note { color: #9cb1d0; font-size: 0.88rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_clock_card() -> None:
    components.html(
        """
        <div style="font-family: Arial, sans-serif; background:#0f1b30; color:#f5f7fb; border:1px solid rgba(255,255,255,.08); border-radius:18px; padding:12px 16px;">
          <div style="font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:#9cb1d0;">Live system clock</div>
          <div id="clock" style="font-size:24px; font-weight:700; margin-top:4px; color:#52d3aa;"></div>
        </div>
        <script>
          const clock = document.getElementById('clock');
          function tick() { clock.textContent = new Date().toLocaleString(); }
          tick();
          setInterval(tick, 1000);
        </script>
        """,
        height=100,
    )


def ensure_state() -> None:
    defaults = {
        "authenticated": False,
        "current_user": None,
        "chat_history": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def seed_demo_data(storage) -> None:
    if storage.list_machines().empty:
        machines = [
            ("Hydraulic Press A", "HP-900", "Plant Floor 1", "active"),
            ("CNC Lathe B", "CN-320", "Plant Floor 2", "active"),
            ("Packaging Line C", "PK-120", "Warehouse Bay", "monitoring"),
        ]
        for machine_name, model_name, location, status in machines:
            storage.create_machine(machine_name, model_name, location, status)

    if storage.list_telemetry().empty:
        machines_df = storage.list_machines()
        rows: list[dict] = []
        for _, row in machines_df.iterrows():
            for hours_back in range(30, 0, -3):
                base = random.uniform(0.0, 1.0)
                temp = round(random.uniform(52, 92) + base * 8, 2)
                vibration = round(random.uniform(0.7, 3.5) + base, 2)
                pressure = round(random.uniform(4.2, 8.0), 2)
                load_pct = round(random.uniform(58, 97), 2)
                efficiency = round(random.uniform(68, 97) - base * 6, 2)
                score = min(1.0, max(0.0, ((temp - 55) / 45 + vibration / 6 + (100 - efficiency) / 100) / 3))
                rows.append(
                    {
                        "machine_uid": row["machine_uid"],
                        "captured_at": (datetime.utcnow() - timedelta(hours=hours_back)).isoformat(timespec="seconds"),
                        "temperature": temp,
                        "vibration": vibration,
                        "pressure": pressure,
                        "load_pct": load_pct,
                        "efficiency": efficiency,
                        "anomaly_score": round(score, 3),
                        "risk_level": "high" if score >= 0.7 else "medium" if score >= 0.4 else "low",
                    }
                )
        storage.add_telemetry_rows(rows)


def login_panel(storage) -> None:
    st.title(APP_TITLE)
    st.write(APP_SUBTITLE)
    render_clock_card()
    col1, col2 = st.columns([0.95, 1.05])
    with col1:
        st.markdown(
            """
            <div class="hero">
                <span class="pill">Machine analysis</span>
                <span class="pill">Access control</span>
                <span class="pill">Excel reports</span>
                <h1 style="margin-top:0.8rem;">Prototype for Streamlit testing now, standalone app later.</h1>
                <p style="color:#c7d5ea; margin-top:0.6rem;">The app includes role-based login, unique machine IDs, maintenance records, and an AI helper. Use the demo credentials below to sign in.</p>
                <p class="small-note"><b>Admin:</b> admin / admin123<br><b>User:</b> user / user123</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            user = storage.fetch_user(username)
            if user and verify_password(password, user["password_hash"]):
                st.session_state.authenticated = True
                st.session_state.current_user = {
                    "username": user["username"],
                    "role": user["role"],
                    "display_name": user["display_name"],
                }
                storage.log_action(user["username"], "login", "User authenticated")
                st.rerun()
            st.error("Invalid credentials")


def top_bar(user: dict, storage) -> None:
    left, right = st.columns([0.75, 0.25])
    with left:
        st.markdown(
            f"<div class='hero'><span class='pill'>Logged in as {user['role']}</span><h2 style='margin:0.35rem 0 0;'>Welcome, {user['display_name']}</h2><p class='small-note'>Role-aware access keeps admin controls separated from user data entry.</p></div>",
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Logout", use_container_width=True):
            storage.log_action(user["username"], "logout", "User logged out")
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.rerun()


def dashboard_tab(storage, telemetry_df: pd.DataFrame, machines_df: pd.DataFrame, maintenance_df: pd.DataFrame) -> None:
    result = build_analysis_result(telemetry_df) if not telemetry_df.empty else None
    if result is not None:
        storage.save_model_version(result.version_label, result.model_name, result.accuracy, "Latest telemetry scoring run")
        telemetry_df = result.frame

    summary = summarize_frame(telemetry_df)
    maintenance_tip = maintenance_recommendation(telemetry_df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Machines", summary.get("machines", len(machines_df)))
    c2.metric("Telemetry records", summary.get("records", len(telemetry_df)))
    c3.metric("High risk", summary.get("high_risk", 0))
    c4.metric("Maintenance logs", len(maintenance_df))

    st.info(maintenance_tip)

    if not telemetry_df.empty:
        risk_counts = telemetry_df["risk_level"].value_counts().reset_index()
        risk_counts.columns = ["risk_level", "count"]
        st.subheader("Risk distribution")
        st.bar_chart(risk_counts.set_index("risk_level"))
        st.subheader("Latest telemetry")
        st.dataframe(telemetry_df.head(20), use_container_width=True)
    else:
        st.warning("No telemetry data available yet.")


def machines_tab(storage, user: dict) -> None:
    st.subheader("Machine registry")
    with st.form("machine_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            machine_name = st.text_input("Machine name")
            location = st.text_input("Location")
        with col2:
            model_name = st.text_input("Model name")
            status = st.selectbox("Status", ["active", "monitoring", "down", "maintenance"])
        with col3:
            st.caption("A unique machine ID will be generated automatically.")
            submitted = st.form_submit_button("Save machine")

    if submitted and machine_name and model_name and location:
        machine_uid = storage.create_machine(machine_name, model_name, location, status)
        storage.log_action(user["username"], "create_machine", f"Created {machine_uid}")
        st.success(f"Machine saved with ID {machine_uid}")

    st.dataframe(storage.list_machines(), use_container_width=True)


def telemetry_tab(storage, user: dict) -> None:
    st.subheader("Telemetry ingestion")
    machines_df = storage.list_machines()
    if machines_df.empty:
        st.warning("Create a machine first.")
        return

    machine_map = {f"{row.machine_uid} - {row.machine_name}": row.machine_uid for row in machines_df.itertuples(index=False)}
    upload = st.file_uploader("Upload CSV with telemetry columns", type=["csv"])

    if upload is not None:
        frame = pd.read_csv(upload)
        scored = score_frame(frame)
        st.dataframe(scored, use_container_width=True)
        if st.button("Store uploaded telemetry"):
            rows = []
            for _, row in scored.iterrows():
                rows.append(
                    {
                        "machine_uid": str(row.get("machine_uid") or row.get("machine_id") or next(iter(machine_map.values()))),
                        "captured_at": str(row.get("captured_at", datetime.utcnow().isoformat(timespec="seconds"))),
                        "temperature": float(row.get("temperature", 0.0)),
                        "vibration": float(row.get("vibration", 0.0)),
                        "pressure": float(row.get("pressure", 0.0)),
                        "load_pct": float(row.get("load_pct", 0.0)),
                        "efficiency": float(row.get("efficiency", 0.0)),
                        "anomaly_score": float(row.get("anomaly_score", 0.0)),
                        "risk_level": str(row.get("risk_level", "low")),
                    }
                )
            storage.add_telemetry_rows(rows)
            storage.log_action(user["username"], "upload_telemetry", f"Stored {len(rows)} records")
            st.success("Telemetry stored.")

    with st.form("telemetry_form", clear_on_submit=True):
        selected = st.selectbox("Machine", list(machine_map.keys()))
        cols1, cols2 = st.columns(2)
        with cols1:
            temperature = st.number_input("Temperature", value=72.0)
            pressure = st.number_input("Pressure", value=6.2)
            load_pct = st.number_input("Load percentage", value=78.0)
        with cols2:
            vibration = st.number_input("Vibration", value=1.8)
            efficiency = st.number_input("Efficiency", value=88.0)
            captured_at = st.date_input("Captured date", value=date.today())
        submitted = st.form_submit_button("Add telemetry")

    if submitted:
        frame = score_frame(
            pd.DataFrame(
                [
                    {
                        "machine_uid": machine_map[selected],
                        "temperature": temperature,
                        "vibration": vibration,
                        "pressure": pressure,
                        "load_pct": load_pct,
                        "efficiency": efficiency,
                    }
                ]
            )
        )
        row = frame.iloc[0]
        storage.add_telemetry_rows(
            [
                {
                    "machine_uid": machine_map[selected],
                    "captured_at": datetime.combine(captured_at, datetime.utcnow().time()).isoformat(timespec="seconds"),
                    "temperature": float(temperature),
                    "vibration": float(vibration),
                    "pressure": float(pressure),
                    "load_pct": float(load_pct),
                    "efficiency": float(efficiency),
                    "anomaly_score": float(row["anomaly_score"]),
                    "risk_level": str(row["risk_level"]),
                }
            ]
        )
        storage.log_action(user["username"], "add_telemetry", f"Added telemetry for {selected}")
        st.success("Telemetry recorded.")

    st.dataframe(storage.list_telemetry(), use_container_width=True)


def maintenance_tab(storage, user: dict) -> None:
    st.subheader("Maintenance planning")
    machines_df = storage.list_machines()
    if machines_df.empty:
        st.warning("Create machines before logging maintenance.")
        return

    machine_map = {f"{row.machine_uid} - {row.machine_name}": row.machine_uid for row in machines_df.itertuples(index=False)}
    with st.form("maintenance_form", clear_on_submit=True):
        selected = st.selectbox("Machine", list(machine_map.keys()))
        maintenance_date = st.date_input("Maintenance date", value=date.today())
        maintenance_type = st.selectbox("Type", ["preventive", "corrective", "inspection", "calibration"])
        technician = st.text_input("Technician")
        notes = st.text_area("Notes")
        next_due = st.date_input("Next due date", value=date.today() + timedelta(days=30))
        submitted = st.form_submit_button("Save maintenance")

    if submitted:
        storage.add_maintenance_log(
            machine_map[selected],
            maintenance_date.isoformat(),
            maintenance_type,
            notes or "No notes provided.",
            next_due.isoformat(),
            technician or user["username"],
        )
        storage.log_action(user["username"], "maintenance_log", f"Logged {maintenance_type} for {selected}")
        st.success("Maintenance saved.")

    st.dataframe(storage.list_maintenance(), use_container_width=True)


def reports_tab(storage) -> None:
    st.subheader("Excel reports")
    report_bytes = build_excel_report(
        {
            "Machines": storage.list_machines(),
            "Telemetry": storage.list_telemetry(),
            "Maintenance": storage.list_maintenance(),
            "Users": storage.list_users(),
        }
    )
    st.download_button(
        "Download Excel workbook",
        data=report_bytes,
        file_name=f"machine_insight_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption("The workbook includes machine, telemetry, maintenance, and role data.")


def assistant_tab(storage, user: dict) -> None:
    st.subheader("AI assistant")
    telemetry_df = storage.list_telemetry()
    summary = summarize_frame(telemetry_df)
    summary["maintenance_tip"] = maintenance_recommendation(telemetry_df)

    for item in st.session_state.chat_history:
        with st.chat_message(item["role"]):
            st.write(item["content"])

    message = st.chat_input("Ask about risk, maintenance, reports, or roles")
    if message:
        st.session_state.chat_history.append({"role": "user", "content": message})
        reply = get_assistant_reply(message, summary)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        storage.log_action(user["username"], "assistant_query", message)
        st.rerun()


def admin_tab(storage, user: dict) -> None:
    st.subheader("Administration")
    st.write("Manage access roles and reset demo credentials here.")
    st.dataframe(storage.list_users(), use_container_width=True)

    with st.form("user_form", clear_on_submit=True):
        username = st.text_input("Username")
        display_name = st.text_input("Display name")
        password = st.text_input("Temporary password", type="password")
        role = st.selectbox("Role", ["user", "admin"])
        active = st.checkbox("Active", value=True)
        submitted = st.form_submit_button("Save user")

    if submitted and username and display_name and password:
        storage.upsert_user(username, password, role, display_name, int(active))
        storage.log_action(user["username"], "upsert_user", f"Saved user {username}")
        st.success("User saved.")


def main() -> None:
    if CORE_IMPORT_ERROR is not None:
        st.error("Core module import failed during startup.")
        st.code(CORE_IMPORT_TRACE)
        st.stop()

    ensure_directories()
    apply_theme()
    storage = get_storage()
    storage.initialize()
    seed_demo_data(storage)
    ensure_state()

    if not st.session_state.authenticated:
        login_panel(storage)
        return

    user = st.session_state.current_user
    top_bar(user, storage)

    machines_df = storage.list_machines()
    telemetry_df = storage.list_telemetry()
    maintenance_df = storage.list_maintenance()

    tabs = st.tabs(["Dashboard", "Machines", "Telemetry", "Maintenance", "Reports", "AI Assistant"] + (["Admin"] if user["role"] == "admin" else []))
    with tabs[0]:
        dashboard_tab(storage, telemetry_df, machines_df, maintenance_df)
    with tabs[1]:
        machines_tab(storage, user)
    with tabs[2]:
        telemetry_tab(storage, user)
    with tabs[3]:
        maintenance_tab(storage, user)
    with tabs[4]:
        reports_tab(storage)
    with tabs[5]:
        assistant_tab(storage, user)
    if user["role"] == "admin":
        with tabs[6]:
            admin_tab(storage, user)


if __name__ == "__main__":
    main()
