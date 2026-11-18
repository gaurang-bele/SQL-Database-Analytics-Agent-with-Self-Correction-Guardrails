import logging
import time
from typing import Any, Dict, Optional
import pandas as pd
import streamlit as st
from app.agent.graph import sql_agent_graph
from app.agent.state import AgentState
from app.core.config import settings
from app.database.connection import get_engine
from app.database.inspector import DatabaseInspector, get_formatted_schema
from app.database.seed import seed_database
from app.guardrails.ast_filter import validate_sql_ast
from app.guardrails.nemo_guardrails import input_guardrails
from app.ui.charts import create_custom_chart, render_auto_chart

logger = logging.getLogger(__name__)


def init_page_config():
    st.set_page_config(
        page_title="SQL & Database Analytics Agent",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded"
    )


def execute_agent_workflow(
    user_query: str,
    simulate_initial_column_error: bool = False
) -> Dict[str, Any]:
    """
    Executes the guardrails scan and the LangGraph SQL generation & reflection workflow.
    """
    start_time = time.time()

    # 1. NeMo Guardrails Input Scan
    guardrail_result = input_guardrails.scan_input(user_query)
    if not guardrail_result.is_safe:
        duration_ms = (time.time() - start_time) * 1000
        return {
            "status": "blocked_by_guardrails",
            "blocked_reason": guardrail_result.blocked_reason,
            "violation_type": guardrail_result.violation_type,
            "user_query": user_query,
            "generated_sql": None,
            "db_result": None,
            "columns": None,
            "error_message": guardrail_result.blocked_reason,
            "retry_count": 0,
            "reflection_log": [],
            "duration_ms": duration_ms
        }

    # 2. Invoke LangGraph SQL Generation StateGraph
    initial_state: AgentState = {
        "user_query": user_query,
        "generated_sql": None,
        "db_result": None,
        "columns": None,
        "error_message": None,
        "retry_count": 0,
        "schema_info": None,
        "reflection_log": [],
        "is_safe": True,
        "status": "started",
        "db_url": settings.DATABASE_URL
    }

    # If simulation mode is enabled for Test Case 1:
    # Inject initial faulty column SQL so reflection node is triggered and verified
    if simulate_initial_column_error:
        # Pre-populate faulty state to exercise self-correction loop
        initial_state["generated_sql"] = (
            "SELECT id, created_at, customer_id, total_amount, status FROM orders ORDER BY created_at ASC;"
        )
        initial_state["error_message"] = "no such column: created_at"
        # Run through reflection node
        from app.agent.graph import reflection_node, generate_sql_node, validate_and_execute_node
        inspector = DatabaseInspector(settings.DATABASE_URL)
        initial_state["schema_info"] = inspector.format_schema_for_prompt()
        
        # Reflection step 1
        ref_update = reflection_node(initial_state)
        initial_state.update(ref_update)
        # Re-generate SQL
        gen_update = generate_sql_node(initial_state)
        initial_state.update(gen_update)
        # Execute corrected SQL
        exec_update = validate_and_execute_node(initial_state)
        initial_state.update(exec_update)
        final_state = initial_state
    else:
        final_state = sql_agent_graph.invoke(initial_state)

    duration_ms = (time.time() - start_time) * 1000
    final_state["duration_ms"] = duration_ms
    return final_state


