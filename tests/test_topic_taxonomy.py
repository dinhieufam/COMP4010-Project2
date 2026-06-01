from __future__ import annotations

import importlib


topics_module = importlib.import_module("pipeline.04_topic_modeling")


def test_taxonomy_has_unique_complete_topics():
    topics, fallback = topics_module.load_taxonomy()
    ids = [topic["id"] for topic in topics] + [fallback["id"]]
    labels = [topic["label"] for topic in topics] + [fallback["label"]]
    assert len(ids) == len(set(ids))
    assert len(labels) == len(set(labels))
    assert len(topics) == 15
    for topic in [*topics, fallback]:
        assert topic["keywords"]
        assert topic["seed_phrases"]


def test_known_titles_map_to_curated_topics():
    topics, fallback = topics_module.load_taxonomy()
    cases = {
        "Scaling Laws for Large Language Models and Reasoning": "Natural Language Processing & LLMs",
        "Offline Reinforcement Learning with Policy Gradients": "Reinforcement Learning & Decision Making",
        "Graph Neural Networks for Node Classification": "Graph Learning & Network Science",
    }
    for title, expected in cases.items():
        assignment = topics_module.assign_topic(title, "", topics, fallback)
        assert assignment["topic_label"] == expected
        assert not assignment["topic_review_flag"]


def test_weak_titles_are_flagged_for_review():
    topics, fallback = topics_module.load_taxonomy()
    assignment = topics_module.assign_topic("A Note on Something Vague", "", topics, fallback)
    assert assignment["topic_label"] == "General / Other ML"
    assert assignment["topic_review_flag"]


def test_overrides_win_and_parse_secondary_topics():
    topics, fallback = topics_module.load_taxonomy()
    lookup = {topics_module.canonical_label(topic["label"]): topic for topic in [*topics, fallback]}
    assignment = topics_module.assign_topic(
        "Graph Neural Networks for Node Classification",
        "",
        topics,
        fallback,
    )
    override = {
        "primary": lookup[topics_module.canonical_label("Natural Language Processing & LLMs")],
        "secondary": topics_module.parse_secondary_topics(
            "Graph Learning & Network Science; Data, Evaluation & Benchmarks",
            lookup,
        ),
    }
    updated = topics_module.apply_override(assignment, override)
    assert updated["topic_label"] == "Natural Language Processing & LLMs"
    assert updated["secondary_topic_labels"] == [
        "Graph Learning & Network Science",
        "Data, Evaluation & Benchmarks",
    ]
    assert not updated["topic_review_flag"]
