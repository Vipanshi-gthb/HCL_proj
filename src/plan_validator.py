"""Plan Validator module for P_123.

Enforces validation rules specified in P123_ARCHITECTURE.md section 6.2:
- Whitelist check on operation and aggregation
- Exact or case-insensitive column resolution against real DataFrame columns
- Numeric type enforcement for mathematical aggregations
- Limit clamping (1 to 50)
- Local filter value coercion against actual column values (values never leave server)
- Defense-in-depth security checks against unexpected symbols
"""

from typing import List, Optional
import pandas as pd

from src.errors import PlanError
from src.query_planner import QueryPlan, FilterSpec


VALID_OPERATIONS = {
    "dataset_summary",
    "data_quality",
    "scalar_aggregate",
    "group_aggregate",
    "top_n",
    "time_series",
    "value_counts",
    "unsupported",
}

VALID_AGGREGATIONS = {"sum", "mean", "median", "min", "max", "count", "nunique"}


def _resolve_column_name(col: str, available_cols: List[str]) -> str:
    """Resolves column name against available columns with case/space/underscore insensitivity."""
    if col in available_cols:
        return col

    col_clean = col.lower().replace("_", "").replace(" ", "").strip()
    for actual in available_cols:
        actual_clean = actual.lower().replace("_", "").replace(" ", "").strip()
        if col_clean == actual_clean:
            return actual

    raise PlanError(
        f"Column '{col}' was not found in the dataset. Available columns: {', '.join(available_cols)}"
    )


def validate_plan(plan: QueryPlan, df: pd.DataFrame) -> QueryPlan:
    """Validates the QueryPlan against the real DataFrame and enforces domain constraints."""
    if plan.operation not in VALID_OPERATIONS:
        raise PlanError(f"Unsupported analysis operation: '{plan.operation}'.")

    if plan.operation == "unsupported":
        return plan

    # Check for defense-in-depth injection patterns
    for field_val in [plan.explanation, plan.metric_column, plan.time_column] + plan.group_by:
        if field_val and "__" in str(field_val):
            raise PlanError("Invalid characters detected in analysis plan.")

    available_cols = list(df.columns)

    # 1. Resolve and validate metric_column
    if plan.metric_column:
        plan.metric_column = _resolve_column_name(plan.metric_column, available_cols)

    # 2. Resolve and validate group_by columns
    if plan.group_by:
        if len(plan.group_by) > 2:
            plan.group_by = plan.group_by[:2]
        resolved_groups = []
        for g in plan.group_by:
            resolved_groups.append(_resolve_column_name(g, available_cols))
        plan.group_by = resolved_groups

    # 3. Resolve and validate time_column
    if plan.time_column:
        plan.time_column = _resolve_column_name(plan.time_column, available_cols)

    # 4. Operation-specific validations
    if plan.operation in ("scalar_aggregate", "group_aggregate", "top_n", "time_series"):
        if not plan.metric_column:
            # If metric_column is missing, try to default or fail
            raise PlanError(f"Operation '{plan.operation}' requires a metric column to aggregate.")

        if plan.aggregation and plan.aggregation not in VALID_AGGREGATIONS:
            raise PlanError(f"Unsupported aggregation '{plan.aggregation}'. Allowed: {', '.join(VALID_AGGREGATIONS)}")

        if not plan.aggregation:
            plan.aggregation = "sum"

        # Math aggregations require numeric columns
        if plan.aggregation in ("sum", "mean", "median", "min", "max"):
            if not pd.api.types.is_numeric_dtype(df[plan.metric_column]):
                raise PlanError(
                    f"Column '{plan.metric_column}' is not numeric and cannot be aggregated using '{plan.aggregation}'."
                )

    if plan.operation == "group_aggregate":
        if not plan.group_by:
            raise PlanError("Group aggregate operation requires at least one group_by column.")

    if plan.operation == "value_counts":
        if not plan.group_by:
            if plan.metric_column:
                plan.group_by = [plan.metric_column]
            else:
                raise PlanError("Value counts operation requires a column to count.")

    if plan.operation == "time_series":
        if not plan.time_column:
            # Try to auto-detect a datetime column
            dt_cols = [c for c in available_cols if pd.api.types.is_datetime64_any_dtype(df[c])]
            if dt_cols:
                plan.time_column = dt_cols[0]
            else:
                raise PlanError("Time series operation requires a valid date/time column.")
        else:
            if not pd.api.types.is_datetime64_any_dtype(df[plan.time_column]):
                # Attempt to parse
                try:
                    df[plan.time_column] = pd.to_datetime(df[plan.time_column])
                except Exception:
                    raise PlanError(f"Column '{plan.time_column}' cannot be parsed as date/time.")

        if not plan.time_grain:
            plan.time_grain = "month"

    # Clamp limit between 1 and 50
    plan.limit = max(1, min(50, plan.limit))

    # 5. Resolve and coerce filters locally
    validated_filters: List[FilterSpec] = []
    for f in plan.filters:
        resolved_col = _resolve_column_name(f.column, available_cols)
        coerced_vals = []
        col_series = df[resolved_col]

        # Case-insensitive matching for string/categorical columns
        if not pd.api.types.is_numeric_dtype(col_series) and not pd.api.types.is_datetime64_any_dtype(col_series):
            unique_vals = [str(u) for u in col_series.dropna().unique()]
            unique_lower_map = {str(u).lower().strip(): str(u) for u in unique_vals}

            for val in f.values:
                val_clean = str(val).lower().strip()
                if val_clean in unique_lower_map:
                    coerced_vals.append(unique_lower_map[val_clean])
                else:
                    coerced_vals.append(val)
        else:
            coerced_vals = f.values

        validated_filters.append(
            FilterSpec(column=resolved_col, op=f.op, values=coerced_vals)
        )

    plan.filters = validated_filters
    return plan
