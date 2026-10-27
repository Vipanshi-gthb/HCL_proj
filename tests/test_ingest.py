"""Tests for CSV Ingestion and Validation module."""

import os
import tempfile
import pytest
import pandas as pd

from src.errors import UploadError
from src.ingest import load_csv


def test_load_valid_csv(sample_csv_path: str):
    df, report = load_csv(sample_csv_path)
    assert len(df) == 500
    assert len(df.columns) == 19
    assert report.truncated is False
    assert "Order_Date" in report.date_columns_parsed
    assert pd.api.types.is_datetime64_any_dtype(df["Order_Date"])


def test_reject_non_existent_file():
    with pytest.raises(UploadError) as exc:
        load_csv("non_existent_file.csv")
    assert "does not exist" in str(exc.value)


def test_reject_non_csv_extension():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"col1,col2\n1,2\n")
        tmp_name = f.name
    try:
        with pytest.raises(UploadError) as exc:
            load_csv(tmp_name)
        assert "upload a .csv file" in str(exc.value)
    finally:
        os.remove(tmp_name)


def test_reject_empty_file():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        tmp_name = f.name
    try:
        with pytest.raises(UploadError) as exc:
            load_csv(tmp_name)
        assert "empty (0 bytes)" in str(exc.value)
    finally:
        os.remove(tmp_name)


def test_reject_binary_file():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"\x00\x01\x02\x03\x04binarydata")
        tmp_name = f.name
    try:
        with pytest.raises(UploadError) as exc:
            load_csv(tmp_name)
        assert "binary file" in str(exc.value)
    finally:
        os.remove(tmp_name)


def test_reject_oversized_file():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        # Write 2 MB into a temp file
        f.write(b"a" * (2 * 1024 * 1024))
        tmp_name = f.name
    try:
        # Setting max_upload_mb=1 should reject
        with pytest.raises(UploadError) as exc:
            load_csv(tmp_name, max_upload_mb=1)
        assert "exceeds the 1 MB limit" in str(exc.value)
    finally:
        os.remove(tmp_name)


def test_encoding_fallback_latin1():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        # Write text with Latin-1 specific characters like é (\xe9)
        f.write("City,Revenue\nMünchen,1500\nMontréal,2300\n".encode("latin-1"))
        tmp_name = f.name
    try:
        df, report = load_csv(tmp_name)
        assert len(df) == 2
        assert "München" in df["City"].values or "Munchen" in df["City"].values or df["City"].iloc[0] == "München"
    finally:
        os.remove(tmp_name)


def test_header_stripping_and_deduplication():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b" Name , Age , Name , \nAlice,25,Smith,Extra\n")
        tmp_name = f.name
    try:
        df, report = load_csv(tmp_name)
        expected_cols = ["Name", "Age", "Name_1", "unnamed"]
        assert list(df.columns) == expected_cols
    finally:
        os.remove(tmp_name)


def test_column_cap_rejection():
    # Generate CSV with 15 columns, set max_cols=10
    cols = [f"Col_{i}" for i in range(15)]
    header = ",".join(cols) + "\n"
    row = ",".join(["1"] * 15) + "\n"
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write((header + row).encode("utf-8"))
        tmp_name = f.name
    try:
        with pytest.raises(UploadError) as exc:
            load_csv(tmp_name, max_cols=10)
        assert "exceeding maximum allowed limit of 10" in str(exc.value)
    finally:
        os.remove(tmp_name)


def test_row_cap_truncation_warning():
    # Generate CSV with 20 rows, set max_rows=5
    content = "ID,Value\n" + "\n".join(f"{i},{i*10}" for i in range(20)) + "\n"
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(content.encode("utf-8"))
        tmp_name = f.name
    try:
        df, report = load_csv(tmp_name, max_rows=5)
        assert len(df) == 5
        assert report.truncated is True
        assert any("truncated from 20 rows to 5 rows" in w for w in report.warnings)
    finally:
        os.remove(tmp_name)


def test_date_parsing_threshold_rejection():
    # Column named 'Event_Date', but only 10% valid dates -> must not parse
    content = "Event_Date,Score\n2024-01-01,10\nnot-a-date,20\ninvalid,30\nrandom,40\ntext,50\n"
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(content.encode("utf-8"))
        tmp_name = f.name
    try:
        df, report = load_csv(tmp_name)
        # Should not be parsed as datetime
        assert not pd.api.types.is_datetime64_any_dtype(df["Event_Date"])
        assert "Event_Date" not in report.date_columns_parsed
    finally:
        os.remove(tmp_name)
