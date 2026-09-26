from __future__ import annotations

from typing import Any

from core.config import Settings, load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def run_phase1_pipeline(settings: Settings) -> dict[str, Any]:
    """Run the clean baseline pipeline and return its main results."""
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        raw_records = fetch_source_records(settings)
    else:
        raw_records = load_raw_records(settings.paths.raw_records_json)

    clean_df = build_clean_dataframe(raw_records, now_utc())
    if clean_df.empty:
        raise ValueError("Cleaning produced no records, so the baseline pipeline cannot continue.")

    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(
        clean_df,
        settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )

    should_rebuild_test_set = (
        settings.refresh_source
        or settings.refresh_test_set
        or not settings.paths.eval_testset.exists()
    )
    if should_rebuild_test_set:
        build_test_set(clean_df, settings.paths.eval_testset)

    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)

    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "raw_records": len(raw_records),
        "clean_records": len(clean_df),
        "collection_name": index.collection_name,
        "indexed_documents": index.collection.count(),
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

    return {
        "source": source_summary,
        "metrics": evaluation.summary,
        "quality": quality,
        "freshness": freshness,
        "report_path": str(settings.paths.baseline_report),
    }


def main() -> None:
    result = run_phase1_pipeline(load_settings())
    source = result["source"]
    metrics = result["metrics"]
    print(
        f"Baseline complete: {source['clean_records']} clean rows, "
        f"{source['indexed_documents']} indexed documents."
    )
    print(f"Retrieval hit rate: {metrics['retrieval_hit_rate']:.3f}")
    print(f"Mean token F1: {metrics['mean_token_f1']:.3f}")
    print(f"Quality gate passed: {result['quality']['success']}")
    print(f"Report: {result['report_path']}")
