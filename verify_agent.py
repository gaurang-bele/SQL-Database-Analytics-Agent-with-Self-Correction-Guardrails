#!/usr/bin/env python3
"""
Verification Script for SQL & Database Analytics Agent.
Runs the exact test workflows specified in Section 4 of the Project Brief:
1. SQL Self-Correction column-reference recovery loop
2. AST Safety Filter & SQL Injection Block
3. Automated Test Suite Execution
"""
import sys
import subprocess
from app.ui.dashboard import execute_agent_workflow
from app.database.connection import get_engine
from app.database.seed import seed_database
from app.core.config import settings
from sqlalchemy import text


def print_banner(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def verify_test_case_1():
    print_banner("RUNNING TEST CASE 1: SQL Self-Correction Column Recovery")
    print("Step 1: Ensure database is seeded with 'orders' having 'id' and 'order_date'...")
    seed_database(settings.DATABASE_URL)

    print("Step 2: Asking agent: 'Show orders sorted by date' with simulated non-existent column 'created_at'...")
    result = execute_agent_workflow(
        user_query="Show orders sorted by date.",
        simulate_initial_column_error=True
    )

    print(f"Step 3: Verification status: {result['status']}")
    print(f"Initial Error Caught: {result['reflection_log'][0]['error_message']}")
    print(f"Reflection Diagnosis: {result['reflection_log'][0]['diagnosis']}")
    print(f"Reflection Instruction: {result['reflection_log'][0]['instruction']}")
    print(f"Rewritten Corrected SQL: {result['generated_sql']}")
    print(f"Retry count: {result['retry_count']} (capped at 3)")
    print(f"Rows returned: {len(result['db_result'] or [])}")

    assert result["retry_count"] == 1, "Expected exactly 1 retry step."
    assert "order_date" in result["generated_sql"], "Corrected SQL must reference 'order_date'."
    assert "created_at" not in result["generated_sql"], "Faulty column 'created_at' must be replaced."
    assert len(result["db_result"]) == 8, "Expected 8 order records."
    print(">>> TEST CASE 1: PASSED [SUCCESS]")


def verify_test_case_2():
    print_banner("RUNNING TEST CASE 2: AST Safety Filter & SQL Injection Block")
    malicious_query = "DROP TABLE orders; --"
    print(f"Step 1: Submitting malicious query: '{malicious_query}'...")

    result = execute_agent_workflow(user_query=malicious_query)

    print(f"Step 2: Verification status: {result['status']}")
    print(f"Security Alert Message: {result['error_message']}")

    assert result["status"] in ("blocked_by_guardrails", "blocked_by_ast"), "Query was not blocked!"
    assert result["db_result"] is None, "No results should be returned for malicious query."

    print("Step 3: Checking database integrity - verifying table 'orders' remains intact...")
    engine = get_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM orders;")).scalar()
        print(f"Table 'orders' row count: {count} rows")
        assert count == 8, f"Table was compromised! Expected 8 rows, found {count}."

    print(">>> TEST CASE 2: PASSED [SUCCESS]")


def verify_test_case_3():
    print_banner("RUNNING TEST CASE 3: Automated pytest Suite Execution")
    cmd = [sys.executable, "-m", "pytest", "-v"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
        raise RuntimeError("pytest suite failed!")
    print(">>> TEST CASE 3: PASSED [SUCCESS]")


def main():
    print_banner("SQL & DATABASE ANALYTICS AGENT - VERIFICATION SUITE")
    verify_test_case_1()
    verify_test_case_2()
    verify_test_case_3()
    print_banner("ALL VERIFICATION WORKFLOWS COMPLETED SUCCESSFULLY [100%]")


if __name__ == "__main__":
    main()
