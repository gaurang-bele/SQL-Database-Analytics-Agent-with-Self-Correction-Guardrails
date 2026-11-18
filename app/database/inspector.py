import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import inspect
from app.database.connection import get_engine

logger = logging.getLogger(__name__)

class DatabaseInspector:
    """Reflects and extracts database schema metadata using SQLAlchemy inspection."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url

    def get_schema_metadata(self) -> Dict[str, Any]:
        """
        Inspect all tables, columns, data types, primary keys, and foreign keys
        using SQLAlchemy reflection properties.
        """
        engine = get_engine(self.db_url)
        inspector = inspect(engine)
        
        table_names = inspector.get_table_names()
        schema: Dict[str, Any] = {}
        
        for table in table_names:
            columns_info = inspector.get_columns(table)
            pk_constraint = inspector.get_pk_constraint(table)
            primary_keys = set(pk_constraint.get("constrained_columns", []))
            foreign_keys = inspector.get_foreign_keys(table)
            
            cols = []
            for col in columns_info:
                cols.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "primary_key": col["name"] in primary_keys
                })
            
            fks = []
            for fk in foreign_keys:
                fks.append({
                    "constrained_columns": fk.get("constrained_columns", []),
                    "referred_table": fk.get("referred_table", ""),
                    "referred_columns": fk.get("referred_columns", [])
                })
                
            schema[table] = {
                "columns": cols,
                "foreign_keys": fks
            }
            
        return schema

    def format_schema_for_prompt(self, schema_dict: Optional[Dict[str, Any]] = None) -> str:
        """
        Formats schema dictionary into clear schema representation for LLM prompts.
        """
        if schema_dict is None:
            schema_dict = self.get_schema_metadata()
            
        lines = []
        for table, meta in schema_dict.items():
            cols_desc = []
            for c in meta["columns"]:
                pk_flag = " PRIMARY KEY" if c["primary_key"] else ""
                null_flag = " NOT NULL" if not c["nullable"] else ""
                cols_desc.append(f"  {c['name']} {c['type']}{pk_flag}{null_flag}")
            
            fk_desc = []
            for fk in meta.get("foreign_keys", []):
                cc = ", ".join(fk["constrained_columns"])
                rc = ", ".join(fk["referred_columns"])
                fk_desc.append(f"  FOREIGN KEY ({cc}) REFERENCES {fk['referred_table']}({rc})")
                
            all_defs = cols_desc + fk_desc
            table_str = f"TABLE {table} (\n" + ",\n".join(all_defs) + "\n);"
            lines.append(table_str)
            
        return "\n\n".join(lines)


def inspect_schema(db_url: Optional[str] = None) -> Dict[str, Any]:
    """Helper function to inspect schema."""
    inspector = DatabaseInspector(db_url)
    return inspector.get_schema_metadata()


def get_formatted_schema(db_url: Optional[str] = None) -> str:
    """Helper function to get string representation of schema for prompt."""
    inspector = DatabaseInspector(db_url)
    return inspector.format_schema_for_prompt()
