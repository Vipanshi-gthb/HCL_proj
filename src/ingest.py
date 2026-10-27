"""CSV Ingestion and Validation module for P_123.

Follows P123_ARCHITECTURE.md section 5.2 and requirements:
- .csv extension and file existence validation
- Max file size enforcement (MAX_UPLOAD_MB)
- Empty-file and binary-file rejection
- Encoding fallback: utf-8 -> utf-8-sig -> latin-1
- Header stripping and de-duplication
- Row cap (truncates with warning) and Column cap (rejects if exceeded)
- Safe date parsing for columns containing 'date' or 'time' (>=80% success rule)
"""

import os
from dataclasses import dataclass, field
from typing import List, Tuple
import pandas as pd
from src.errors import UploadError


@dataclass
class IngestReport:
    row_count: int
    col_count: int
    truncated: bool = False
    original_row_count: int = 0
    date_columns_parsed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def load_csv(
    file_path: str,
    max_upload_mb: int = 10,
    max_rows: int = 200000,
    max_cols: int = 100,
) -> Tuple[pd.DataFrame, IngestReport]:
    """Validates and loads a CSV file into a pandas DataFrame.

    Raises UploadError if the file is invalid, oversized, empty, binary, or unparseable.
    """
    if not file_path or not os.path.exists(file_path):
        raise UploadError("The specified file does not exist.")

    if not file_path.lower().endswith(".csv"):
        raise UploadError("Unsupported file format. Please upload a .csv file.")

    try:
        file_size = os.path.getsize(file_path)
    except OSError as e:
        raise UploadError(f"Could not read file size: {str(e)}")

    if file_size == 0:
        raise UploadError("The uploaded CSV file is empty (0 bytes).")

    max_bytes = max_upload_mb * 1024 * 1024
    if file_size > max_bytes:
        raise UploadError(
            f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds the {max_upload_mb} MB limit."
        )

    # Check for binary content in the first 2KB
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(2048)
            if b"\x00" in chunk:
                raise UploadError("The uploaded file appears to be a binary file, not a valid CSV.")
    except UploadError:
        raise
    except Exception as e:
        raise UploadError(f"Error inspecting file contents: {str(e)}")

    # Encoding fallback: utf-8 -> utf-8-sig -> latin-1
    encodings = ["utf-8", "utf-8-sig", "latin-1"]
    df = None
    last_error = None

    for enc in encodings:
        try:
            df = pd.read_csv(file_path, encoding=enc)
            break
        except (UnicodeDecodeError, pd.errors.ParserError) as e:
            last_error = e
            continue
        except Exception as e:
            raise UploadError(f"Failed to parse CSV file: {str(e)}")

    if df is None:
        raise UploadError(f"Could not parse CSV with supported encodings (utf-8, latin-1): {str(last_error)}")

    if df.empty and len(df.columns) == 0:
        raise UploadError("The CSV file contains no data or columns.")

    # Strip and de-duplicate column headers
    import re
    raw_columns = [re.sub(r"\s*\.\d+$", "", str(c).strip()).strip() for c in df.columns]
    seen = {}
    deduped_columns = []
    for c in raw_columns:
        if not c or c.startswith("Unnamed:"):
            c = "unnamed"
        if c in seen:
            seen[c] += 1
            deduped_columns.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            deduped_columns.append(c)
    df.columns = deduped_columns

    # Enforce Column Cap
    if len(df.columns) > max_cols:
        raise UploadError(
            f"Dataset has {len(df.columns)} columns, exceeding maximum allowed limit of {max_cols}."
        )

    warnings: List[str] = []
    original_rows = len(df)
    truncated = False

    # Enforce Row Cap
    if original_rows > max_rows:
        df = df.iloc[:max_rows].copy()
        truncated = True
        warnings.append(
            f"Dataset truncated from {original_rows:,} rows to {max_rows:,} rows maximum limit."
        )

    # Safe Date Parsing (SRS FR-1.2): 80% non-null threshold
    date_columns_parsed: List[str] = []
    for col in df.columns:
        col_lower = col.lower()
        if ("date" in col_lower or "time" in col_lower) and not pd.api.types.is_datetime64_any_dtype(df[col]):
            if not pd.api.types.is_numeric_dtype(df[col]):
                non_null_count = df[col].notna().sum()
                if non_null_count > 0:
                    parsed = pd.to_datetime(df[col], errors="coerce")
                    valid_parsed_count = parsed.notna().sum()
                    if valid_parsed_count / non_null_count >= 0.80:
                        df[col] = parsed
                        date_columns_parsed.append(col)

    report = IngestReport(
        row_count=len(df),
        col_count=len(df.columns),
        truncated=truncated,
        original_row_count=original_rows,
        date_columns_parsed=date_columns_parsed,
        warnings=warnings,
    )

    return df, report