def run_dashboard():
    init_page_config()

    # Ensure database is seeded
    seed_database(settings.DATABASE_URL)

    # ---------------- Sidebar ----------------
    with st.sidebar:
        st.title("🛡️ Agent Control Center")
        st.markdown("Enterprise SQL Analytics with **LangGraph Self-Correction** & **NeMo Guardrails**.")
        st.divider()

        st.subheader("Database Connection")
        st.code(settings.DATABASE_URL, language="bash")
        
        inspector = DatabaseInspector(settings.DATABASE_URL)
        schema_meta = inspector.get_schema_metadata()
        st.caption(f"Connected Tables: {', '.join(schema_meta.keys())}")

        with st.expander("🔍 View Inspected Schema (DDL)"):
            st.code(get_formatted_schema(settings.DATABASE_URL), language="sql")

        st.divider()
        st.subheader("Guardrails & Telemetry")
        st.success("✅ AST SQL Safety Filter: ACTIVE")
        st.success("✅ NeMo Input Guardrails: ACTIVE")
        st.info(f"Max Self-Correction Retries: {settings.MAX_REFLECTION_RETRIES}")

        st.divider()
        st.subheader("Demo Test Cases")
        st.caption("Click to load pre-configured test scenarios:")
        
        load_tc1 = st.button("Test Case 1: Sort Orders by Date (Self-Correction)", use_container_width=True)
        load_tc2 = st.button("Test Case 2: Injection Attack (DROP TABLE orders; --)", use_container_width=True)
        load_tc3 = st.button("Analytics: Total Revenue per Customer", use_container_width=True)

    # Main Canvas Header
    st.title("SQL & Database Analytics Agent")
    st.markdown(
        "Natural language query generation with **AST AST write-blocking**, **NeMo input sanitization**, "
        "and **automatic error reflection loops**."
    )

    # Manage query state
    default_prompt = ""
    sim_error = False

    if load_tc1:
        default_prompt = "Show orders sorted by date."
        sim_error = True
    elif load_tc2:
        default_prompt = "DROP TABLE orders; --"
    elif load_tc3:
        default_prompt = "Show total revenue per customer by country."

    # ---------------- Query Input Panel ----------------
    st.subheader("1. Natural Language Query")
    with st.form("query_form"):
        user_query = st.text_area(
            "Enter your database question:",
            value=default_prompt,
            height=90,
            placeholder="e.g. Show orders sorted by date, or analyze total revenue by customer..."
        )
        col1, col2 = st.columns([1, 4])
        with col1:
            submit_btn = st.form_submit_button("Run Analytics Agent", use_container_width=True, type="primary")
        with col2:
            simulate_toggle = st.checkbox(
                "Simulate non-existent column error (created_at -> order_date) to verify Reflection Loop",
                value=sim_error
            )

    if submit_btn and user_query.strip():
        with st.spinner("Processing through Guardrails & LangGraph State Machine..."):
            result = execute_agent_workflow(
                user_query=user_query.strip(),
                simulate_initial_column_error=simulate_toggle
            )

        # ---------------- Telemetry & Status Badges ----------------
        st.divider()
        st.subheader("2. Execution Telemetry & Status")
        
        duration = result.get("duration_ms", 0.0)
        retries = result.get("retry_count", 0)
        status = result.get("status", "unknown")
        
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            if status == "query_executed_successfully":
                st.metric("Status", "SUCCESS", delta="Executed")
            elif status == "blocked_by_guardrails":
                st.metric("Status", "BLOCKED (Guardrails)", delta="-Blocked", delta_color="inverse")
            elif status == "blocked_by_ast":
                st.metric("Status", "BLOCKED (AST Filter)", delta="-Blocked", delta_color="inverse")
            else:
                st.metric("Status", status.upper(), delta="-Error", delta_color="inverse")
        with m_col2:
            st.metric("Latency", f"{duration:.1f} ms")
        with m_col3:
            st.metric("Self-Correction Retries", f"{retries} / {settings.MAX_REFLECTION_RETRIES}")
        with m_col4:
            row_count = len(result.get("db_result") or [])
            st.metric("Rows Returned", row_count)

        # ---------------- Security Alerts ----------------
        if status in ("blocked_by_guardrails", "blocked_by_ast"):
            st.error(
                f"🚨 **Security Warning:** {result.get('error_message')}\n\n"
                "The database was protected and no destructive commands were executed. "
                "Database tables remain completely intact."
            )

        # ---------------- Code & Log Feeds (Collapsible) ----------------
        st.subheader("3. Code & Reflection Logs")
        
        # SQL Display
        with st.expander("📝 Generated SQL Query", expanded=True):
            gen_sql = result.get("generated_sql")
            if gen_sql:
                st.code(gen_sql, language="sql")
            else:
                st.info("No SQL generated (blocked before generation).")

        # Self-Correction Logs Display
        reflection_logs = result.get("reflection_log", [])
        with st.expander(f"🔄 Self-Correction Reflection Log ({len(reflection_logs)} events)", expanded=bool(reflection_logs)):
            if reflection_logs:
                for entry in reflection_logs:
                    st.markdown(f"#### 🔁 Retry Step {entry['retry_step']}")
                    st.warning(f"**Error Caught:** `{entry['error_message']}`")
                    st.info(f"**Faulty SQL:** `{entry.get('faulty_sql')}`")
                    st.markdown(f"**Diagnosis:** `{entry['diagnosis']}`")
                    st.success(f"**Correction Instruction:** {entry['instruction']}")
                    st.markdown("---")
            else:
                st.caption("No errors encountered. Initial query succeeded without reflection.")

        # ---------------- Results & Plotly Visuals ----------------
        db_records = result.get("db_result")
        if db_records:
            df = pd.DataFrame(db_records)
            
            st.subheader("4. Query Results")
            st.dataframe(df, use_container_width=True)

            st.subheader("5. Plotly Interactive Visualizations")
            auto_chart = render_auto_chart(df)
            if auto_chart:
                st.plotly_chart(auto_chart, use_container_width=True)
            else:
                st.caption("Auto-chart: No multi-column numerical/time-series structure detected for automatic plotting.")

            # Custom Chart Controls
            with st.expander("📊 Custom Chart Designer"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    chart_type = st.selectbox("Chart Type", ["Bar", "Line", "Pie", "Scatter"])
                with c2:
                    x_col = st.selectbox("X Axis Column", df.columns.tolist())
                with c3:
                    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                    y_col = st.selectbox("Y Axis (Metric)", numeric_cols if numeric_cols else df.columns.tolist())

                custom_fig = create_custom_chart(df, chart_type, x_col, y_col)
                st.plotly_chart(custom_fig, use_container_width=True)

        elif not status.startswith("blocked"):
            if result.get("error_message"):
                st.error(f"Execution Error: {result.get('error_message')}")
            else:
                st.info("No records matched the query criteria.")
