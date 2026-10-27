"""Tests for Plan Validator module."""

import pytest
import pandas as pd
from src.errors import PlanError
from src.query_planner import QueryPlan, FilterSpec
from src.plan_validator import validate_plan


def test_valid_scalar_plan(sample_df: pd.DataFrame):
    plan = QueryPlan(
        operation="scalar_aggregate",
        metric_column="Total_Sales_INR",
        aggregation="sum",
    )
    validated = validate_plan(plan, sample_df)
    assert validated.metric_column == "Total_Sales_INR"
    assert validated.aggregation == "sum"


def test_case_insensitive_column_resolution(sample_df: pd.DataFrame):
    plan = QueryPlan(
        operation="scalar_aggregate",
        metric_column="total_sales_inr",
        aggregation="sum",
    )
    validated = validate_plan(plan, sample_df)
    assert validated.metric_column == "Total_Sales_INR"


def test_unknown_column_raises_error(sample_df: pd.DataFrame):
    plan = QueryPlan(
        operation="scalar_aggregate",
        metric_column="NonExistentColumn",
        aggregation="sum",
    )
    with pytest.raises(PlanError) as exc_info:
        validate_plan(plan, sample_df)
    assert "was not found in the dataset" in str(exc_info.value)


def test_non_numeric_metric_raises_error(sample_df: pd.DataFrame):
    plan = QueryPlan(
        operation="scalar_aggregate",
        metric_column="Region",
        aggregation="sum",
    )
    with pytest.raises(PlanError) as exc_info:
        validate_plan(plan, sample_df)
    assert "is not numeric and cannot be aggregated" in str(exc_info.value)


def test_filter_coercion_case_insensitive(sample_df: pd.DataFrame):
    plan = QueryPlan(
        operation="group_aggregate",
        metric_column="Total_Sales_INR",
        group_by=["Category"],
        filters=[FilterSpec(column="Region", op="eq", values=["north"])],
    )
    validated = validate_plan(plan, sample_df)
    assert validated.filters[0].values == ["North"]
