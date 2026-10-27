"""Local Narrative Generator for P_123.

Follows P123_ARCHITECTURE.md sections 4.1 and 5.7:
- Converts ExecutionResult into 1-3 plain-English sentences.
- Grounded strictly in computed numbers (zero LLM hallucinations, zero data leakage).
- Formats numbers with thousands separators and '₹' prefix for *_INR columns.
"""

from typing import Any
import pandas as pd
import numpy as np

from src.execution_engine import ExecutionResult


def _format_value(val: Any, col_name: str = "") -> str:
    """Formats numeric values with commas and currency symbols if applicable."""
    if isinstance(val, (int, np.integer)):
        formatted = f"{int(val):,}"
    elif isinstance(val, (float, np.floating)):
        formatted = f"{float(val):,.2f}"
    else:
        return str(val)

    if "inr" in col_name.lower():
        return f"₹{formatted}"
    return formatted


def narrate_result(result: ExecutionResult) -> str:
    """Produces a concise, factually grounded natural language summary of analytical results."""
    plan = result.plan
    res_type = result.result_type
    metric = plan.metric_column or ""
    agg = plan.aggregation or "sum"

    if res_type == "unsupported":
        return str(result.data)

    if res_type == "empty":
        return "No records in the dataset matched your specified filter criteria."

    # 1. Scalar Aggregate
    if res_type == "scalar":
        formatted_val = _format_value(result.data, metric)
        agg_label = "total" if agg == "sum" else ("average" if agg == "mean" else agg)
        return f"The computed {agg_label} for **{metric}** across the dataset is **{formatted_val}**."

    # 2. Top N
    if res_type in ("series", "dataframe") and plan.operation == "top_n":
        data = result.data
        if isinstance(data, pd.Series):
            if len(data) == 0:
                return "No records found to rank."
            winner = str(data.index[0])
            winner_val = _format_value(data.iloc[0], metric)

            if plan.limit == 1 or len(data) == 1:
                direction = "highest" if plan.sort_order == "desc" else "lowest"
                group_name = plan.group_by[0] if plan.group_by else "category"
                return (
                    f"The {group_name} with the {direction} {metric} is **{winner}** "
                    f"with a {agg} of **{winner_val}**."
                )
            else:
                top_items = [f"{idx} ({_format_value(val, metric)})" for idx, val in data.items()]
                preview = ", ".join(top_items[:3])
                return (
                    f"The top {len(data)} performers by {metric} are led by **{winner}** ({winner_val}). "
                    f"Top rankings: {preview}."
                )

    # 3. Group Aggregate
    if res_type == "series" and plan.operation == "group_aggregate":
        data = result.data
        if len(data) > 0:
            top_group = str(data.index[0])
            top_val = _format_value(data.iloc[0], metric)
            group_name = plan.group_by[0]
            if len(data) > 1:
                second_group = str(data.index[1])
                second_val = _format_value(data.iloc[1], metric)
                return (
                    f"Analysis of **{metric}** grouped by **{group_name}** shows **{top_group}** leads "
                    f"with {top_val}, followed by **{second_group}** ({second_val})."
                )
            return f"Analysis of **{metric}** by **{group_name}** shows **{top_group}** with {top_val}."

    # 4. Time Series
    if res_type == "series" and plan.operation == "time_series":
        data = result.data
        if len(data) > 0:
            peak_period = str(data.idxmax())
            peak_val = _format_value(data.max(), metric)
            lowest_period = str(data.idxmin())
            lowest_val = _format_value(data.min(), metric)
            return (
                f"Across {len(data)} time periods, **{metric}** peaked in **{peak_period}** at **{peak_val}**, "
                f"with the lowest performance in **{lowest_period}** ({lowest_val})."
            )

    # 5. Value Counts
    if res_type == "series" and plan.operation == "value_counts":
        data = result.data
        if len(data) > 0:
            top_item = str(data.index[0])
            top_count = f"{int(data.iloc[0]):,}"
            col_name = plan.group_by[0] if plan.group_by else "category"
            return (
                f"The distribution for **{col_name}** is led by **{top_item}** with **{top_count}** orders/records."
            )

    # 6. Data Quality
    if res_type == "quality":
        info = result.data
        dup_count = info.get("duplicate_count", 0)
        missing_df = info.get("missing_table", pd.DataFrame())

        dup_msg = f"Found **{dup_count:,} duplicate rows**." if dup_count > 0 else "No duplicate rows found."
        if len(missing_df) == 0:
            return f"Data quality check: {dup_msg} No missing values were detected in any column."
        else:
            missing_cols = [
                f"{row['Column']} ({int(row['Missing_Count']):,} missing)"
                for _, row in missing_df.iterrows()
            ]
            return f"Data quality check: {dup_msg} Missing values detected in: {', '.join(missing_cols)}."

    # 7. Dataset Summary
    if res_type == "summary":
        return "Statistical summary generated. Please refer to the computed metrics table below for detailed distribution percentiles."

    return "Analysis complete. Detailed results are displayed below."
