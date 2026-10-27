import os
import sys
import pytest
import pandas as pd

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(scope="session")
def sample_csv_path() -> str:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root_dir, "dataset", "P123_sample_ecommerce_dataset.csv")
    if not os.path.exists(path):
        fallback = os.path.join(root_dir, "P123_sample_ecommerce_dataset.csv")
        if os.path.exists(fallback):
            return fallback
        pytest.skip(f"Sample dataset not found at {path} or {fallback}")
    return path


@pytest.fixture(scope="session")
def sample_df(sample_csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(sample_csv_path)
    if "Order_Date" in df.columns:
        df["Order_Date"] = pd.to_datetime(df["Order_Date"])
    return df
