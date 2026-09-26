from __future__ import annotations

from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json


DROP_LATEST_RATIO = 0.20
FIELD_CORRUPTION_RATIO = 0.15
STALE_RATIO = 0.30
DUPLICATE_RATIO = 0.10
STALE_DAYS = 365
NOISE_TEXT = " [CORRUPTED_NOISE] !!! ### @@"


def _sample_count(row_count: int, ratio: float) -> int:
    return min(row_count, max(1, ceil(row_count * ratio))) if row_count else 0


def _paper_ids(df: pd.DataFrame, indices: list[int]) -> list[str]:
    return [str(df.at[index, "paper_id"]) for index in indices]


def _rebuild_text_for_embedding(df: pd.DataFrame, indices: list[int]) -> None:
    def build_text(row: pd.Series) -> str:
        return "\n".join(
            [
                f"Title: {row.get('title', '')}",
                f"Authors: {row.get('authors_joined', '')}",
                f"Categories: {row.get('categories_joined', '')}",
                f"Published: {row.get('published', '')}",
                f"Summary: {row.get('summary', '')}",
            ]
        )

    df.loc[indices, "text_for_embedding"] = df.loc[indices].apply(build_text, axis=1)


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path) -> pd.DataFrame:
    """Apply the six required deterministic corruption scenarios.

    The input dataframe is never modified. Records for field-level corruptions are
    selected by sorted paper ID so repeated runs produce the same result.
    """
    required_columns = {
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "categories_joined",
        "published",
        "age_days",
        "summary_chars",
        "text_for_embedding",
    }
    missing_columns = sorted(required_columns.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    row_count_before = len(corrupted)
    scenarios: list[dict[str, Any]] = []

    published_dates = pd.to_datetime(corrupted["published"], errors="coerce")
    if published_dates.isna().any():
        invalid_ids = corrupted.loc[published_dates.isna(), "paper_id"].astype(str).tolist()
        raise ValueError(f"Invalid published dates for paper IDs: {', '.join(invalid_ids)}")
    age_days = pd.to_numeric(corrupted["age_days"], errors="coerce")
    if age_days.isna().any():
        invalid_ids = corrupted.loc[age_days.isna(), "paper_id"].astype(str).tolist()
        raise ValueError(f"Invalid age_days for paper IDs: {', '.join(invalid_ids)}")
    corrupted["age_days"] = age_days.astype(int)
    latest_order = (
        pd.DataFrame(
            {
                "index": corrupted.index,
                "published": published_dates,
                "paper_id": corrupted["paper_id"].astype(str),
            }
        )
        .sort_values(["published", "paper_id"], ascending=[False, True], na_position="last")
        ["index"]
        .tolist()
    )
    drop_count = min(
        _sample_count(row_count_before, DROP_LATEST_RATIO),
        max(0, row_count_before - 1),
    )
    dropped_indices = latest_order[:drop_count]
    dropped_ids = _paper_ids(corrupted, dropped_indices)
    corrupted = corrupted.drop(index=dropped_indices).reset_index(drop=True)
    scenarios.append(
        {
            "name": "drop_latest_records",
            "affected_count": len(dropped_ids),
            "paper_ids": dropped_ids,
            "parameters": {"ratio": DROP_LATEST_RATIO},
        }
    )

    stable_indices = corrupted.sort_values("paper_id", kind="stable").index.tolist()
    field_count = _sample_count(len(corrupted), FIELD_CORRUPTION_RATIO)
    stale_count = _sample_count(len(corrupted), STALE_RATIO)
    cursor = 0

    def take_indices(count: int) -> list[int]:
        nonlocal cursor
        if not stable_indices:
            return []
        selected = [
            stable_indices[(cursor + offset) % len(stable_indices)]
            for offset in range(count)
        ]
        cursor += count
        return selected

    blank_indices = take_indices(field_count)
    blank_changes = [
        {
            "paper_id": str(corrupted.at[index, "paper_id"]),
            "before": str(corrupted.at[index, "summary"]),
            "after": "",
        }
        for index in blank_indices
    ]
    corrupted.loc[blank_indices, "summary"] = ""
    scenarios.append(
        {
            "name": "blank_summary",
            "affected_count": len(blank_indices),
            "paper_ids": _paper_ids(corrupted, blank_indices),
            "changes": blank_changes,
        }
    )

    noise_indices = take_indices(field_count)
    noise_changes = []
    for index in noise_indices:
        before = str(corrupted.at[index, "summary"])
        after = f"{before}{NOISE_TEXT}"
        corrupted.at[index, "summary"] = after
        noise_changes.append(
            {
                "paper_id": str(corrupted.at[index, "paper_id"]),
                "before": before,
                "after": after,
            }
        )
    scenarios.append(
        {
            "name": "inject_noise",
            "affected_count": len(noise_indices),
            "paper_ids": _paper_ids(corrupted, noise_indices),
            "parameters": {"noise": NOISE_TEXT.strip()},
            "changes": noise_changes,
        }
    )

    title_indices = take_indices(field_count)
    title_changes = []
    for index in title_indices:
        before = str(corrupted.at[index, "title"])
        after = before[:7]
        corrupted.at[index, "title"] = after
        title_changes.append(
            {
                "paper_id": str(corrupted.at[index, "paper_id"]),
                "before": before,
                "after": after,
            }
        )
    scenarios.append(
        {
            "name": "truncate_title",
            "affected_count": len(title_indices),
            "paper_ids": _paper_ids(corrupted, title_indices),
            "parameters": {"maximum_length": 7},
            "changes": title_changes,
        }
    )

    stale_indices = take_indices(stale_count)
    stale_changes = []
    for index in stale_indices:
        before = str(corrupted.at[index, "published"])
        parsed = pd.to_datetime(before, errors="coerce")
        if pd.isna(parsed):
            continue
        after = (parsed - pd.Timedelta(days=STALE_DAYS)).date().isoformat()
        corrupted.at[index, "published"] = after
        corrupted.at[index, "age_days"] = (
            int(corrupted.at[index, "age_days"]) + STALE_DAYS
        )
        stale_changes.append(
            {
                "paper_id": str(corrupted.at[index, "paper_id"]),
                "before": before,
                "after": after,
            }
        )
    stale_ids = [change["paper_id"] for change in stale_changes]
    scenarios.append(
        {
            "name": "stale_publication_date",
            "affected_count": len(stale_changes),
            "paper_ids": stale_ids,
            "parameters": {"days_subtracted": STALE_DAYS, "target_ratio": STALE_RATIO},
            "changes": stale_changes,
        }
    )

    changed_indices = list(
        dict.fromkeys(blank_indices + noise_indices + title_indices + stale_indices)
    )
    corrupted.loc[changed_indices, "summary_chars"] = (
        corrupted.loc[changed_indices, "summary"].fillna("").astype(str).str.len()
    )
    _rebuild_text_for_embedding(corrupted, changed_indices)

    duplicate_count = _sample_count(len(corrupted), DUPLICATE_RATIO)
    duplicate_indices = stable_indices[:duplicate_count]
    duplicate_rows = corrupted.loc[duplicate_indices].copy(deep=True)
    duplicate_ids = duplicate_rows["paper_id"].astype(str).tolist()
    corrupted = pd.concat([corrupted, duplicate_rows], ignore_index=True)
    scenarios.append(
        {
            "name": "duplicate_rows",
            "affected_count": len(duplicate_rows),
            "paper_ids": duplicate_ids,
            "parameters": {"ratio": DUPLICATE_RATIO},
        }
    )

    write_json(
        Path(output_log_path),
        {
            "row_count_before": row_count_before,
            "row_count_after": len(corrupted),
            "scenario_count": len(scenarios),
            "scenarios": scenarios,
        },
    )
    return corrupted
