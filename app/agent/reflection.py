import logging
import re
from typing import Any, Dict, List, Optional
from app.database.inspector import inspect_schema

logger = logging.getLogger(__name__)

class ErrorReflector:
    """
    Analyzes database execution errors and formulates targeted correction instructions
    for the SQL generation node.
    """

    @staticmethod
    def analyze_error(
        error_message: str,
        faulty_sql: str,
        schema_dict: Optional[Dict[str, Any]] = None,
        db_url: Optional[str] = None
    ) -> Dict[str, Any]:
        if schema_dict is None:
            schema_dict = inspect_schema(db_url)

        diagnosis = {
            "error_type": "general_error",
            "faulty_element": None,
            "suggestion": None,
            "instruction": None
        }

        # 1. Missing Column Error (SQLite: 'no such column: ...' | Postgres: 'column ... does not exist')
        col_match = re.search(r"no such column:\s*([a-zA-Z0-9_\.]+)", error_message, re.IGNORECASE)
        if not col_match:
            col_match = re.search(r'column ["\']?([a-zA-Z0-9_\.]+)["\']? does not exist', error_message, re.IGNORECASE)

        if col_match:
            missing_col = col_match.group(1).split(".")[-1].strip()
            diagnosis["error_type"] = "missing_column"
            diagnosis["faulty_element"] = missing_col

            # Search all tables for valid columns
            all_valid_columns = []
            for tbl, meta in schema_dict.items():
                col_names = [c["name"] for c in meta.get("columns", [])]
                all_valid_columns.extend(col_names)
                if missing_col in ("created_at", "date", "orderdate", "ordered_at") and "order_date" in col_names:
                    diagnosis["suggestion"] = "order_date"

            if not diagnosis["suggestion"]:
                # Simple fuzzy heuristic: if column contains 'date', suggest 'order_date' or 'signup_date'
                if "date" in missing_col.lower() or "time" in missing_col.lower():
                    for vc in all_valid_columns:
                        if "date" in vc.lower():
                            diagnosis["suggestion"] = vc
                            break

            if diagnosis["suggestion"]:
                diagnosis["instruction"] = (
                    f"The column '{missing_col}' does not exist in the database. "
                    f"Use '{diagnosis['suggestion']}' instead. "
                    f"Ensure you only reference valid columns present in the schema."
                )
            else:
                diagnosis["instruction"] = (
                    f"The column '{missing_col}' does not exist in the database. "
                    f"Check the schema and choose an existing column from: {', '.join(set(all_valid_columns))}."
                )
            return diagnosis

        # 2. Missing Table Error (SQLite: 'no such table: ...' | Postgres: 'relation ... does not exist')
        tbl_match = re.search(r"no such table:\s*([a-zA-Z0-9_]+)", error_message, re.IGNORECASE)
        if not tbl_match:
            tbl_match = re.search(r'relation ["\']?([a-zA-Z0-9_]+)["\']? does not exist', error_message, re.IGNORECASE)

        if tbl_match:
            missing_tbl = tbl_match.group(1).strip()
            available_tables = list(schema_dict.keys())
            diagnosis["error_type"] = "missing_table"
            diagnosis["faulty_element"] = missing_tbl
            diagnosis["instruction"] = (
                f"The table '{missing_tbl}' does not exist in the database. "
                f"Valid tables are: {', '.join(available_tables)}."
            )
            return diagnosis

        # 3. Syntax or general SQL error
        diagnosis["instruction"] = (
            f"The database returned this error: '{error_message}'. "
            f"Please inspect the SQL syntax and revise it to be valid read-only SQL matching the schema."
        )
        return diagnosis
