import pytest
from app.guardrails.nemo_guardrails import input_guardrails

class TestInputGuardrails:
    """Automated tests verifying raw input scanning for tautologies, comments, script tags, and destructive statements."""

    @pytest.mark.parametrize("malicious_input, expected_violation", [
        ("DROP TABLE orders; --", "comment_expansion_injection"),
        ("SELECT * FROM users WHERE '1'='1'", "tautology_injection"),
        ("Show me orders where 1=1 OR 'a'='a'", "tautology_injection"),
        ("admin' --", "comment_expansion_injection"),
        ("SELECT * FROM users /* bypass filter */", "comment_expansion_injection"),
        ("<script>alert('xss')</script>", "script_tag_injection"),
        ("<img src=x onerror=alert(1)>", "script_tag_injection"),
        ("javascript:void(0)", "script_tag_injection"),
        ("DROP TABLE orders", "destructive_command"),
        ("DELETE FROM customers", "destructive_command"),
        ("TRUNCATE TABLE products", "destructive_command"),
    ])
    def test_guardrails_blocks_malicious_inputs(self, malicious_input, expected_violation):
        """Verify malicious inputs are caught and blocked before reaching the agent."""
        result = input_guardrails.scan_input(malicious_input)
        assert not result.is_safe, f"Failed to block malicious input: {malicious_input}"
        assert result.violation_type == expected_violation
        assert result.blocked_reason is not None

    @pytest.mark.parametrize("safe_input", [
        "Show orders sorted by date.",
        "What is the total revenue per customer?",
        "List all products with price greater than 100",
        "Give me monthly order volume and trends",
        "Count customers from USA and Germany",
    ])
    def test_guardrails_allows_benign_queries(self, safe_input):
        """Verify normal business questions pass without false alarms."""
        result = input_guardrails.scan_input(safe_input)
        assert result.is_safe, f"False positive blocking benign query: {safe_input}"
        assert result.blocked_reason is None

    def test_empty_input_blocked(self):
        """Verify empty prompts are rejected."""
        assert not input_guardrails.scan_input("").is_safe
        assert not input_guardrails.scan_input("   ").is_safe
