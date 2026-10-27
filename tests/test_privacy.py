"""Privacy proof tests verifying zero cell data leakage to external LLM."""

import inspect
import pandas as pd
from unittest.mock import MagicMock

from src.schema_extractor import extract_schema
from src.query_planner import plan_query, QueryPlan
from src.config import Settings


SENTINEL_STRING = "SENTINEL_CELL_7731"
SENTINEL_NUM = 9876543.21


class FakeGeminiClient:
    def __init__(self):
        self.recorded_calls = []
        self.models = MagicMock()
        self.models.generate_content.side_effect = self._generate_content

    def _generate_content(self, model, contents, config=None):
        self.recorded_calls.append({
            "model": model,
            "contents": str(contents),
            "system_instruction": str(getattr(config, "system_instruction", "")),
        })
        mock_resp = MagicMock()
        mock_resp.text = QueryPlan(
            operation="scalar_aggregate",
            metric_column="Sentinel_Amount",
            aggregation="sum",
            explanation="Sum of sentinel amount"
        ).model_dump_json()
        return mock_resp


def test_planner_signature_rejects_dataframe():
    """Asserts that plan_query cannot accept a DataFrame by type/signature."""
    sig = inspect.signature(plan_query)
    param_names = list(sig.parameters.keys())
    assert "df" not in param_names
    assert "dataframe" not in param_names
    assert "data" not in param_names
    assert "schema" in param_names
    assert "question" in param_names


def test_zero_cell_data_leakage():
    """Builds a DataFrame containing confidential sentinels and proves they never reach Gemini."""
    df_private = pd.DataFrame({
        "Customer_Name": [SENTINEL_STRING, "Alice", "Bob"],
        "Sentinel_Amount": [SENTINEL_NUM, 100.0, 200.0],
        "Category": ["Confidential_Category_X", "Standard", "Standard"],
    })

    # Step 1: Extract schema
    schema = extract_schema(df_private)

    # Step 2: Run planner with recording client
    fake_client = FakeGeminiClient()
    settings = Settings(gemini_api_key="TEST_KEY_DO_NOT_LEAK")

    plan = plan_query(
        schema=schema,
        question="What is the total sentinel amount?",
        client=fake_client,
        settings=settings,
    )

    assert plan.operation == "scalar_aggregate"
    assert len(fake_client.recorded_calls) == 1

    call = fake_client.recorded_calls[0]
    payload = call["contents"] + " " + call["system_instruction"]

    # Critical privacy assertions: sentinel values must NEVER appear in LLM payload
    assert SENTINEL_STRING not in payload
    assert str(SENTINEL_NUM) not in payload
    assert "Confidential_Category_X" not in payload

    # Verify column names and kinds DO appear
    assert "Customer_Name" in payload
    assert "Sentinel_Amount" in payload
    assert "Category" in payload
    assert "What is the total sentinel amount?" in payload


def test_api_key_not_in_error_or_logs():
    """Asserts that API keys never leak in exception messages."""
    settings = Settings(gemini_api_key="SECRET_API_KEY_12345")
    # Fake client that throws an error
    error_client = MagicMock()
    error_client.models.generate_content.side_effect = Exception("HTTP 500: Server Error at https://generativelanguage.googleapis.com/v1beta/models")

    df_dummy = pd.DataFrame({"col": [1, 2]})
    schema = extract_schema(df_dummy)

    try:
        plan_query(schema=schema, question="test", client=error_client, settings=settings)
    except Exception as e:
        assert "SECRET_API_KEY_12345" not in str(e)
