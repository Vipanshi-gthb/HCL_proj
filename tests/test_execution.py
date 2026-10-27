"""Tests for execution engine numerical correctness on sample dataset."""

import pytest
import pandas as pd
from src.query_planner import QueryPlan, FilterSpec
from src.execution_engine import execute_plan


def test_total_revenue(sample_df: pd.DataFrame):
    expected_sum = round(float(sample_df["Total_Sales_INR"].sum()), 2)
    plan = QueryPlan(
        operation="scalar_aggregate",
        metric_column="Total_Sales_INR",
        aggregation="sum",
    )
    result = execute_plan(plan, sample_df)
    assert result.result_type == "scalar"
    assert pytest.approx(result.data, 0.01) == expected_sum


def test_highest_sales_category(sample_df: pd.DataFrame):
    grouped = sample_df.groupby("Category")["Total_Sales_INR"].sum().sort_values(ascending=False)
    expected_winner = grouped.index[0]
    expected_val = round(float(grouped.iloc[0]), 2)

    plan = QueryPlan(
        operation="top_n",
        metric_column="Total_Sales_INR",
        group_by=["Category"],
        limit=1,
        sort_order="desc",
    )
    result = execute_plan(plan, sample_df)
    assert result.result_type == "series"
    assert result.data.index[0] == expected_winner
    assert pytest.approx(result.data.iloc[0], 0.01) == expected_val


def test_average_profit_by_region(sample_df: pd.DataFrame):
    expected_profit = sample_df.groupby("Region")["Profit_INR"].mean().sort_values(ascending=False).round(2)
    plan = QueryPlan(
        operation="group_aggregate",
        metric_column="Profit_INR",
        group_by=["Region"],
        aggregation="mean",
    )
    result = execute_plan(plan, sample_df)
    assert result.result_type == "series"
    for region, val in expected_profit.items():
        assert pytest.approx(result.data[region], 0.01) == val


def test_monthly_sales(sample_df: pd.DataFrame):
    expected_ts = sample_df.groupby(sample_df["Order_Date"].dt.to_period("M"))["Total_Sales_INR"].sum().round(2)
    plan = QueryPlan(
        operation="time_series",
        metric_column="Total_Sales_INR",
        time_column="Order_Date",
        time_grain="month",
        aggregation="sum",
    )
    result = execute_plan(plan, sample_df)
    assert result.result_type == "series"
    assert len(result.data) == len(expected_ts)
    for period, val in expected_ts.items():
        assert pytest.approx(result.data[str(period)], 0.01) == val


def test_best_selling_product_quantity(sample_df: pd.DataFrame):
    expected_best = sample_df.groupby("Product")["Quantity"].sum().sort_values(ascending=False).head(1)
    plan = QueryPlan(
        operation="top_n",
        metric_column="Quantity",
        group_by=["Product"],
        limit=1,
        sort_order="desc",
    )
    result = execute_plan(plan, sample_df)
    assert result.data.index[0] == expected_best.index[0]
    assert result.data.iloc[0] == expected_best.iloc[0]


def test_order_status_counts(sample_df: pd.DataFrame):
    expected_counts = sample_df["Order_Status"].value_counts()
    plan = QueryPlan(
        operation="value_counts",
        group_by=["Order_Status"],
    )
    result = execute_plan(plan, sample_df)
    assert (result.data == expected_counts).all()


def test_data_quality(sample_df: pd.DataFrame):
    plan = QueryPlan(operation="data_quality")
    result = execute_plan(plan, sample_df)
    assert result.result_type == "quality"
    assert result.data["duplicate_count"] == 0
    # Rating has 72 missing values in sample dataset
    missing_df = result.data["missing_table"]
    rating_row = missing_df[missing_df["Column"] == "Rating"]
    assert len(rating_row) == 1
    assert rating_row.iloc[0]["Missing_Count"] == 72


def test_filter_and_empty_result(sample_df: pd.DataFrame):
    # Non-matching filter
    plan = QueryPlan(
        operation="scalar_aggregate",
        metric_column="Total_Sales_INR",
        aggregation="sum",
        filters=[FilterSpec(column="Region", op="eq", values=["NonExistentRegion"])],
    )
    result = execute_plan(plan, sample_df)
    assert result.result_type == "empty"
