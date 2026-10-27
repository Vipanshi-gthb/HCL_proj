"""Mocked Gemini failure handling tests covering retries, fallbacks, and error boundaries."""

import pytest
from unittest.mock import MagicMock, patch

from src.config import Settings
from src.errors import ConfigError, PlannerUnavailableError, PlanError
from src.schema_extractor import Schema, ColumnInfo
from src.query_planner import plan_query, QueryPlan


@pytest.fixture
def dummy_schema() -> Schema:
    return Schema(columns=[
        ColumnInfo(name="Region", dtype="object", kind="categorical"),
        ColumnInfo(name="Sales", dtype="float64", kind="numeric"),
    ])


def test_missing_api_key_raises_config_error(dummy_schema: Schema):
    settings = Settings(gemini_api_key="")
    with pytest.raises(ConfigError) as exc:
        plan_query(schema=dummy_schema, question="What is total sales?", client=None, settings=settings)
    assert "GEMINI_API_KEY missing" in str(exc.value)


def test_valid_plan_parsing(dummy_schema: Schema):
    fake_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"operation": "scalar_aggregate", "metric_column": "Sales", "aggregation": "sum", "explanation": "Total sales"}'
    fake_client.models.generate_content.return_value = mock_resp

    settings = Settings(gemini_api_key="valid_key")
    plan = plan_query(schema=dummy_schema, question="Total sales?", client=fake_client, settings=settings)
    assert plan.operation == "scalar_aggregate"
    assert plan.metric_column == "Sales"
    assert plan.aggregation == "sum"


def test_malformed_json_triggers_repair_and_succeeds(dummy_schema: Schema):
    fake_client = MagicMock()
    # First call returns invalid JSON, second call returns valid JSON
    bad_resp = MagicMock()
    bad_resp.text = "{malformed: json, missing quotes"
    good_resp = MagicMock()
    good_resp.text = '{"operation": "scalar_aggregate", "metric_column": "Sales", "aggregation": "sum", "explanation": "Repaired"}'
    fake_client.models.generate_content.side_effect = [bad_resp, good_resp]

    settings = Settings(gemini_api_key="valid_key")
    plan = plan_query(schema=dummy_schema, question="Total sales?", client=fake_client, settings=settings)
    assert plan.operation == "scalar_aggregate"
    assert fake_client.models.generate_content.call_count == 2


def test_malformed_json_twice_raises_friendly_plan_error(dummy_schema: Schema):
    fake_client = MagicMock()
    bad_resp = MagicMock()
    bad_resp.text = "{still malformed"
    fake_client.models.generate_content.return_value = bad_resp

    settings = Settings(gemini_api_key="valid_key")
    with pytest.raises(PlanError) as exc:
        plan_query(schema=dummy_schema, question="Total sales?", client=fake_client, settings=settings)
    assert "couldn't turn that question into a supported analysis plan" in str(exc.value)


@patch("time.sleep", return_value=None)
def test_rate_limit_429_retries_and_falls_back(mock_sleep, dummy_schema: Schema):
    fake_client = MagicMock()
    # Model 1 fails with 429, Model 2 succeeds
    good_resp = MagicMock()
    good_resp.text = '{"operation": "scalar_aggregate", "metric_column": "Sales", "aggregation": "sum"}'

    fake_client.models.generate_content.side_effect = [
        Exception("429 ResourceExhausted: Quota exceeded"),
        Exception("429 ResourceExhausted: Quota exceeded"),
        Exception("429 ResourceExhausted: Quota exceeded"),
        good_resp,
    ]

    settings = Settings(
        gemini_api_key="valid_key",
        gemini_model="primary-model",
        gemini_fallback_models=["fallback-model"],
    )

    plan = plan_query(schema=dummy_schema, question="Total sales?", client=fake_client, settings=settings)
    assert plan.operation == "scalar_aggregate"
    assert fake_client.models.generate_content.call_count == 4


@patch("time.sleep", return_value=None)
def test_503_service_unavailable_retries(mock_sleep, dummy_schema: Schema):
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = Exception("503 Service Unavailable: Backends busy")

    settings = Settings(
        gemini_api_key="valid_key",
        gemini_model="primary-model",
        gemini_fallback_models=[],
    )

    with pytest.raises(PlannerUnavailableError) as exc:
        plan_query(schema=dummy_schema, question="Total sales?", client=fake_client, settings=settings)
    assert "busy or unavailable" in str(exc.value)


def test_404_model_not_found_switches_immediately_to_fallback(dummy_schema: Schema):
    fake_client = MagicMock()
    good_resp = MagicMock()
    good_resp.text = '{"operation": "scalar_aggregate", "metric_column": "Sales", "aggregation": "sum"}'

    # 404 should NOT retry 3 times; it should immediately move to fallback model
    fake_client.models.generate_content.side_effect = [
        Exception("404 Not Found: Model gemini-deprecated is not supported"),
        good_resp,
    ]

    settings = Settings(
        gemini_api_key="valid_key",
        gemini_model="gemini-deprecated",
        gemini_fallback_models=["gemini-fallback"],
    )

    plan = plan_query(schema=dummy_schema, question="Total sales?", client=fake_client, settings=settings)
    assert plan.operation == "scalar_aggregate"
    assert fake_client.models.generate_content.call_count == 2
