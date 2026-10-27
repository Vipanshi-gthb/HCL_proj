"""Tests for schema extraction and privacy isolation."""

import pandas as pd
from src.schema_extractor import extract_schema, determine_kind, create_dataset_overview


def test_determine_kind():
    assert determine_kind(pd.Series([1, 2, 3]).dtype) == "numeric"
    assert determine_kind(pd.Series([1.5, 2.5]).dtype) == "numeric"
    assert determine_kind(pd.Series(["a", "b"]).dtype) == "categorical"
    assert determine_kind(pd.Series([True, False]).dtype) == "bool"
    assert determine_kind(pd.to_datetime(pd.Series(["2024-01-01"])).dtype) == "datetime"


def test_extract_schema_sample_dataset(sample_df: pd.DataFrame):
    schema = extract_schema(sample_df)
    assert len(schema.columns) == len(sample_df.columns)

    col_names = [col.name for col in schema.columns]
    assert "Total_Sales_INR" in col_names
    assert "Region" in col_names
    assert "Order_Date" in col_names

    summary = schema.to_summary_dict()
    assert "columns" in summary
    assert len(summary["columns"]) == 19

    # Verify no row values leaked into schema summary
    summary_str = str(summary)
    assert "Electronics" not in summary_str
    assert "North" not in summary_str


def test_create_dataset_overview(sample_df: pd.DataFrame):
    overview = create_dataset_overview(sample_df)
    assert overview.row_count == 500
    assert overview.col_count == 19
    assert overview.duplicate_rows == 0
    assert len(overview.preview_records) == 10
