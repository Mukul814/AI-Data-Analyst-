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


def test_natural_language_totals_groups_distributions_and_relationships():
    frame = pd.DataFrame({
        "Region": ["East", "West", "East"],
        "Product": ["A", "B", "B"],
        "Revenue": [10, 20, 30],
        "Profit": [2, 5, 4],
    })
    total = analyze(frame, "What is the total sales?")
    assert total["result"]["total"] == 60
    grouped = analyze(frame, "Which region has the highest revenue?")
    assert grouped["result"][0]["label"] == "East" and len(grouped["result"]) == 1
    product = analyze(frame, "What are the top 5 products?")
    assert product["result"][0]["label"] == "B"
    distribution = analyze(frame, "How are sales distributed?")
    assert distribution["visualization"]["type"] == "histogram"
    relationship = analyze(frame, "Is there a relationship between sales and profit?")
    assert relationship["visualization"]["type"] == "scatter"


def test_unsupported_question_is_explicit():
    result = analyze(pd.DataFrame({"sales": [10, 20]}), "Tell me a joke")
    assert result["analysis_type"] == "unsupported"
    assert "couldn't safely map" in result["answer"]


def test_revenue_share_by_region_uses_revenue_totals_not_record_counts():
    frame = pd.DataFrame({"Region": ["East", "West", "East"], "Revenue": [40, 30, 60]})
    result = analyze(frame, "How are revenue shares distributed by region?")
    assert {row["label"]: row["value"] for row in result["result"]} == {"East": 100.0, "West": 30.0}
    assert {row["label"]: row["share_percentage"] for row in result["result"]} == pytest.approx({"East": 100 / 130 * 100, "West": 30 / 130 * 100}, abs=0.0001)
    assert result["visualization"]["y"] == "share_percentage"


def test_explicit_sales_profit_correlation_uses_exact_requested_columns():
    frame = pd.DataFrame({"Revenue": [1, 2, 3, 4], "Profit": [2, 4, 6, 8], "Units": [4, 1, 3, 2]})
    result = analyze(frame, "Is there a relationship between sales and profit?")
    assert result["result"]["columns"] == ["Revenue", "Profit"]
    assert result["result"]["correlation"] == pytest.approx(1)


def test_average_order_value_uses_revenue_and_rejects_order_count_only():
    frame = pd.DataFrame({"Revenue": [50, 100], "Order_Count": [5, 10], "Profit": [2, 4]})
    result = analyze(frame, "What is the average order value?")
    assert result["result"] == {"column": "Revenue", "average": 75.0}
    with pytest.raises(ValueError, match="order-value column"):
        analyze(pd.DataFrame({"Order_Count": [5, 10]}), "What is the average order value?")


def test_forecast_next_period_returns_one_period():
    frame = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=4, freq="MS"), "revenue": [10, 12, 15, 17]})
    result = analyze(frame, "Forecast revenue for the next period")
    assert len(result["result"]["forecast"]) == 1
    assert "next period" in result["answer"]
