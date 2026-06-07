from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import AUDITS_DIR, INTERIM_DIR, MANUAL_DIR, TOPIC_TAXONOMY_PATH, ensure_dirs
from pipeline.io import write_parquet


OVERRIDE_COLUMNS = ["paper_id", "title", "primary_topic", "secondary_topics", "notes"]
OVERRIDE_PATH = MANUAL_DIR / "topic_overrides.csv"
PRIMARY_THRESHOLD = 3.0
SECONDARY_THRESHOLD = 3.0
SECONDARY_RATIO = 0.55
REVIEW_SCORE_THRESHOLD = 5.0
REVIEW_MARGIN_THRESHOLD = 1.5
VECTOR_PRIMARY_THRESHOLD = 0.28
VECTOR_REVIEW_PROBABILITY = 0.34
VECTOR_REVIEW_MARGIN = 0.045


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assign curated NeurIPS taxonomy topics.")
    parser.add_argument("--taxonomy", default=str(TOPIC_TAXONOMY_PATH))
    parser.add_argument("--overrides", default=str(OVERRIDE_PATH))
    return parser.parse_args()


def normalize_text(value: Any) -> str:
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokens_for(text: str) -> Counter[str]:
    return Counter(part for part in normalize_text(text).split() if part)


def canonical_label(value: str) -> str:
    return normalize_text(value).replace(" ", "")


def load_taxonomy(path: Path | str = TOPIC_TAXONOMY_PATH) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    topics = payload["topics"]
    fallback = payload["fallback"]
    validate_taxonomy(topics, fallback)
    return topics, fallback


def validate_taxonomy(topics: list[dict[str, Any]], fallback: dict[str, Any]) -> None:
    topic_ids = [int(topic["id"]) for topic in topics] + [int(fallback["id"])]
    labels = [str(topic["label"]) for topic in topics] + [str(fallback["label"])]
    if len(topic_ids) != len(set(topic_ids)):
        raise ValueError("Topic taxonomy has duplicate topic IDs.")
    if len(labels) != len(set(labels)):
        raise ValueError("Topic taxonomy has duplicate labels.")
    for topic in [*topics, fallback]:
        if not topic.get("keywords") or not topic.get("seed_phrases"):
            raise ValueError(f"Topic {topic.get('label')} needs keywords and seed_phrases.")


def score_topic(text: str, token_counts: Counter[str], topic: dict[str, Any]) -> float:
    normalized = normalize_text(text)
    score = 0.0
    for phrase in topic.get("seed_phrases", []):
        normalized_phrase = normalize_text(phrase)
        if normalized_phrase and re.search(rf"\b{re.escape(normalized_phrase)}\b", normalized):
            score += 4.0
    for keyword in topic.get("keywords", []):
        normalized_keyword = normalize_text(keyword)
        if not normalized_keyword:
            continue
        if " " in normalized_keyword:
            if re.search(rf"\b{re.escape(normalized_keyword)}\b", normalized):
                score += 2.5
        else:
            count = token_counts.get(normalized_keyword, 0)
            if count:
                score += min(count, 3) * 1.0
    return round(score, 3)


def topic_keywords(topic: dict[str, Any]) -> str:
    return ", ".join(str(value) for value in topic.get("keywords", [])[:8])


def paper_topic_text(title: str, abstract: str) -> str:
    return f"{title} {title} {abstract}".strip()


def topic_prototype_text(topic: dict[str, Any]) -> str:
    label = str(topic.get("label", ""))
    seed_phrases = " ".join(str(value) for value in topic.get("seed_phrases", []))
    keywords = " ".join(str(value) for value in topic.get("keywords", []))
    return f"{label}. {label}. {seed_phrases}. {seed_phrases}. {keywords}".strip()


def softmax(values: np.ndarray, temperature: float = 0.18) -> np.ndarray:
    if values.size == 0:
        return values
    scaled = values / temperature
    scaled = scaled - np.max(scaled)
    exp_values = np.exp(scaled)
    return exp_values / max(float(exp_values.sum()), 1e-12)


