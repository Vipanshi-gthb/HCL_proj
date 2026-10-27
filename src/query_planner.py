"""Query Planner module using Google Gemini (official google-genai SDK).

Follows P123_ARCHITECTURE.md sections 5.4, 6, 9, 10, 11, 12:
- Translates natural language questions into structured QueryPlan instances.
- Receives ONLY Schema metadata and the question string (NEVER receives a DataFrame).
- Handles retries, fallback models, JSON repair, and converts errors into domain exceptions.
- Client injection supported for deterministic offline testing.
"""

import json
import time
import random
from typing import Literal, Optional, List, Any
from pydantic import BaseModel, Field, ValidationError, ConfigDict

from src.config import Settings, get_settings
from src.errors import (
    ConfigError,
    QuestionError,
    PlannerUnavailableError,
    PlanError,
)
from src.schema_extractor import Schema


Agg = Literal["sum", "mean", "median", "min", "max", "count", "nunique"]
Op = Literal[
    "dataset_summary",
    "data_quality",
    "scalar_aggregate",
    "group_aggregate",
    "top_n",
    "time_series",
    "value_counts",
    "unsupported",
]


class FilterSpec(BaseModel):
    column: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains", "between"]
    values: List[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    operation: Op
    metric_column: Optional[str] = None
    aggregation: Optional[Agg] = None
    group_by: List[str] = Field(default_factory=list)
    time_column: Optional[str] = None
    time_grain: Optional[Literal["day", "week", "month", "quarter", "year"]] = None
    filters: List[FilterSpec] = Field(default_factory=list)
    sort_order: Literal["asc", "desc"] = "desc"
    limit: int = 10
    chart_type: Literal["bar", "line", "pie", "none"] = "none"
    explanation: str = ""
    unsupported_reason: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


SYSTEM_PROMPT = """You are the structured Query Planner for a data analysis assistant.
Your job is to translate the user's natural-language question into a validated QueryPlan.

CRITICAL INSTRUCTIONS:
1. NEVER compute numbers or hallucinate analytical answers. You only produce the analysis plan.
2. Select EXACT column names from the provided dataset schema. Do not invent or alter column names.
3. Operations allowed:
   - "dataset_summary": high-level dataset overview / summary statistics.
   - "data_quality": missing values, null checks, or duplicate records.
   - "scalar_aggregate": single overall metric calculation (e.g. total revenue, average profit, count).
   - "group_aggregate": breakdown of a metric grouped by 1 or 2 categorical columns (e.g., average profit by region, compare sales across regions).
   - "top_n": ranking / highest / lowest / top performers (e.g., category with highest sales, top 3 products). Use limit=1 for single 'highest'/'lowest' questions.
   - "time_series": trends or performance grouped over time (requires time_column and time_grain).
   - "value_counts": frequency count of values in a categorical column (e.g., orders by status).
   - "unsupported": if the question requires complex joins, machine learning, external data, or arbitrary code. Set unsupported_reason.
4. Chart selection guidance:
   - "bar": for group_aggregate, top_n, or value_counts with many categories.
   - "line": for time_series trends.
   - "pie": for value_counts or group_aggregate with <= 6 distinct categories.
   - "none": for scalar_aggregate, dataset_summary, data_quality, or unsupported.
5. Provide a clear 1-sentence explanation of what the plan does.
"""


def _build_user_prompt(schema: Schema, question: str) -> str:
    schema_json = json.dumps(schema.to_summary_dict(), indent=2)
    return f"""Dataset Schema and Column Metadata:
{schema_json}

User Question:
"{question}"

Produce a valid QueryPlan JSON adhering to the QueryPlan schema.
"""


def plan_query(
    schema: Schema,
    question: str,
    client: Optional[Any] = None,
    settings: Optional[Settings] = None,
) -> QueryPlan:
    """Translates question and schema into a validated QueryPlan.

    Enforces data privacy: the function signature accepts ONLY Schema and question.
    """
    if settings is None:
        settings = get_settings()

    # Input validation
    clean_q = question.strip() if question else ""
    if not clean_q:
        raise QuestionError("Type a question (max 500 characters).")

    if len(clean_q) > settings.max_question_chars:
        raise QuestionError(
            f"Question length ({len(clean_q)} characters) exceeds maximum limit of {settings.max_question_chars}."
        )

    # Prepare Gemini Client
    if client is None:
        if not settings.is_gemini_configured:
            raise ConfigError("AI planning isn't configured on this server (GEMINI_API_KEY missing).")
        try:
            from google import genai
            client = genai.Client(api_key=settings.gemini_api_key)
        except Exception as e:
            raise ConfigError(f"Failed to initialize Gemini client: {str(e)}")

    user_prompt = _build_user_prompt(schema, clean_q)
    models_to_try = [settings.gemini_model] + [m for m in settings.gemini_fallback_models if m != settings.gemini_model]

    last_exception: Optional[Exception] = None
    response_text = ""

    for model_name in models_to_try:
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Import google.genai types dynamically if available
                from google.genai import types
                config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=QueryPlan,
                    temperature=0.0,
                    http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=config,
                )
                response_text = response.text or ""
                break
            except Exception as e:
                last_exception = e
                err_msg = str(e).lower()
                is_transient = any(code in err_msg for code in ["429", "500", "503", "quota", "resource_exhausted", "timeout", "deadline"])
                is_model_missing = "404" in err_msg or "not found" in err_msg or "is not supported" in err_msg

                if is_model_missing:
                    # Model not found/retired -> try next model in fallback list immediately
                    break

                if is_transient and attempt < max_retries:
                    # Exponential backoff with jitter
                    sleep_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                    time.sleep(sleep_time)
                    continue

                if is_transient:
                    # Exhausted retries on this model; try fallback model if available
                    break

                # Non-transient error (e.g. 400 bad request, 401 auth error)
                if "401" in err_msg or "api_key" in err_msg:
                    raise ConfigError("Invalid Gemini API Key or authentication failed.")
                raise PlannerUnavailableError(f"Gemini request failed: {str(e)}")

        if response_text:
            break

    if not response_text:
        raise PlannerUnavailableError(
            f"The AI planning service is currently busy or unavailable. {str(last_exception) if last_exception else ''}".strip()
        )

    # Attempt to parse QueryPlan JSON
    try:
        return QueryPlan.model_validate_json(response_text)
    except (ValidationError, json.JSONDecodeError) as parse_err:
        # Attempt 1 repair call as per specification
        try:
            repair_prompt = f"""The previous JSON response did not match the required QueryPlan schema.
Validation error: {str(parse_err)}

Original invalid response:
{response_text}

Provide the corrected, strictly valid QueryPlan JSON conforming to the schema."""
            repair_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=QueryPlan,
                temperature=0.0,
                http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
            )
            repair_response = client.models.generate_content(
                model=models_to_try[0],
                contents=repair_prompt,
                config=repair_config,
            )
            repaired_text = repair_response.text or ""
            return QueryPlan.model_validate_json(repaired_text)
        except Exception:
            raise PlanError(
                f"I couldn't turn that question into a supported analysis plan. Please try rephrasing your question."
            )
