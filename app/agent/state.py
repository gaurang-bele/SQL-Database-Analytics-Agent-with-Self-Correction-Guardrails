from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """
    State dictionary tracking the SQL generation and reflection pipeline.
    Mandated fields: user_query, generated_sql, db_result, error_message, retry_count.
    """
    user_query: str
    generated_sql: Optional[str]
    db_result: Optional[List[Dict[str, Any]]]
    columns: Optional[List[str]]
    error_message: Optional[str]
    retry_count: int
    schema_info: Optional[str]
    reflection_log: List[Dict[str, Any]]
    is_safe: bool
    status: str
    db_url: Optional[str]
