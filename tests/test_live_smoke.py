"""Optional real Gemini live smoke test."""

import pytest
from src.config import get_settings
from src.schema_extractor import extract_schema
from src.query_planner import plan_query


@pytest.mark.live
def test_real_gemini_smoke(sample_df):
    settings = get_settings()
    if not settings.is_gemini_configured:
        pytest.skip("GEMINI_API_KEY is not configured; skipping live Gemini test.")

    schema = extract_schema(sample_df)
    plan = plan_query(schema=schema, question="What is the total revenue?", settings=settings)
    assert plan.operation in ("scalar_aggregate", "top_n")
    assert plan.metric_column == "Total_Sales_INR"
