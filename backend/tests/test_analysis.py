from io import BytesIO

import pandas as pd
import pytest
from openpyxl import Workbook

from app.analysis.engine import analyze
from app.analysis.profile import profile_dataframe
from app.ingestion import parse_dataset


def test_profile_counts_missing_duplicates_and_numeric_stats():
    df = pd.DataFrame({"revenue": [10, 20, None, 10], "region": ["N", "S", "S", "N"]})
    p = profile_dataframe(df)
    assert p["row_count"] == 4 and p["duplicate_rows"] == 1
    assert p["missing_cells"] == 1 and p["columns"][0]["mean"] == pytest.approx(13.3333)


def test_upload_csv_parsing_and_invalid_file():
    df = parse_dataset("small.csv", b"region,revenue\nWest,12\nEast,14\n")
    assert list(df.columns) == ["region", "revenue"] and len(df) == 2
    with pytest.raises(ValueError):
        parse_dataset("bad.xlsx", b"not an excel workbook")


def test_xlsx_ingestion():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["region", "revenue"])
    sheet.append(["North", 25])
    buffer = BytesIO()
    workbook.save(buffer)
    frame = parse_dataset("sample.xlsx", buffer.getvalue())
    assert frame.iloc[0].to_dict() == {"region": "North", "revenue": 25}


def test_top_categories_uses_real_data_and_chart_contract():
    df = pd.DataFrame({"category": ["A", "B", "A"], "revenue": [10, 20, 30]})
    result = analyze(df, "What are the top 2 categories by revenue? Plot it")
    assert result["result"] == [{"label": "A", "value": 40.0}, {"label": "B", "value": 20.0}]
    assert result["visualization"]["type"] == "bar"


def test_row_count_question():
    result = analyze(pd.DataFrame({"x": [1, 2, 3]}), "How many rows are in the dataset?")
    assert result["result"]["rows"] == 3


def test_analysis_worker_returns_structured_result():
    from app.execution.runner import execute_analysis

    result = execute_analysis(
        [{"category": "A", "revenue": 5}], ["category", "revenue"], "average revenue"
    )
    assert result["result"]["average"] == 5


def test_monthly_revenue_and_followup_chart():
    frame = pd.DataFrame(
        {
            "date": ["2025-01-02", "2025-01-20", "2025-02-03"],
            "revenue": [10, 20, 5],
            "region": ["West", "East", "West"],
        }
    )
    first = analyze(frame, "Plot monthly revenue")
    assert first["result"][0]["revenue"] == 30
    followup = analyze(frame, "Show that as a chart", first)
    assert followup["visualization"] is not None


def test_iqr_anomaly_detection_discloses_method():
    result = analyze(pd.DataFrame({"sales": [10, 11, 12, 13, 1000]}), "Find unusual sales values")
    assert result["result"]["method"] == "IQR"
    assert result["result"]["count"] == 1


def test_correlation_serializes_constant_columns_as_null():
    from app.execution.runner import execute_analysis

    result = execute_analysis(
        [{"constant": 1, "changing": 2}, {"constant": 1, "changing": 4}],
        ["constant", "changing"],
        "Show the correlation",
    )
    assert result["analysis_type"] == "correlation"
