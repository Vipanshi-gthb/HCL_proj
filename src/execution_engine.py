"""Deterministic Pandas Execution Engine for P_123.

Follows P123_ARCHITECTURE.md sections 6.1 and 11:
- Deterministic, fixed Pandas code paths only.
- ZERO use of exec(), eval(), compile(), or unsafe attribute reflection.
- Generates transparent, formatted equivalent Pandas code string for display only.
- Handles empty filter results gracefully.
"""

from dataclasses import dataclass
from typing import Any, Optional, Literal, Union, List, Tuple
import pandas as pd
import numpy as np

from src.errors import ExecutionError
from src.query_planner import QueryPlan, FilterSpec


ResultType = Literal["scalar", "series", "dataframe", "summary", "quality", "empty", "unsupported"]


@dataclass
class ExecutionResult:
    data: Any
    result_type: ResultType
    plan: QueryPlan
    pandas_code: str
    row_count: int = 0
    full_ranking_for_chart: Optional[Any] = None


def _apply_filters(df: pd.DataFrame, filters: List[FilterSpec]) -> Tuple[pd.DataFrame, List[str]]:
    """Applies filter specifications deterministically to the DataFrame."""
    filtered_df = df
    code_snippets = []

    for f in filters:
        col = f.column
        op = f.op
        vals = f.values

        if not vals and op not in ("isna", "notna"):
            continue

        if op == "eq":
            v = vals[0]
            if pd.api.types.is_numeric_dtype(df[col]):
                try:
                    num_v = float(v)
                    filtered_df = filtered_df[filtered_df[col] == num_v]
                    code_snippets.append(f"df = df[df['{col}'] == {num_v}]")
                except ValueError:
                    filtered_df = filtered_df[filtered_df[col].astype(str) == str(v)]
                    code_snippets.append(f"df = df[df['{col}'].astype(str) == '{v}']")
            else:
                filtered_df = filtered_df[filtered_df[col].astype(str).str.lower() == str(v).lower()]
                code_snippets.append(f"df = df[df['{col}'].str.lower() == '{v.lower()}']")

        elif op == "ne":
            v = vals[0]
            filtered_df = filtered_df[filtered_df[col].astype(str).str.lower() != str(v).lower()]
            code_snippets.append(f"df = df[df['{col}'].str.lower() != '{v.lower()}']")

        elif op in ("gt", "gte", "lt", "lte"):
            try:
                num_v = float(vals[0])
                if op == "gt":
                    filtered_df = filtered_df[filtered_df[col] > num_v]
                    code_snippets.append(f"df = df[df['{col}'] > {num_v}]")
                elif op == "gte":
                    filtered_df = filtered_df[filtered_df[col] >= num_v]
                    code_snippets.append(f"df = df[df['{col}'] >= {num_v}]")
                elif op == "lt":
                    filtered_df = filtered_df[filtered_df[col] < num_v]
                    code_snippets.append(f"df = df[df['{col}'] < {num_v}]")
                elif op == "lte":
                    filtered_df = filtered_df[filtered_df[col] <= num_v]
                    code_snippets.append(f"df = df[df['{col}'] <= {num_v}]")
            except ValueError:
                pass

        elif op == "in":
            lower_vals = [str(x).lower() for x in vals]
            filtered_df = filtered_df[filtered_df[col].astype(str).str.lower().isin(lower_vals)]
            code_snippets.append(f"df = df[df['{col}'].isin({vals})]")

        elif op == "contains":
            pattern = str(vals[0])
            filtered_df = filtered_df[filtered_df[col].astype(str).str.contains(pattern, case=False, na=False)]
            code_snippets.append(f"df = df[df['{col}'].str.contains('{pattern}', case=False, na=False)]")

        elif op == "between" and len(vals) >= 2:
            try:
                low, high = float(vals[0]), float(vals[1])
                filtered_df = filtered_df[filtered_df[col].between(low, high)]
                code_snippets.append(f"df = df[df['{col}'].between({low}, {high})]")
            except ValueError:
                pass

    return filtered_df, code_snippets


