"""Schema Extractor and Dataset Overview module for P_123.

Enforces data isolation guardrails (P123_ARCHITECTURE.md sections 5.3, 10):
- Extracts column names, pandas dtype strings, and coarse 'kind' classification.
- NEVER samples or passes cell values into the Schema sent to Gemini.
- Prepares DatasetOverview for display in the local UI only.
"""

from typing import List, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import pandas as pd


Kind = Literal["numeric", "categorical", "datetime", "text", "bool"]


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    kind: Kind


class Schema(BaseModel):
    columns: List[ColumnInfo] = Field(default_factory=list)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to simple dict suitable for JSON serialization in LLM prompt."""
        return {
            "columns": [col.model_dump() for col in self.columns]
        }


class DatasetOverview(BaseModel):
    row_count: int
    col_count: int
    duplicate_rows: int
    total_missing_cells: int
    dtypes_summary: List[Dict[str, Any]]
    preview_records: List[Dict[str, Any]]

    model_config = ConfigDict(arbitrary_types_allowed=True)


def determine_kind(dtype: Any) -> Kind:
    """Derives a coarse data kind strictly from pandas dtype without inspecting cell values."""
    if pd.api.types.is_bool_dtype(dtype):
        return "bool"
    if pd.api.types.is_datetime64_any_dtype(dtype) or pd.api.types.is_timedelta64_dtype(dtype):
        return "datetime"
    if pd.api.types.is_numeric_dtype(dtype):
        return "numeric"
    # Object or string dtypes are classified as categorical
    return "categorical"


def extract_schema(df: pd.DataFrame) -> Schema:
    """Extracts schema containing ONLY column names, dtypes, and kinds.

    CRITICAL PRIVACY GUARANTEE: Does not inspect, sample, or include any row/cell values.
    """
    cols: List[ColumnInfo] = []
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        kind = determine_kind(df[col].dtype)
        cols.append(ColumnInfo(name=str(col), dtype=dtype_str, kind=kind))
    return Schema(columns=cols)


def create_dataset_overview(df: pd.DataFrame) -> DatasetOverview:
    """Generates an inspection summary of the dataset for the user's browser UI only.

    This summary is NEVER transmitted to external LLMs.
    """
    row_count = len(df)
    col_count = len(df.columns)
    duplicate_rows = int(df.duplicated().sum())
    total_missing = int(df.isna().sum().sum())

    dtypes_summary = []
    for col in df.columns:
        missing = int(df[col].isna().sum())
        missing_pct = round((missing / row_count * 100), 1) if row_count > 0 else 0.0
        dtypes_summary.append({
            "Column": str(col),
            "Type": str(df[col].dtype),
            "Kind": determine_kind(df[col].dtype),
            "Missing": missing,
            "Missing %": f"{missing_pct}%",
        })

    # Prepare preview of first 10 rows (converting timestamps/dates to string for JSON serialization)
    preview_df = df.head(10).copy()
    for col in preview_df.columns:
        if pd.api.types.is_datetime64_any_dtype(preview_df[col]):
            preview_df[col] = preview_df[col].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
        else:
            preview_df[col] = preview_df[col].astype(str)

    preview_records = preview_df.to_dict(orient="records")

    return DatasetOverview(
        row_count=row_count,
        col_count=col_count,
        duplicate_rows=duplicate_rows,
        total_missing_cells=total_missing,
        dtypes_summary=dtypes_summary,
        preview_records=preview_records,
    )
