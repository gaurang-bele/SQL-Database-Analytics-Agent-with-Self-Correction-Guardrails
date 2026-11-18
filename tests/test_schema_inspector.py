import pytest
from app.database.inspector import DatabaseInspector, inspect_schema, get_formatted_schema

class TestSchemaInspector:
    """Automated tests verifying SQLAlchemy reflection properties and schema extraction."""

    def test_inspect_schema_tables_and_columns(self, test_db):
        """Verify inspector accurately discovers tables and columns via SQLAlchemy reflection."""
        inspector = DatabaseInspector(test_db)
        schema = inspector.get_schema_metadata()

        assert "orders" in schema
        assert "customers" in schema
        assert "products" in schema
        assert "order_items" in schema

        # Check 'orders' table specifically
        orders_cols = {c["name"]: c for c in schema["orders"]["columns"]}
        assert "id" in orders_cols
        assert "order_date" in orders_cols, "orders table must have order_date column"
        assert "customer_id" in orders_cols
        assert "total_amount" in orders_cols
        assert "status" in orders_cols

        # Ensure created_at does NOT exist in orders
        assert "created_at" not in orders_cols

    def test_inspect_foreign_keys(self, test_db):
        """Verify foreign key relations are properly extracted."""
        inspector = DatabaseInspector(test_db)
        schema = inspector.get_schema_metadata()

        orders_fks = schema["orders"]["foreign_keys"]
        assert len(orders_fks) >= 1
        fk = orders_fks[0]
        assert fk["referred_table"] == "customers"
        assert "customer_id" in fk["constrained_columns"]

    def test_format_schema_for_prompt(self, test_db):
        """Verify formatted DDL representation contains valid table DDL strings."""
        formatted = get_formatted_schema(test_db)
        assert "TABLE orders" in formatted
        assert "order_date" in formatted
        assert "TABLE customers" in formatted
        assert "FOREIGN KEY (customer_id) REFERENCES customers" in formatted