def build_vector_scores(papers: pd.DataFrame, topics: list[dict[str, Any]]) -> np.ndarray:
    paper_texts = [
        normalize_text(paper_topic_text(str(row.get("title") or ""), str(row.get("abstract") or "")))
        for row in papers.to_dict("records")
    ]
    prototype_texts = [normalize_text(topic_prototype_text(topic)) for topic in topics]
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.92,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform([*paper_texts, *prototype_texts])
    paper_matrix = matrix[: len(paper_texts)]
    prototype_matrix = matrix[len(paper_texts) :]
    return cosine_similarity(paper_matrix, prototype_matrix)


def assign_topic(
    title: str,
    abstract: str,
    topics: list[dict[str, Any]],
    fallback: dict[str, Any],
    vector_scores: np.ndarray | None = None,
) -> dict[str, Any]:
    text = paper_topic_text(title, abstract)
    token_counts = tokens_for(text)
    scored = [
        {
            **topic,
            "keyword_score": score_topic(text, token_counts, topic),
            "vector_score": float(vector_scores[index]) if vector_scores is not None else 0.0,
        }
        for index, topic in enumerate(topics)
    ]
    max_keyword = max([float(topic["keyword_score"]) for topic in scored] + [1.0])
    max_vector = max([float(topic["vector_score"]) for topic in scored] + [1e-9])
    for topic in scored:
        keyword_component = min(float(topic["keyword_score"]) / max(max_keyword, 8.0), 1.0)
        vector_component = float(topic["vector_score"]) / max_vector if max_vector > 0 else 0.0
        topic["score"] = round((0.62 * vector_component) + (0.38 * keyword_component), 6)
    scored.sort(key=lambda topic: (float(topic["score"]), float(topic["keyword_score"]), -int(topic["id"])), reverse=True)
    best = scored[0]
    second = scored[1] if len(scored) > 1 else {**fallback, "score": 0.0, "keyword_score": 0.0}
    probabilities = softmax(np.array([float(topic["score"]) for topic in scored]))
    best_probability = float(probabilities[0]) if probabilities.size else 0.0
    second_probability = float(probabilities[1]) if probabilities.size > 1 else 0.0

    if float(best["score"]) < VECTOR_PRIMARY_THRESHOLD and float(best["keyword_score"]) < PRIMARY_THRESHOLD:
        best = {**fallback, "score": 0.0}
        secondary = []
        best_probability = 0.0
        second_probability = 0.0
    else:
        secondary = [
            topic
            for topic in scored[1:]
            if float(topic["score"]) >= VECTOR_PRIMARY_THRESHOLD
            and float(topic["score"]) >= float(best["score"]) * 0.82
        ][:3]

    best_score = float(best["score"])
    second_score = float(second["score"])
    review_flag = (
        str(best["label"]) == str(fallback["label"])
        or best_probability < VECTOR_REVIEW_PROBABILITY
        or best_probability - second_probability < VECTOR_REVIEW_MARGIN
    )

    return {
        "topic_id": int(best["id"]),
        "topic_label": str(best["label"]),
        "topic_probability": round(best_probability, 3),
        "topic_keywords": topic_keywords(best),
        "secondary_topic_ids": [int(topic["id"]) for topic in secondary],
        "secondary_topic_labels": [str(topic["label"]) for topic in secondary],
        "topic_score": round(best_score, 3),
        "secondary_topic_score": round(float(secondary[0]["score"]), 3) if secondary else 0.0,
        "topic_review_flag": bool(review_flag),
    }


def ensure_override_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OVERRIDE_COLUMNS)
        writer.writeheader()