def execute_plan(plan: QueryPlan, df: pd.DataFrame) -> ExecutionResult:
    """Executes a validated QueryPlan deterministically against a pandas DataFrame."""
    if plan.operation == "unsupported":
        reason = plan.unsupported_reason or "This type of analysis is not currently supported."
        return ExecutionResult(
            data=reason,
            result_type="unsupported",
            plan=plan,
            pandas_code="# Operation is marked unsupported by planner\nresult = None",
        )

    try:
        # Step 1: Filter evaluation
        filtered_df, filter_code = _apply_filters(df, plan.filters)
        code_lines = ["import pandas as pd", ""]
        if filter_code:
            code_lines.extend(filter_code)

        if filtered_df.empty:
            code_lines.append("result = 'No matching records found after filtering.'")
            return ExecutionResult(
                data="No matching records found.",
                result_type="empty",
                plan=plan,
                pandas_code="\n".join(code_lines),
                row_count=0,
            )

        # Step 2: Deterministic operations
        op = plan.operation
        metric = plan.metric_column
        agg = plan.aggregation or "sum"
        ascending = (plan.sort_order == "asc")

        # 1. Dataset Summary
        if op == "dataset_summary":
            num_df = filtered_df.describe().round(2)
            code_lines.append("result = df.describe().round(2)")
            return ExecutionResult(
                data=num_df,
                result_type="summary",
                plan=plan,
                pandas_code="\n".join(code_lines),
                row_count=len(num_df),
            )

        # 2. Data Quality
        elif op == "data_quality":
            missing_counts = filtered_df.isna().sum()
            dup_count = int(filtered_df.duplicated().sum())
            quality_df = pd.DataFrame({
                "Column": missing_counts.index,
                "Missing_Count": missing_counts.values,
                "Missing_Pct": (missing_counts.values / len(filtered_df) * 100).round(2),
            })
            quality_df = quality_df[quality_df["Missing_Count"] > 0]
            summary_info = {
                "missing_table": quality_df,
                "duplicate_count": dup_count,
                "total_rows": len(filtered_df),
            }
            code_lines.append("missing_counts = df.isna().sum()")
            code_lines.append("duplicate_count = df.duplicated().sum()")
            code_lines.append("result = {'missing': missing_counts, 'duplicates': duplicate_count}")
            return ExecutionResult(
                data=summary_info,
                result_type="quality",
                plan=plan,
                pandas_code="\n".join(code_lines),
                row_count=len(quality_df),
            )

        # 3. Scalar Aggregate
        elif op == "scalar_aggregate":
            if agg == "sum":
                val = filtered_df[metric].sum()
            elif agg == "mean":
                val = filtered_df[metric].mean()
            elif agg == "median":
                val = filtered_df[metric].median()
            elif agg == "min":
                val = filtered_df[metric].min()
            elif agg == "max":
                val = filtered_df[metric].max()
            elif agg == "count":
                val = filtered_df[metric].count()
            elif agg == "nunique":
                val = filtered_df[metric].nunique()
            else:
                val = filtered_df[metric].agg(agg)
            # Round float values
            if isinstance(val, (float, np.floating)):
                val = round(float(val), 2)
            elif isinstance(val, (int, np.integer)):
                val = int(val)
            code_lines.append(f"result = df['{metric}'].{agg}()")
            return ExecutionResult(
                data=val,
                result_type="scalar",
                plan=plan,
                pandas_code="\n".join(code_lines),
                row_count=1,
            )

        # 4. Group Aggregate
        elif op == "group_aggregate":
            groups = plan.group_by
            if len(groups) == 1:
                series = filtered_df.groupby(groups[0])[metric].agg(agg).sort_values(ascending=ascending)
                if isinstance(series, pd.Series):
                    series = series.round(2)
                code_lines.append(
                    f"result = df.groupby('{groups[0]}')['{metric}'].{agg}().sort_values(ascending={ascending})"
                )
                return ExecutionResult(
                    data=series,
                    result_type="series",
                    plan=plan,
                    pandas_code="\n".join(code_lines),
                    row_count=len(series),
                )
            else:
                grouped_df = filtered_df.groupby(groups)[metric].agg(agg).unstack().round(2)
                code_lines.append(
                    f"result = df.groupby({groups})['{metric}'].{agg}().unstack().round(2)"
                )
                return ExecutionResult(
                    data=grouped_df,
                    result_type="dataframe",
                    plan=plan,
                    pandas_code="\n".join(code_lines),
                    row_count=len(grouped_df),
                )

        # 5. Top N
        elif op == "top_n":
            groups = plan.group_by
            limit = plan.limit
            if groups:
                full_grouped = filtered_df.groupby(groups[0])[metric].agg(agg).sort_values(ascending=ascending).round(2)
                top_slice = full_grouped.head(limit)
                code_lines.append(
                    f"full_ranking = df.groupby('{groups[0]}')['{metric}'].{agg}().sort_values(ascending={ascending})\nresult = full_ranking.head({limit})"
                )
                return ExecutionResult(
                    data=top_slice,
                    result_type="series",
                    plan=plan,
                    pandas_code="\n".join(code_lines),
                    row_count=len(top_slice),
                    full_ranking_for_chart=full_grouped.head(15),
                )
            else:
                top_df = filtered_df.sort_values(by=metric, ascending=ascending).head(limit)
                code_lines.append(f"result = df.sort_values(by='{metric}', ascending={ascending}).head({limit})")
                return ExecutionResult(
                    data=top_df,
                    result_type="dataframe",
                    plan=plan,
                    pandas_code="\n".join(code_lines),
                    row_count=len(top_df),
                )

        # 6. Time Series
        elif op == "time_series":
            time_col = plan.time_column
            grain = plan.time_grain or "month"
            freq_map = {
                "day": "D",
                "week": "W",
                "month": "M",
                "quarter": "Q",
                "year": "Y",
            }
            period_freq = freq_map.get(grain, "M")

            # Group by Period for cleaner time series representations
            period_series = filtered_df[time_col].dt.to_period(period_freq)
            ts = filtered_df.groupby(period_series)[metric].agg(agg).round(2)
            ts.index = ts.index.astype(str)
            code_lines.append(
                f"result = df.groupby(df['{time_col}'].dt.to_period('{period_freq}'))['{metric}'].{agg}()"
            )
            return ExecutionResult(
                data=ts,
                result_type="series",
                plan=plan,
                pandas_code="\n".join(code_lines),
                row_count=len(ts),
            )

        # 7. Value Counts
        elif op == "value_counts":
            col = plan.group_by[0] if plan.group_by else (plan.metric_column or filtered_df.columns[0])
            counts = filtered_df[col].value_counts().head(plan.limit)
            code_lines.append(f"result = df['{col}'].value_counts().head({plan.limit})")
            return ExecutionResult(
                data=counts,
                result_type="series",
                plan=plan,
                pandas_code="\n".join(code_lines),
                row_count=len(counts),
            )

        else:
            raise ExecutionError(f"Unhandled operation '{op}'.")

    except Exception as e:
        if isinstance(e, ExecutionError):
            raise
        raise ExecutionError(f"Execution failed on dataset: {str(e)}")
