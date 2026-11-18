import logging
import re
from typing import Any, Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are an expert SQL Assistant. Your task is to generate a single, read-only SQL query (SELECT) matching the user's request based strictly on the provided database schema.

### Database Schema:
{schema_info}

### Rules:
1. Return ONLY the raw SQL query. Do not include markdown code fences (```sql), explanations, or comments.
2. Only use read-only SELECT statements. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, or other write commands.
3. Only use tables and columns defined in the schema above.
{reflection_section}
"""

REFLECTION_SECTION_TEMPLATE = """
### PREVIOUS ATTEMPT FAILED:
- Faulty SQL: {faulty_sql}
- Database Error: {error_message}
- Reflection Guidance: {reflection_instruction}
Please carefully correct the query to resolve the above error. Ensure all column and table names exist in the schema.
"""


def clean_sql_output(raw_output: str) -> str:
    """Strip markdown code fences and whitespace from LLM output."""
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


class SQLGenerator:
    """Generates SQL queries using an LLM or fallback deterministic engine."""

    def __init__(self, model_name: Optional[str] = None, temperature: Optional[float] = None):
        self.model_name = model_name or settings.OPENAI_MODEL
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self.api_key = settings.OPENAI_API_KEY
        self._llm = None
        self._init_llm()

    def _init_llm(self):
        if self.api_key and not self.api_key.startswith("mock-"):
            try:
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model=self.model_name,
                    temperature=self.temperature,
                    api_key=self.api_key,
                )
                logger.info(f"Initialized ChatOpenAI with model {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize ChatOpenAI: {e}")
                self._llm = None

    def generate(
        self,
        user_query: str,
        schema_info: str,
        faulty_sql: Optional[str] = None,
        error_message: Optional[str] = None,
        reflection_instruction: Optional[str] = None,
        simulate_column_error: bool = False
    ) -> str:
        """
        Generates an SQL query given the user query and schema.
        Incorporates reflection feedback if retrying.
        """
        # If simulation flag is passed and this is attempt 0 without reflection yet,
        # generate a query with 'created_at' to exercise the self-correction loop
        if simulate_column_error and not error_message:
            return "SELECT id, created_at, customer_id, total_amount, status FROM orders ORDER BY created_at ASC;"

        reflection_section = ""
        if error_message and reflection_instruction:
            reflection_section = REFLECTION_SECTION_TEMPLATE.format(
                faulty_sql=faulty_sql or "",
                error_message=error_message,
                reflection_instruction=reflection_instruction,
            )

        # 1. Try invoking live LLM if available
        if self._llm is not None:
            prompt = SYSTEM_PROMPT_TEMPLATE.format(
                schema_info=schema_info,
                reflection_section=reflection_section
            )
            try:
                from langchain_core.messages import SystemMessage, HumanMessage
                messages = [
                    SystemMessage(content=prompt),
                    HumanMessage(content=user_query)
                ]
                response = self._llm.invoke(messages)
                return clean_sql_output(response.content)
            except Exception as e:
                logger.warning(f"LLM call failed: {e}. Falling back to rule-based generation.")

        # 2. Rule-based / deterministic fallback generation
        return self._generate_fallback_sql(
            user_query=user_query,
            faulty_sql=faulty_sql,
            error_message=error_message,
            reflection_instruction=reflection_instruction
        )

    def _generate_fallback_sql(
        self,
        user_query: str,
        faulty_sql: Optional[str] = None,
        error_message: Optional[str] = None,
        reflection_instruction: Optional[str] = None
    ) -> str:
        """
        Deterministic SQL generator for test environments, offline evaluation,
        and instant response without external API requirements.
        """
        uq_lower = user_query.lower()

        # If we have reflection guidance instructing us to replace a column
        if faulty_sql and error_message and reflection_instruction:
            corrected = faulty_sql
            if "order_date" in reflection_instruction and "created_at" in faulty_sql:
                corrected = corrected.replace("created_at", "order_date")
                return corrected
            # Generic correction based on instruction
            col_match = re.search(r"Use '([a-zA-Z0-9_]+)' instead", reflection_instruction)
            bad_match = re.search(r"The column '([a-zA-Z0-9_]+)' does not exist", reflection_instruction)
            if col_match and bad_match:
                good_col = col_match.group(1)
                bad_col = bad_match.group(1)
                return faulty_sql.replace(bad_col, good_col)

        # Case: "Show orders sorted by date"
        if "order" in uq_lower and "date" in uq_lower:
            return "SELECT id, order_date, customer_id, total_amount, status FROM orders ORDER BY order_date ASC;"

        # Case: "Total revenue per customer" / customer spend
        if "revenue" in uq_lower or "sales" in uq_lower or "customer" in uq_lower:
            return (
                "SELECT c.id, c.name, c.country, SUM(o.total_amount) AS total_revenue "
                "FROM customers c JOIN orders o ON c.id = o.customer_id "
                "GROUP BY c.id, c.name, c.country ORDER BY total_revenue DESC;"
            )

        # Case: "Monthly order counts" or trends
        if "month" in uq_lower or "trend" in uq_lower or "count" in uq_lower:
            return (
                "SELECT order_date, COUNT(id) AS order_count, SUM(total_amount) AS daily_revenue "
                "FROM orders GROUP BY order_date ORDER BY order_date ASC;"
            )

        # Case: "Top products" / products
        if "product" in uq_lower:
            return (
                "SELECT p.id, p.name, p.category, p.price, p.stock_quantity "
                "FROM products p ORDER BY p.price DESC;"
            )

        # Default fallback
        return "SELECT id, order_date, customer_id, total_amount, status FROM orders LIMIT 20;"
