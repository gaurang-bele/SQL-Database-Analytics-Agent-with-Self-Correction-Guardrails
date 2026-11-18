import pytest
from app.guardrails.ast_filter import is_safe_select_only, validate_sql_ast

class TestASTSafetyFilter:
    """Automated tests verifying AST safety filter blocks write operations and allows read-only SELECT."""

    @pytest.mark.parametrize("dangerous_query", [
        "DELETE FROM users;",
        "DELETE FROM users WHERE id = 1;",
        "DROP TABLE orders;",
        "DROP TABLE orders; --",
        "INSERT INTO orders (id, order_date) VALUES (999, '2024-01-01');",
        "UPDATE customers SET name = 'Hacked' WHERE id = 1;",
        "ALTER TABLE orders ADD COLUMN hack TEXT;",
        "TRUNCATE TABLE products;",
        "CREATE TABLE backdoor (id INT);",
        "ATTACH DATABASE 'malicious.db' AS mal;",
        "SELECT * FROM orders; DROP TABLE customers;",
        "SELECT 1; DELETE FROM orders;",
    ])
    def test_ast_filter_rejects_write_operations(self, dangerous_query):
        """Assert the AST parser successfully catches and rejects write queries."""
        # Check standard bool specification
        assert not is_safe_select_only(dangerous_query), f"Failed to block dangerous query: {dangerous_query}"

        # Check detailed validation result
        result = validate_sql_ast(dangerous_query)
        assert not result.is_safe, f"Validation result unexpectedly marked query as safe: {dangerous_query}"
        assert result.error_message is not None

    @pytest.mark.parametrize("safe_query", [
        "SELECT * FROM orders;",
        "SELECT id, order_date FROM orders ORDER BY order_date ASC;",
        "SELECT c.name, COUNT(o.id) FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.name;",
        "WITH monthly_sales AS (SELECT order_date, total_amount FROM orders) SELECT * FROM monthly_sales;",
        "SELECT * FROM products WHERE price > 50.0 AND stock_quantity > 0;",
    ])
    def test_ast_filter_allows_valid_select_queries(self, safe_query):
        """Assert the AST parser successfully allows read-only SELECT queries."""
        assert is_safe_select_only(safe_query), f"False positive: blocked safe query: {safe_query}"
        result = validate_sql_ast(safe_query)
        assert result.is_safe, f"Validation marked valid query unsafe: {result.error_message}"

    def test_empty_or_whitespace_queries(self):
        """Verify empty queries are considered unsafe / invalid."""
        assert not is_safe_select_only("")
        assert not is_safe_select_only("   ")
        assert not validate_sql_ast("").is_safe
