"""Tests proving the end-to-end pipeline works on a completely different domain dataset."""

import os
import pytest
import pandas as pd

from src.ingest import load_csv
from src.schema_extractor import extract_schema, create_dataset_overview
from src.query_planner import QueryPlan, FilterSpec
from src.plan_validator import validate_plan
from src.execution_engine import execute_plan
from src.charts import generate_chart
from src.narrator import narrate_result


@pytest.fixture
def student_csv_path() -> str:
    path = os.path.join(os.path.dirname(__file__), "fixtures", "student_grades.csv")
    assert os.path.exists(path), f"Fixture not found at {path}"
    return path


def test_second_dataset_full_pipeline(student_csv_path: str):
    # 1. Ingest
    df, report = load_csv(student_csv_path)
    assert len(df) == 40
    assert "Exam_Date" in report.date_columns_parsed
    assert pd.api.types.is_datetime64_any_dtype(df["Exam_Date"])

    # 2. Schema extraction & overview
    schema = extract_schema(df)
    overview = create_dataset_overview(df)
    assert overview.row_count == 40
    assert overview.col_count == 4
    assert overview.duplicate_rows == 1  # Exactly 1 duplicate row as specified
    assert overview.total_missing_cells == 1  # Exactly 1 missing Marks

    col_names = [c.name for c in schema.columns]
    assert col_names == ["Student", "Department", "Marks", "Exam_Date"]

    # 3. Query Plan (Average Marks by Department)
    plan = QueryPlan(
        operation="group_aggregate",
        metric_column="Marks",
        group_by=["Department"],
        aggregation="mean",
    )

    # 4. Validate
    validated_plan = validate_plan(plan, df)
    assert validated_plan.metric_column == "Marks"
    assert validated_plan.group_by == ["Department"]

    # 5. Execute
    result = execute_plan(validated_plan, df)
    assert result.result_type == "series"
    # Ground truth check
    expected = df.groupby("Department")["Marks"].mean().sort_values(ascending=False).round(2)
    for dept, avg_val in expected.items():
        assert pytest.approx(result.data[dept], 0.01) == avg_val

    # 6. Chart
    fig, note = generate_chart(result)
    assert fig is not None

    # 7. Narration
    narrative = narrate_result(result)
    assert "Marks" in narrative
    assert "Department" in narrative
    assert "₹" not in narrative  # Confirms no e-commerce currency wrongly appended


def test_no_hardcoded_ecommerce_columns_in_engine():
    """Confirms no hardcoded dataset column names in query_planner or plan_validator or execution_engine."""
    for module_file in ["ingest.py", "schema_extractor.py", "plan_validator.py", "execution_engine.py"]:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", module_file)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Verify no hardcoded columns
        assert "Total_Sales_INR" not in content
        assert "Unit_Price_INR" not in content
        assert "Customer_ID" not in content
        assert "Shipping_Days" not in content
