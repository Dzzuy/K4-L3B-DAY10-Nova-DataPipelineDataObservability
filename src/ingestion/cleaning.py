from __future__ import annotations

from datetime import UTC, datetime
from html import unescape
import json
import re
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize raw paper records into a deterministic, embedding-ready dataframe."""
    columns = [
        "paper_id",
        "title",
        "summary",
        "authors",
        "categories",
        "primary_category",
        "published",
        "updated",
        "abs_url",
        "pdf_url",
        "comment",
        "authors_joined",
        "categories_joined",
        "summary_chars",
        "age_days",
        "text_for_embedding",
    ]
    if not records:
        return pd.DataFrame(columns=columns)

    effective_run_date = pd.Timestamp(run_date)
    if effective_run_date.tzinfo is None:
        effective_run_date = effective_run_date.tz_localize(UTC)
    else:
        effective_run_date = effective_run_date.tz_convert(UTC)
    effective_run_date = effective_run_date.normalize()

    rows: list[dict[str, Any]] = []
    for record in records:
        paper_id = _clean_text(record.paper_id)
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        authors = _clean_list(record.authors)
        categories = _clean_list(record.categories)
        published_ts = pd.to_datetime(record.published, errors="coerce", utc=True)
        updated_ts = pd.to_datetime(record.updated, errors="coerce", utc=True)

        # These fields are the minimum useful unit for retrieval and evaluation.
        if not paper_id or not title or not summary or pd.isna(published_ts):
            continue

        published = published_ts.date().isoformat()
        updated = "" if pd.isna(updated_ts) else updated_ts.date().isoformat()
        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        primary_category = _clean_text(record.primary_category)
        if not primary_category and categories:
            primary_category = categories[0]
        age_days = int((effective_run_date - published_ts.normalize()).days)
        text_for_embedding = "\n".join(
            (
                f"Title: {title}",
                f"Authors: {authors_joined}",
                f"Published: {published}",
                f"Categories: {categories_joined}",
                f"Summary: {summary}",
            )
        )
        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)

    dataframe = pd.DataFrame(rows, columns=columns)
    dataframe = dataframe.drop_duplicates(subset=["paper_id"], keep="first")
    return dataframe.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)


def _clean_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return normalize_whitespace(unescape(text))


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            values = parsed if isinstance(parsed, list) else [value]
        except json.JSONDecodeError:
            values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = []

    result: list[str] = []
    for item in values:
        cleaned = _clean_text(item)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result