def load_overrides(path: Path, label_lookup: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    ensure_override_file(path)
    overrides = pd.read_csv(path).fillna("")
    if overrides.empty:
        return {}
    missing = [column for column in OVERRIDE_COLUMNS if column not in overrides.columns]
    if missing:
        raise ValueError(f"topic_overrides.csv is missing columns: {', '.join(missing)}")

    parsed = {}
    for row in overrides.to_dict("records"):
        paper_id = str(row["paper_id"]).strip()
        primary = str(row["primary_topic"]).strip()
        if not paper_id or not primary:
            continue
        if canonical_label(primary) not in label_lookup:
            raise ValueError(f"Unknown primary topic override for {paper_id}: {primary}")
        secondary = parse_secondary_topics(str(row.get("secondary_topics", "")), label_lookup)
        parsed[paper_id] = {
            "primary": label_lookup[canonical_label(primary)],
            "secondary": secondary,
        }
    return parsed


def parse_secondary_topics(value: str, label_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    value = str(value or "").strip()
    if not value:
        return []
    if canonical_label(value) in label_lookup:
        return [label_lookup[canonical_label(value)]]
    parts = [part.strip() for part in re.split(r";|\|", value) if part.strip()]
    topics = []
    for part in parts:
        key = canonical_label(part)
        if key not in label_lookup:
            raise ValueError(f"Unknown secondary topic override: {part}")
        topics.append(label_lookup[key])
    return topics


def apply_override(assignment: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    primary = override["primary"]
    secondary = override["secondary"]
    return {
        **assignment,
        "topic_id": int(primary["id"]),
        "topic_label": str(primary["label"]),
        "topic_probability": 1.0,
        "topic_keywords": topic_keywords(primary),
        "secondary_topic_ids": [int(topic["id"]) for topic in secondary],
        "secondary_topic_labels": [str(topic["label"]) for topic in secondary],
        "topic_score": max(float(assignment.get("topic_score", 0.0)), REVIEW_SCORE_THRESHOLD),
        "secondary_topic_score": float(assignment.get("secondary_topic_score", 0.0)),
        "topic_review_flag": False,
    }


def write_topic_audit(papers: pd.DataFrame, taxonomy_labels: list[str]) -> None:
    rows = []
    for label in taxonomy_labels:
        subset = papers[papers["topic_label"].eq(label)]
        examples = subset.sort_values(["topic_score", "year"], ascending=[False, False])["title"].head(3).tolist()
        review_examples = subset[subset["topic_review_flag"]].sort_values("topic_score")["title"].head(3).tolist()
        rows.append(
            {
                "topic_label": label,
                "paper_count": int(len(subset)),
                "low_confidence_count": int(subset["topic_review_flag"].sum()) if not subset.empty else 0,
                "avg_topic_score": round(float(subset["topic_score"].mean()), 3) if not subset.empty else 0.0,
                "example_papers": " | ".join(examples),
                "review_examples": " | ".join(review_examples),
            }
        )
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(AUDITS_DIR / "topic_audit.csv", index=False)


def main() -> None:
    args = parse_args()
    ensure_dirs()
    clean_path = INTERIM_DIR / "clean.parquet"
    if not clean_path.exists():
        raise RuntimeError("Missing data/interim/clean.parquet. Run 03_clean_normalize.py first.")

    papers = pd.read_parquet(clean_path)
    if papers.empty:
        raise RuntimeError("No papers available for topic modeling.")

    topics, fallback = load_taxonomy(args.taxonomy)
    label_lookup = {canonical_label(topic["label"]): topic for topic in [*topics, fallback]}
    overrides = load_overrides(Path(args.overrides), label_lookup)
    vector_score_matrix = build_vector_scores(papers, topics)

    assignments = []
    for index, row in enumerate(papers.to_dict("records")):
        assignment = assign_topic(
            str(row.get("title") or ""),
            str(row.get("abstract") or ""),
            topics,
            fallback,
            vector_score_matrix[index],
        )
        override = overrides.get(str(row.get("paper_id")))
        if override:
            assignment = apply_override(assignment, override)
        assignments.append(assignment)

    assignment_df = pd.DataFrame(assignments)
    papers = pd.concat([papers.reset_index(drop=True), assignment_df], axis=1)

    write_parquet(papers, INTERIM_DIR / "topics.parquet")
    topic_records = papers[
        [
            "paper_id",
            "topic_id",
            "topic_label",
            "topic_probability",
            "topic_keywords",
            "secondary_topic_ids",
            "secondary_topic_labels",
            "topic_score",
            "secondary_topic_score",
            "topic_review_flag",
        ]
    ]
    write_parquet(topic_records, INTERIM_DIR / "topic_assignments.parquet")
    write_topic_audit(papers, [str(topic["label"]) for topic in [*topics, fallback]])
    review_count = int(papers["topic_review_flag"].sum())
    print(
        f"Assigned {papers['topic_id'].nunique()} curated topics to {len(papers)} papers; "
        f"{review_count} flagged for review."
    )


if __name__ == "__main__":
    main()
