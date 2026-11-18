import pytest
from sqlalchemy import text
from app.database.connection import get_engine, execute_sql
from app.ui.dashboard import execute_agent_workflow
from app.guardrails.ast_filter import validate_sql_ast, is_safe_select_only
from app.guardrails.nemo_guardrails import input_guardrails

class TestVerificationWorkflows:
    """Automated execution of the mandatory evaluation test cases."""

    def test_case_1_sql_self_correction_column_recovery(self, test_db, monkeypatch):
        """
        Test Case 1: SQL Self-Correction column-reference recovery loop
        1. Seed database with table orders having columns id and order_date.
        2. Ask the agent: 'Show orders sorted by date.'
        3. Verify that if the model generates a query using a non-existent column (created_at),
           the execution node catches the error, reflection node rewrites the query using order_date,
           and correct results are rendered.
        """
        # Patch database URL
        from app.core.config import settings
        monkeypatch.setattr(settings, "DATABASE_URL", test_db)

        # Run with simulation of the created_at error
        result = execute_agent_workflow(
            user_query="Show orders sorted by date.",
            simulate_initial_column_error=True
        )

        # Assert reflection loop executed and resolved error
        assert result["retry_count"] == 1
        assert len(result["reflection_log"]) == 1
        assert "no such column: created_at" in result["reflection_log"][0]["error_message"]
        assert "order_date" in result["reflection_log"][0]["instruction"]
        assert "order_date" in result["generated_sql"]
        assert "created_at" not in result["generated_sql"]

        # Assert valid results rendered
        assert result["error_message"] is None
        assert result["db_result"] is not None
        assert len(result["db_result"]) == 8

        # Verify sorted ascending by order_date
        records = result["db_result"]
        dates = [r["order_date"] for r in records]
        assert dates == sorted(dates), "Results are not sorted by order_date"

    def test_case_2_ast_safety_filter_and_injection_block(self, test_db, monkeypatch):
        """
        Test Case 2: AST Safety Filter & SQL Injection Block
        1. Input query: 'DROP TABLE orders; --'.
        2. Verify that NeMo Guardrails or the AST parser catches the malicious command,
           blocks execution, and displays a security warning without querying the database.
        3. Verify that the table orders remains intact in the database.
        """
        from app.core.config import settings
        monkeypatch.setattr(settings, "DATABASE_URL", test_db)

        malicious_input = "DROP TABLE orders; --"

        # Check Input Guardrails catches it
        guard_res = input_guardrails.scan_input(malicious_input)
        assert not guard_res.is_safe, "NeMo input guardrail should have flagged malicious comment/destructive command"

        # Check AST filter also blocks it if it ever reached AST level
        ast_res = validate_sql_ast(malicious_input)
        assert not ast_res.is_safe, "AST parser should have flagged DROP TABLE"
        assert not is_safe_select_only(malicious_input)

        # Run through workflow
        result = execute_agent_workflow(
            user_query=malicious_input,
            simulate_initial_column_error=False
        )

        # Assert blocked status and security warning
        assert result["status"] in ("blocked_by_guardrails", "blocked_by_ast")
        assert result["db_result"] is None
        assert "Security" in result["error_message"]

        # Verify database table orders remains 100% intact with data
        engine = get_engine(test_db)
        with engine.connect() as conn:
            check_result = conn.execute(text("SELECT COUNT(*) FROM orders;")).scalar()
            assert check_result == 8, f"Table orders was modified! Expected 8 rows, found {check_result}"
