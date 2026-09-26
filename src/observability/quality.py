from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import great_expectations as gx
import pandas as pd

from core.config import Settings


def evaluate_freshness_sla(
    df: pd.DataFrame,
    settings: Settings,
) -> dict[str, Any]:
    total_rows = len(df)

    if total_rows == 0:
        return {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "stale_ratio": 1.0,
            "is_fresh": False,
        }

    dates = pd.to_datetime(df["published"], errors="coerce", utc=True).dropna()
    if not dates.empty:
        latest = dates.max().strftime("%Y-%m-%d")
        oldest = dates.min().strftime("%Y-%m-%d")
    else:
        latest = None
        oldest = None

    threshold = settings.freshness_threshold_days
    now = pd.Timestamp.now(tz="UTC")

    if "age_days" in df.columns and not df["age_days"].isna().all():
        age_series = pd.to_numeric(df["age_days"], errors="coerce").fillna(9999)
    else:
        age_series = pd.Series([9999] * total_rows, index=df.index)

    if "published" in df.columns:
        pub_dates = pd.to_datetime(df["published"], errors="coerce", utc=True)
        pub_age = (now - pub_dates).dt.days.fillna(9999)
        age_series = age_series.combine(pub_age, max)

    stale_rows = int((age_series > threshold).sum())
    stale_ratio = stale_rows / total_rows
    is_fresh = bool(stale_ratio <= 0.25)

    return {
        "latest_published": latest,
        "oldest_published": oldest,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "is_fresh": is_fresh,
    }


def build_freshness_report(
    df: pd.DataFrame,
    settings: Settings,
    report_path: Path | str,
) -> dict[str, Any]:
    report = evaluate_freshness_sla(df, settings)

    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def run_data_quality_checks(
    df: pd.DataFrame,
    settings: Settings,
    stage: str = "test",
    report_name: str | None = None,
) -> dict[str, Any]:
    name = report_name or stage

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name="papers_suite")
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="title")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30)
    )

    validation_result = batch.validate(suite)

    freshness = evaluate_freshness_sla(df, settings)
    build_freshness_report(df, settings, settings.paths.freshness_report)

    checks = {}
    for r in validation_result.results:
        exp_type = r.expectation_config.type
        col = r.expectation_config.kwargs.get("column", "")
        if "row_count" in exp_type:
            checks["row_count"] = bool(r.success)
        elif "unique" in exp_type:
            checks[f"{col}_unique"] = bool(r.success)
        elif "lengths" in exp_type:
            checks[f"{col}_min_length"] = bool(r.success)
        elif "not_be_null" in exp_type:
            checks[f"{col}_not_null"] = bool(r.success)

    checks["freshness"] = bool(freshness.get("is_fresh", False))

    passed = bool(validation_result.success and freshness.get("is_fresh", False))

    result = {
        "report_name": name,
        "stage": name,
        "success": passed,
        "passed": passed,
        "gx_success": bool(validation_result.success),
        "total_rows": len(df),
        "checks": checks,
        "freshness": freshness,
    }

    settings.paths.quality_dir.mkdir(parents=True, exist_ok=True)
    report_file_name = name if name.endswith(".json") else f"{name}.json"
    report_path = settings.paths.quality_dir / report_file_name

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
