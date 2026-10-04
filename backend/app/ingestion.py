from io import BytesIO
from pathlib import Path

import pandas as pd


def parse_dataset(filename: str, content: bytes) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError("Unsupported file type. Upload a .csv or .xlsx file.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    try:
        frame = (
            pd.read_csv(BytesIO(content))
            if suffix == ".csv"
            else pd.read_excel(BytesIO(content), engine="openpyxl")
        )
    except Exception as exc:
        raise ValueError(
            "The file could not be parsed. Check that it is a valid CSV or Excel workbook."
        ) from exc
    if frame.empty or len(frame.columns) == 0:
        raise ValueError("The dataset contains no data rows or columns.")
    frame.columns = [str(c).strip() for c in frame.columns]
    if any(not c for c in frame.columns) or len(set(frame.columns)) != len(frame.columns):
        raise ValueError("Column names must be non-empty and unique.")
    return frame
