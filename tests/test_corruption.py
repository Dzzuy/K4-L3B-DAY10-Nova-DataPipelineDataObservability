from __future__ import annotations

import json

import pandas as pd
import pytest

from ingestion.corruption import NOISE_TEXT, corrupt_clean_dataframe


def _clean_dataframe(row_count: int = 24) -> pd.DataFrame:
    rows = []
    for index in range(row_count):
        published = pd.Timestamp("2026-09-01") - pd.Timedelta(days=index)
        summary = f"Summary for paper {index} with enough content for data quality checks."
        rows.append(
            {
                "paper_id": f"paper-{index:02d}",
                "title": f"A sufficiently descriptive paper title {index}",
                "summary": summary,
                "authors_joined": "Author One, Author Two",
                "categories_joined": "Artificial Intelligence, Retrieval",
                "published": published.date().isoformat(),
                "updated": published.date().isoformat(),
                "age_days": index + 1,
                "summary_chars": len(summary),
                "text_for_embedding": f"Original embedding text {index}",
                "abs_url": f"https://example.com/{index}",
                "pdf_url": f"https://example.com/{index}.pdf",
            }
        )
    return pd.DataFrame(rows)


def test_corrupt_clean_dataframe_applies_all_scenarios(tmp_path):
    clean = _clean_dataframe()
    original = clean.copy(deep=True)
    log_path = tmp_path / "corruption_log.json"

    corrupted = corrupt_clean_dataframe(clean, log_path)
    log = json.loads(log_path.read_text(encoding="utf-8"))
    scenarios = {item["name"]: item for item in log["scenarios"]}

    pd.testing.assert_frame_equal(clean, original)
    assert log["scenario_count"] == 6
    assert set(scenarios) == {
        "drop_latest_records",
        "blank_summary",
        "inject_noise",
        "truncate_title",
        "stale_publication_date",
        "duplicate_rows",
    }
    assert all(item["affected_count"] > 0 for item in scenarios.values())
    assert scenarios["drop_latest_records"]["affected_count"] == 5
    assert scenarios["drop_latest_records"]["paper_ids"] == [
        "paper-00",
        "paper-01",
        "paper-02",
        "paper-03",
        "paper-04",
    ]
    assert scenarios["stale_publication_date"]["affected_count"] == 6
    assert scenarios["duplicate_rows"]["affected_count"] == 2
    assert log["row_count_before"] == 24
    assert log["row_count_after"] == 21
    assert corrupted["paper_id"].duplicated().any()
    assert (corrupted["summary"] == "").any()
    assert corrupted["summary"].str.contains(NOISE_TEXT, regex=False).any()
    assert (corrupted["title"].str.len() == 7).any()
    assert (corrupted["age_days"] > original["age_days"].max()).any()
    assert (corrupted["summary_chars"] == corrupted["summary"].str.len()).all()

    for change in scenarios["stale_publication_date"]["changes"]:
        before = pd.Timestamp(change["before"])
        after = pd.Timestamp(change["after"])
        assert (before - after).days == 365

    affected_ids = {
        paper_id
        for scenario in scenarios.values()
        if scenario["name"] not in {"drop_latest_records", "duplicate_rows"}
        for paper_id in scenario["paper_ids"]
    }
    unaffected = corrupted[
        ~corrupted["paper_id"].isin(affected_ids)
        & ~corrupted["paper_id"].duplicated(keep=False)
    ]
    original_text = original.set_index("paper_id")["text_for_embedding"]
    for row in unaffected.itertuples():
        assert row.text_for_embedding == original_text[row.paper_id]


def test_corruption_is_deterministic(tmp_path):
    clean = _clean_dataframe()

    first = corrupt_clean_dataframe(clean, tmp_path / "first.json")
    second = corrupt_clean_dataframe(clean, tmp_path / "second.json")

    pd.testing.assert_frame_equal(first, second)
    assert (tmp_path / "first.json").read_text(encoding="utf-8") == (
        tmp_path / "second.json"
    ).read_text(encoding="utf-8")


def test_corruption_rejects_missing_columns(tmp_path):
    clean = _clean_dataframe().drop(columns=["summary"])

    with pytest.raises(ValueError, match="Missing required columns: summary"):
        corrupt_clean_dataframe(clean, tmp_path / "corruption_log.json")


def test_corruption_rejects_empty_dataframe(tmp_path):
    clean = _clean_dataframe().iloc[0:0]

    with pytest.raises(ValueError, match="empty dataframe"):
        corrupt_clean_dataframe(clean, tmp_path / "corruption_log.json")
