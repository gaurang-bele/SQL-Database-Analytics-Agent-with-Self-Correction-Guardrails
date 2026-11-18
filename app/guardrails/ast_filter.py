import logging
from dataclasses import dataclass
from typing import List, Optional, Set
import sqlparse
from sqlparse.sql import Statement
import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)

FORBIDDEN_KEYWORDS: Set[str] = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "GRANT",
    "REVOKE",
    "VACUUM",
    "PRAGMA",
    "EXEC",
    "EXECUTE",
}

FORBIDDEN_EXPRESSION_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Command,
)


@dataclass
class ASTValidationResult:
    is_safe: bool
    error_message: Optional[str] = None
    statement_types: Optional[List[str]] = None


def is_safe_select_only(sql_query: str) -> bool:
    """
    Validates whether an SQL statement is strictly read-only (SELECT)
    using sqlparse AST analysis. Matches specification from the project brief.
    """
    if not sql_query or not sql_query.strip():
        return False

    parsed = sqlparse.parse(sql_query.strip())
    if not parsed:
        return False

    for statement in parsed:
        stmt_type = statement.get_type()
        if stmt_type != "SELECT":
            return False

        # Additional token-level scan to catch chained write operations or sneaky DDL
        for token in statement.flatten():
            val = token.value.upper()
            if val in FORBIDDEN_KEYWORDS:
                return False

    return True


def validate_sql_ast(sql_query: str) -> ASTValidationResult:
    """
    Comprehensive multi-pass AST analyzer combining sqlparse and sqlglot
    for defense-in-depth safety against SQL injection and destructive write operations.
    """
    clean_query = sql_query.strip().rstrip(";")
    if not clean_query:
        return ASTValidationResult(is_safe=False, error_message="Empty SQL query provided.")

    # Pass 1: sqlparse statement classification
    parsed_statements = sqlparse.parse(sql_query)
    if not parsed_statements:
        return ASTValidationResult(is_safe=False, error_message="Unable to parse SQL statement.")

    statement_types = []
    for statement in parsed_statements:
        stmt_type = statement.get_type()
        statement_types.append(stmt_type)

        if stmt_type != "SELECT":
            return ASTValidationResult(
                is_safe=False,
                error_message=f"Write/destructive statement blocked: Statement type is '{stmt_type}'. Only 'SELECT' queries are allowed.",
                statement_types=statement_types,
            )

        # Deep token check
        for token in statement.flatten():
            token_val = token.value.strip().upper()
            if token_val in FORBIDDEN_KEYWORDS:
                return ASTValidationResult(
                    is_safe=False,
                    error_message=f"Blocked forbidden SQL operation keyword detected: '{token_val}'.",
                    statement_types=statement_types,
                )

    # Pass 2: sqlglot semantic AST verification
    try:
        parsed_glot = sqlglot.parse(clean_query)
        for expression in parsed_glot:
            if expression is None:
                continue
            if isinstance(expression, FORBIDDEN_EXPRESSION_TYPES):
                return ASTValidationResult(
                    is_safe=False,
                    error_message=f"Blocked non-read AST expression: {type(expression).__name__}.",
                    statement_types=statement_types,
                )
            # Find any nested DDL/DML expressions within the AST
            for forbidden_type in FORBIDDEN_EXPRESSION_TYPES:
                if list(expression.find_all(forbidden_type)):
                    return ASTValidationResult(
                        is_safe=False,
                        error_message=f"Blocked nested write operation: {forbidden_type.__name__}.",
                        statement_types=statement_types,
                    )
    except Exception as e:
        # If sqlglot parsing fails, fall back to sqlparse verdict
        logger.warning(f"sqlglot parse warning: {e}")

    return ASTValidationResult(is_safe=True, statement_types=statement_types)
