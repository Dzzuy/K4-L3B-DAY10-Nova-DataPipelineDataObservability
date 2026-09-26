from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


QUESTION_TYPES = ("summary", "authors", "date", "categories")
REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
}


def _evenly_spaced_rows(df: pd.DataFrame, count: int) -> pd.DataFrame:
    """Select rows across the full dataframe while keeping the result deterministic."""
    last_index = len(df) - 1
    positions = [round(i * last_index / (count - 1)) for i in range(count)]
    return df.iloc[positions].reset_index(drop=True)


def _question_and_answer(question_type: str, row: pd.Series) -> tuple[str, str]:
    title = str(row["title"]).strip()
    if question_type == "summary":
        return f"What is the summary of the paper '{title}'?", first_sentence(str(row["summary"]))
    if question_type == "authors":
        return f"Who authored the paper '{title}'?", str(row["authors_joined"]).strip()
    if question_type == "date":
        return f"When was the paper '{title}' published?", str(row["published"]).strip()
    return f"What categories are associated with the paper '{title}'?", str(
        row["categories_joined"]
    ).strip()


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a reproducible 10-question benchmark from cleaned paper records."""
    if len(df) < 10:
        raise ValueError("At least 10 cleaned papers are required to build the test set.")

    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing columns: {', '.join(missing_columns)}")

    selected = _evenly_spaced_rows(df, count=10)
    test_set: list[dict[str, Any]] = []
    for index, (_, row) in enumerate(selected.iterrows(), start=1):
        question_type = QUESTION_TYPES[(index - 1) % len(QUESTION_TYPES)]
        question, ground_truth = _question_and_answer(question_type, row)
        paper_id = str(row["paper_id"]).strip()
        if not paper_id or not ground_truth:
            raise ValueError(f"Selected paper at position {index} has an empty ground-truth field.")

        test_set.append(
            {
                "id": f"eval_{index:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    write_json(output_path, test_set)
    return test_set
