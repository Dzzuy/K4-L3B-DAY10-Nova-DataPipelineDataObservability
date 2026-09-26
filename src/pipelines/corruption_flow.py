from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _require_artifacts(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        formatted = "\n- ".join(missing)
        raise FileNotFoundError(
            "Run the baseline pipeline before the corruption flow. Missing artifacts:\n"
            f"- {formatted}"
        )


def _load_dataframe(path: Path) -> pd.DataFrame:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON record list in {path}.")
    return pd.DataFrame(payload)


def _serializable_records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _save_dataframe(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, _serializable_records(df))


def _baseline_run_date(baseline_df: pd.DataFrame):
    published = pd.to_datetime(baseline_df["published"], errors="coerce")
    age_days = pd.to_numeric(baseline_df["age_days"], errors="coerce")
    reference_dates = (published + pd.to_timedelta(age_days, unit="D")).dropna()
    if reference_dates.empty:
        raise ValueError("Cannot derive the baseline cleaning date for idempotent repair.")
    return reference_dates.mode().iloc[0].to_pydatetime()


def _print_comparison(
    baseline_metrics: dict,
    corrupted_metrics: dict,
    repaired_metrics: dict,
) -> None:
    metric_names = [
        "retrieval_hit_rate",
        "mean_token_f1",
        "judge_accuracy",
        "mean_judge_score",
    ]
    comparison = pd.DataFrame(
        [
            {
                "metric": metric,
                "baseline": baseline_metrics.get(metric),
                "corrupted": corrupted_metrics.get(metric),
                "repaired": repaired_metrics.get(metric),
            }
            for metric in metric_names
        ]
    )
    print("\nBaseline vs Corrupted vs Repaired")
    print(comparison.to_string(index=False))


def main() -> None:
    """Run deterministic corruption, evaluation, and repair from trusted raw data."""
    settings = load_settings()
    paths = settings.paths
    _require_artifacts(
        [
            paths.clean_json,
            paths.raw_records_json,
            paths.eval_testset,
            paths.baseline_metrics,
        ]
    )

    baseline_metrics = read_json(paths.baseline_metrics)
    baseline_df = _load_dataframe(paths.clean_json)

    print("Applying the six corruption scenarios...")
    corrupted_df = corrupt_clean_dataframe(baseline_df, paths.corruption_log)
    _save_dataframe(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)

    print("Building and evaluating the corrupted index...")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        embeddings_output_path=paths.corrupted_embeddings_json,
    )
    corrupted_evaluation = evaluate_pipeline(
        settings,
        corrupted_index,
        paths.eval_testset,
        paths.corrupted_metrics,
        paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        paths.quality_dir / "corrupted_freshness_report.json",
    )

    print("Repairing from the trusted raw snapshot...")
    repair_run_date = _baseline_run_date(baseline_df)
    repaired_df = build_clean_dataframe(
        load_raw_records(paths.raw_records_json),
        repair_run_date,
    )
    _save_dataframe(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)

    print("Building and evaluating the repaired index...")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        embeddings_output_path=paths.repaired_embeddings_json,
    )
    repaired_evaluation = evaluate_pipeline(
        settings,
        repaired_index,
        paths.eval_testset,
        paths.repaired_metrics,
        paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        paths.quality_dir / "repaired_freshness_report.json",
    )

    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_evaluation.summary,
        repaired_evaluation.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )
    _print_comparison(
        baseline_metrics,
        corrupted_evaluation.summary,
        repaired_evaluation.summary,
    )
    print(f"Comparison report written to {paths.comparison_report}")
