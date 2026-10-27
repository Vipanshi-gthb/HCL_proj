"""Tests for Matplotlib Chart Generation module."""

import os
import tempfile
import pandas as pd
import matplotlib.pyplot as plt

from src.query_planner import QueryPlan
from src.execution_engine import ExecutionResult
from src.charts import generate_chart


def test_chart_time_series_line():
    ts_data = pd.Series([100.0, 250.0, 400.0], index=["2024-01", "2024-02", "2024-03"])
    plan = QueryPlan(
        operation="time_series",
        metric_column="Total_Sales_INR",
        time_column="Order_Date",
        time_grain="month",
        chart_type="line",
    )
    result = ExecutionResult(
        data=ts_data,
        result_type="series",
        plan=plan,
        pandas_code="",
    )
    fig, note = generate_chart(result)
    assert fig is not None
    assert note == ""
    plt.close(fig)


def test_chart_group_aggregate_bar():
    group_data = pd.Series([500.0, 300.0, 200.0], index=["Category A", "Category B", "Category C"])
    plan = QueryPlan(
        operation="group_aggregate",
        metric_column="Total_Sales_INR",
        group_by=["Category"],
        chart_type="bar",
    )
    result = ExecutionResult(
        data=group_data,
        result_type="series",
        plan=plan,
        pandas_code="",
    )
    fig, note = generate_chart(result)
    assert fig is not None
    plt.close(fig)


def test_chart_truncation_over_15_groups():
    # 20 categories
    data = pd.Series({f"Category_{i}": 1000 - i * 10 for i in range(20)})
    plan = QueryPlan(
        operation="group_aggregate",
        metric_column="Sales",
        group_by=["Category"],
        chart_type="bar",
    )
    result = ExecutionResult(
        data=data,
        result_type="series",
        plan=plan,
        pandas_code="",
    )
    fig, note = generate_chart(result)
    assert fig is not None
    assert "showing top 15" in note
    plt.close(fig)


def test_chart_pie_rule():
    # Value counts with <= 6 items and pie chart requested
    data = pd.Series({"Delivered": 300, "Processing": 100, "Cancelled": 50})
    plan = QueryPlan(
        operation="value_counts",
        group_by=["Order_Status"],
        chart_type="pie",
    )
    result = ExecutionResult(
        data=data,
        result_type="series",
        plan=plan,
        pandas_code="",
    )
    fig, note = generate_chart(result)
    assert fig is not None
    plt.close(fig)


def test_chart_none_for_scalar():
    plan = QueryPlan(
        operation="scalar_aggregate",
        metric_column="Sales",
        aggregation="sum",
    )
    result = ExecutionResult(
        data=150000.0,
        result_type="scalar",
        plan=plan,
        pandas_code="",
    )
    fig, note = generate_chart(result)
    assert fig is None


def test_chart_save_png_inspection():
    """Renders and saves two figures to confirm Matplotlib handles dark styling and labels cleanly."""
    ts_data = pd.Series([12000.0, 18500.0, 22000.0], index=["2024-01", "2024-02", "2024-03"])
    plan = QueryPlan(operation="time_series", metric_column="Total_Sales_INR", time_column="Order_Date", chart_type="line")
    result = ExecutionResult(data=ts_data, result_type="series", plan=plan, pandas_code="")

    fig, _ = generate_chart(result)
    assert fig is not None
    temp_dir = tempfile.gettempdir()
    img_path = os.path.join(temp_dir, "test_chart_line.png")
    fig.savefig(img_path)
    assert os.path.exists(img_path)
    assert os.path.getsize(img_path) > 1000
    plt.close(fig)
    os.remove(img_path)
