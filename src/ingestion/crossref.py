from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse and normalize valid papers from a Crossref API payload."""
    if not isinstance(payload, dict):
        raise ValueError("Crossref payload must be a JSON object.")

    message = payload.get("message")
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        raise ValueError("Crossref payload is missing message.items.")

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = _clean_text(item.get("DOI")).lower()
        title = _first_text(item.get("title"))
        summary = _clean_jats(item.get("abstract"))
        if not paper_id or not title or not summary:
            continue

        authors = _parse_authors(item.get("author"))
        categories = _crossref_categories(item)
        published = _crossref_date(item.get("published"))
        if not published:
            published = _crossref_date(item.get("published-online")) or _crossref_date(
                item.get("published-print")
            )
        updated = (
            _crossref_datetime(item.get("indexed"))
            or _crossref_datetime(item.get("deposited"))
            or _crossref_datetime(item.get("created"))
            or published
        )
        if not published:
            continue

        abs_url = _clean_text(item.get("URL")) or f"https://doi.org/{paper_id}"
        pdf_url = _pdf_url(item) or abs_url
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=f"Crossref record {paper_id}",
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref data with retry/fallback and persist both raw stages."""
    endpoint = "https://api.crossref.org/works"
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "Nova-DataObservability-Lab/1.0 (Crossref metadata client)",
    }

    payload: dict[str, Any] | None = None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(endpoint, params=params, headers=headers, timeout=(5, 30))
            if response.status_code in {429, 500, 502, 503, 504}:
                raise requests.HTTPError(
                    f"Crossref temporarily unavailable ({response.status_code})",
                    response=response,
                )
            response.raise_for_status()
            candidate = response.json()
            if not isinstance(candidate, dict):
                raise ValueError("Crossref returned a non-object JSON payload.")
            payload = candidate
            break
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("Retry-After")
                try:
                    delay = min(max(float(retry_after), 0.0), 10.0)
                except (TypeError, ValueError):
                    delay = 2**attempt
                time.sleep(delay)

    if payload is None:
        if not settings.paths.raw_api_response.exists():
            raise RuntimeError("Crossref fetch failed and no local raw snapshot is available.") from last_error
        fallback = read_json(settings.paths.raw_api_response)
        if not isinstance(fallback, dict):
            raise ValueError("Local Crossref snapshot must contain a JSON object.")
        payload = fallback

    records = parse_crossref_payload(payload)[: settings.max_results]
    if not records:
        raise ValueError("Crossref payload did not contain any valid paper records.")

    # Keep both stages so a downstream repair can trace cleaned data back to source.
    write_json(settings.paths.raw_api_response, payload)
    write_json(settings.paths.raw_records_json, [record.__dict__ for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load either a parsed-record snapshot or a raw Crossref response."""
    payload = read_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("message"), dict):
        return parse_crossref_payload(payload)
    if not isinstance(payload, list):
        raise ValueError(f"Raw records file must contain a JSON list: {path}")

    records: list[PaperRecord] = []
    field_names = tuple(PaperRecord.__dataclass_fields__)
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record at index {index} is not a JSON object.")
        missing = [name for name in field_names if name not in item]
        if missing:
            raise ValueError(f"Raw record at index {index} is missing fields: {', '.join(missing)}")
        values = {name: item[name] for name in field_names}
        values["authors"] = _text_list(values["authors"])
        values["categories"] = _text_list(values["categories"])
        for name in field_names:
            if name not in {"authors", "categories"}:
                values[name] = _clean_text(values[name])
        records.append(PaperRecord(**values))
    return records


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return normalize_whitespace(unescape(str(value)))


def _clean_jats(value: Any) -> str:
    # Crossref abstracts commonly contain JATS tags and HTML entities.
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return _clean_text(text)


def _text_list(value: Any) -> list[str]:
    candidates = value if isinstance(value, (list, tuple)) else [value]
    result: list[str] = []
    for candidate in candidates:
        text = _clean_text(candidate)
        if text and text not in result:
            result.append(text)
    return result


def _first_text(value: Any) -> str:
    values = _text_list(value)
    return values[0] if values else ""


def _parse_authors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    authors: list[str] = []
    for author in value:
        if not isinstance(author, dict):
            name = _clean_text(author)
        else:
            name = _clean_text(
                " ".join(
                    part
                    for part in (
                        _clean_text(author.get("given")),
                        _clean_text(author.get("family")),
                    )
                    if part
                )
            )
            name = name or _clean_text(author.get("name"))
        if name and name not in authors:
            authors.append(name)
    return authors


def _crossref_categories(item: dict[str, Any]) -> list[str]:
    """Return Crossref subjects, falling back to its document type.

    Crossref publishers frequently omit ``subject`` even when the rest of the
    work metadata is complete. The work ``type`` is less specific, but it is a
    stable controlled value and keeps category-dependent downstream steps from
    receiving an empty field.
    """
    subjects = _text_list(item.get("subject"))
    if subjects:
        return subjects

    work_type = _clean_text(item.get("type"))
    if not work_type:
        return ["Uncategorized"]
    return [work_type.replace("-", " ").title()]


def _crossref_date(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    date_parts = value.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts or not isinstance(date_parts[0], list):
        return ""
    parts = date_parts[0]
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day).isoformat()
    except (IndexError, TypeError, ValueError):
        return ""


def _crossref_datetime(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    raw = value.get("date-time")
    if raw:
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return _crossref_date(value)


def _pdf_url(item: dict[str, Any]) -> str:
    links = item.get("link")
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            content_type = _clean_text(link.get("content-type")).lower()
            url = _clean_text(link.get("URL"))
            if url and ("pdf" in content_type or url.lower().endswith(".pdf")):
                return url
    resource = item.get("resource")
    if isinstance(resource, dict):
        primary = resource.get("primary")
        if isinstance(primary, dict):
            return _clean_text(primary.get("URL"))
    return ""
