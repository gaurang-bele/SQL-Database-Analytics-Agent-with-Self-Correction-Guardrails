import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from app.core.config import settings

logger = logging.getLogger(__name__)

_engines: Dict[str, Engine] = {}

def get_engine(db_url: Optional[str] = None) -> Engine:
    """Retrieve or create a cached SQLAlchemy engine."""
    target_url = db_url or settings.DATABASE_URL
    
    # If SQLite file path doesn't have parent dir, make sure dir exists
    if target_url.startswith("sqlite:///"):
        sqlite_path = target_url.replace("sqlite:///", "")
        if sqlite_path and sqlite_path != ":memory:":
            from pathlib import Path
            Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

    if target_url not in _engines:
        connect_args = {}
        if target_url.startswith("sqlite:"):
            connect_args["check_same_thread"] = False
        
        engine = create_engine(target_url, connect_args=connect_args)
        _engines[target_url] = engine
        logger.info(f"Initialized database engine for: {target_url}")
        
    return _engines[target_url]


def execute_sql(
    sql_query: str,
    db_url: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Execute a read-only SQL query and return (records, column_names).
    Raises exception on database execution failure.
    """
    engine = get_engine(db_url)
    with engine.connect() as connection:
        # Wrap query in sqlalchemy text
        statement = text(sql_query)
        result = connection.execute(statement)
        
        # Retrieve column names and rows
        columns = list(result.keys()) if result.returns_rows else []
        rows = result.fetchall() if result.returns_rows else []
        
        records = [dict(zip(columns, row)) for row in rows]
        return records, columns
