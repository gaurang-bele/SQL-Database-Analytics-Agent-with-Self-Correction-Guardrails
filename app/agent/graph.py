import logging
import time
from typing import Any, Dict, Literal, Optional
from langgraph.graph import END, StateGraph
from app.agent.generator import SQLGenerator
from app.agent.reflection import ErrorReflector
from app.agent.state import AgentState
from app.core.config import settings
from app.database.connection import execute_sql
from app.database.inspector import inspect_schema, DatabaseInspector
from app.guardrails.ast_filter import validate_sql_ast, is_safe_select_only

logger = logging.getLogger(__name__)

# Initialize singletons
sql_generator = SQLGenerator()


# -------------------------------------------------------------------------
# Graph Nodes
# -------------------------------------------------------------------------

def inspect_schema_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: inspect_schema_node
    Automatically queries table metadata using SQLAlchemy reflection properties.
    """
    logger.info("Executing inspect_schema_node...")
    db_url = state.get("db_url")
    inspector = DatabaseInspector(db_url)
    schema_dict = inspector.get_schema_metadata()
    schema_formatted = inspector.format_schema_for_prompt(schema_dict)

    return {
        "schema_info": schema_formatted,
        "status": "schema_inspected"
    }


def generate_sql_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 2: generate_sql_node
    Invokes LLM to generate the SQL statement matching the user's request,
    taking into account reflection guidance if this is a retry attempt.
    """
    logger.info(f"Executing generate_sql_node (retry_count={state.get('retry_count', 0)})...")
    user_query = state.get("user_query", "")
    schema_info = state.get("schema_info", "")
    faulty_sql = state.get("generated_sql")
    error_message = state.get("error_message")
    
    # Check if there is any reflection instruction from a previous reflection_node execution
    reflection_log = state.get("reflection_log", [])
    latest_instruction = None
    if reflection_log:
        latest_instruction = reflection_log[-1].get("instruction")

    # Generate SQL
    sql = sql_generator.generate(
        user_query=user_query,
        schema_info=schema_info,
        faulty_sql=faulty_sql,
        error_message=error_message,
        reflection_instruction=latest_instruction
    )

    return {
        "generated_sql": sql,
        "status": "sql_generated"
    }


def validate_and_execute_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 3: execute_query_node
    Validates AST safety filter first, then connects to PostgreSQL or SQLite
    and executes the SQL statement, catching database errors.
    """
    sql = state.get("generated_sql", "")
    db_url = state.get("db_url")
    logger.info(f"Executing execute_query_node for SQL: {sql}")

    # 1. AST Safety Filter Check
    ast_check = validate_sql_ast(sql)
    if not ast_check.is_safe or not is_safe_select_only(sql):
        err_msg = f"AST Security Check Failed: {ast_check.error_message or 'Destructive/Non-SELECT statement blocked.'}"
        logger.warning(err_msg)
        return {
            "error_message": err_msg,
            "is_safe": False,
            "db_result": None,
            "status": "blocked_by_ast"
        }

    # 2. Database Execution
    try:
        records, columns = execute_sql(sql, db_url)
        return {
            "db_result": records,
            "columns": columns,
            "error_message": None,
            "is_safe": True,
            "status": "query_executed_successfully"
        }
    except Exception as exc:
        err_msg = str(exc)
        logger.error(f"Database execution error: {err_msg}")
        return {
            "error_message": err_msg,
            "db_result": None,
            "columns": None,
            "status": "execution_error"
        }


def reflection_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 4: reflection_node
    If a database error is caught, reads the error message, increments the retry counter,
    and formulates targeted correction instructions for the generator node.
    """
    current_retries = state.get("retry_count", 0)
    new_retry_count = current_retries + 1
    error_message = state.get("error_message", "Unknown error")
    faulty_sql = state.get("generated_sql", "")
    db_url = state.get("db_url")

    logger.info(f"Executing reflection_node: retry {new_retry_count}/3 for error: {error_message}")

    # Analyze error against schema
    diagnosis = ErrorReflector.analyze_error(
        error_message=error_message,
        faulty_sql=faulty_sql,
        db_url=db_url
    )

    reflection_entry = {
        "retry_step": new_retry_count,
        "error_message": error_message,
        "faulty_sql": faulty_sql,
        "diagnosis": diagnosis["error_type"],
        "suggestion": diagnosis.get("suggestion"),
        "instruction": diagnosis["instruction"],
        "timestamp": time.time()
    }

    reflection_log = list(state.get("reflection_log", []))
    reflection_log.append(reflection_entry)

    return {
        "retry_count": new_retry_count,
        "reflection_log": reflection_log,
        "status": "reflected_on_error"
    }


# -------------------------------------------------------------------------
# Conditional Routing Logic
# -------------------------------------------------------------------------

def route_after_execution(state: AgentState) -> Literal["reflection_node", "__end__"]:
    """
    Routes execution after query attempt:
    - If successful without error -> END.
    - If AST security block -> END (do not retry malicious attacks).
    - If database error and retry_count < MAX_RETRIES (3) -> reflection_node.
    - If max retries reached -> END.
    """
    error = state.get("error_message")
    retry_count = state.get("retry_count", 0)
    is_safe = state.get("is_safe", True)
    max_retries = settings.MAX_REFLECTION_RETRIES

    if not error:
        return END

    # If AST filter blocked it as malicious write operation, do not self-correct to bypass security
    if not is_safe:
        logger.info("AST filter blocked malicious SQL. Terminating graph.")
        return END

    if retry_count < max_retries:
        logger.info(f"Error caught ({error}). Routing to reflection_node (retry {retry_count + 1}/{max_retries}).")
        return "reflection_node"
    else:
        logger.warning(f"Maximum retry limit ({max_retries}) reached. Terminating graph.")
        return END


# -------------------------------------------------------------------------
# Graph Construction
# -------------------------------------------------------------------------

def build_sql_agent_graph() -> StateGraph:
    """
    Constructs and compiles the LangGraph StateGraph.
    Coordinates inspect_schema_node, generate_sql_node, execute_query_node, and reflection_node.
    """
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("inspect_schema_node", inspect_schema_node)
    workflow.add_node("generate_sql_node", generate_sql_node)
    workflow.add_node("execute_query_node", validate_and_execute_node)
    workflow.add_node("reflection_node", reflection_node)

    # Set Entry Point
    workflow.set_entry_point("inspect_schema_node")

    # Connect Edges
    workflow.add_edge("inspect_schema_node", "generate_sql_node")
    workflow.add_edge("generate_sql_node", "execute_query_node")

    # Conditional Routing from execution node
    workflow.add_conditional_edges(
        "execute_query_node",
        route_after_execution,
        {
            "reflection_node": "reflection_node",
            END: END
        }
    )

    # Reflection node loops back to generate_sql_node
    workflow.add_edge("reflection_node", "generate_sql_node")

    return workflow.compile()


# Compiled agent graph instance
sql_agent_graph = build_sql_agent_graph()
