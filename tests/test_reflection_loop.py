import pytest
from unittest.mock import patch, MagicMock
from app.agent.graph import (
    build_sql_agent_graph,
    reflection_node,
    generate_sql_node,
    validate_and_execute_node,
)
from app.agent.reflection import ErrorReflector
from app.agent.state import AgentState

class TestReflectionAndSelfCorrection:
    """Automated tests for LangGraph error reflection and self-correction loop."""

    def test_reflection_diagnosis_missing_column(self, test_db):
        """Verify ErrorReflector diagnoses missing created_at and suggests order_date."""
        faulty_sql = "SELECT id, created_at FROM orders ORDER BY created_at;"
        error_msg = "no such column: created_at"

        diagnosis = ErrorReflector.analyze_error(
            error_message=error_msg,
            faulty_sql=faulty_sql,
            db_url=test_db
        )

        assert diagnosis["error_type"] == "missing_column"
        assert diagnosis["faulty_element"] == "created_at"
        assert diagnosis["suggestion"] == "order_date"
        assert "order_date" in diagnosis["instruction"]

    def test_reflection_node_state_update(self, test_db):
        """Verify reflection_node increments retry counter and stores log."""
        state: AgentState = {
            "user_query": "Show orders sorted by date.",
            "generated_sql": "SELECT id, created_at FROM orders;",
            "db_result": None,
            "columns": None,
            "error_message": "no such column: created_at",
            "retry_count": 0,
            "schema_info": "TABLE orders (id INTEGER, order_date DATE);",
            "reflection_log": [],
            "is_safe": True,
            "status": "execution_error",
            "db_url": test_db
        }

        updated = reflection_node(state)
        assert updated["retry_count"] == 1
        assert len(updated["reflection_log"]) == 1
        entry = updated["reflection_log"][0]
        assert entry["retry_step"] == 1
        assert "order_date" in entry["instruction"]

    def test_mocked_first_run_error_self_correction_loop(self, test_db):
        """
        Mock a database error ('no such column: created_at') on the first run,
        and verify the graph executes the reflection node and successfully corrects
        the query in the subsequent step to produce valid results.
        """
        graph = build_sql_agent_graph()

        # We simulate the first execution attempt generating faulty column 'created_at',
        # followed by reflection self-correction
        initial_state: AgentState = {
            "user_query": "Show orders sorted by date.",
            "generated_sql": None,
            "db_result": None,
            "columns": None,
            "error_message": None,
            "retry_count": 0,
            "schema_info": None,
            "reflection_log": [],
            "is_safe": True,
            "status": "started",
            "db_url": test_db
        }

        # Track execution call count
        call_count = {"count": 0}
        from app.agent import graph as graph_module

        original_generator = graph_module.sql_generator.generate

        def mock_generate(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                # First run: model mistakenly generates 'created_at'
                return "SELECT id, created_at FROM orders ORDER BY created_at ASC;"
            else:
                # Subsequent run: model incorporates reflection instruction and uses 'order_date'
                return "SELECT id, order_date, total_amount, status FROM orders ORDER BY order_date ASC;"

        with patch.object(graph_module.sql_generator, "generate", side_effect=mock_generate):
            final_state = graph.invoke(initial_state)

        # Assertions
        assert final_state["error_message"] is None, f"Query failed with error: {final_state['error_message']}"
        assert final_state["db_result"] is not None
        assert len(final_state["db_result"]) > 0
        assert final_state["retry_count"] == 1, "Self-correction loop should have incremented retry_count to 1"
        assert len(final_state["reflection_log"]) == 1
        assert "order_date" in final_state["generated_sql"]
        assert "created_at" not in final_state["generated_sql"]

    def test_max_retries_capped_at_three(self, test_db):
        """Verify the self-correction loop strictly terminates after 3 retries."""
        graph = build_sql_agent_graph()

        initial_state: AgentState = {
            "user_query": "Invalid query forcing persistent error",
            "generated_sql": None,
            "db_result": None,
            "columns": None,
            "error_message": None,
            "retry_count": 0,
            "schema_info": None,
            "reflection_log": [],
            "is_safe": True,
            "status": "started",
            "db_url": test_db
        }

        from app.agent import graph as graph_module

        # Mock generator to persistently return an invalid column query
        def persistent_faulty_generate(*args, **kwargs):
            return "SELECT non_existent_col FROM orders;"

        with patch.object(graph_module.sql_generator, "generate", side_effect=persistent_faulty_generate):
            final_state = graph.invoke(initial_state)

        # Must terminate when retry_count reaches 3
        assert final_state["retry_count"] == 3
        assert final_state["error_message"] is not None
        assert final_state["db_result"] is None
