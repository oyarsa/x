"""Shared configuration and types for conference paper counting."""

from dataclasses import dataclass


@dataclass
class Paper:
    """Represents a paper with relevant metadata."""

    paper_id: str
    title: str
    year: int | None
    venue: str | None
    citation_count: int | None
    fields_of_study: list[str]
    url: str
    open_access_pdf: str | None


@dataclass
class ConferencePattern:
    """Pattern for identifying a conference across different naming conventions."""

    name: str  # Canonical name for grouping
    venue_patterns: list[str]  # Venue names to match


# Comprehensive list of conferences to search for
# Each conference may have multiple name variations across years
CONFERENCE_PATTERNS: list[ConferencePattern] = [
    # *ACL Conferences
    ConferencePattern(
        name="ACL",
        venue_patterns=[
            "Annual Meeting of the Association for Computational Linguistics",
            "ACL",
        ],
    ),
    ConferencePattern(
        name="EMNLP",
        venue_patterns=[
            "Conference on Empirical Methods in Natural Language Processing",
            "Empirical Methods in Natural Language Processing",
            "EMNLP",
        ],
    ),
    ConferencePattern(
        name="NAACL",
        venue_patterns=[
            "North American Chapter of the Association for Computational Linguistics",
            "NAACL",
        ],
    ),
    ConferencePattern(
        name="EACL",
        venue_patterns=[
            "Conference of the European Chapter of the Association for Computational Linguistics",
            "European Chapter of the Association for Computational Linguistics",
            "EACL",
        ],
    ),
    ConferencePattern(
        name="AACL-IJCNLP",
        venue_patterns=[
            "AACL",
            "International Joint Conference on Natural Language Processing",
            "IJCNLP",
            "AACL-IJCNLP",
        ],
    ),
    ConferencePattern(
        name="COLING",
        venue_patterns=[
            "International Conference on Computational Linguistics",
            "COLING",
        ],
    ),
    ConferencePattern(
        name="CoNLL",
        venue_patterns=[
            "Conference on Computational Natural Language Learning",
            "CoNLL",
        ],
    ),
    ConferencePattern(
        name="SEM",
        venue_patterns=[
            "Joint Conference on Lexical and Computational Semantics",
            "SEM",
            "StarSEM",
        ],
    ),
    # Major ML/AI Conferences
    ConferencePattern(
        name="NeurIPS",
        venue_patterns=[
            "Neural Information Processing Systems",
            "NeurIPS",
            "NIPS",
        ],
    ),
    ConferencePattern(
        name="ICML",
        venue_patterns=[
            "International Conference on Machine Learning",
            "ICML",
        ],
    ),
    ConferencePattern(
        name="ICLR",
        venue_patterns=[
            "International Conference on Learning Representations",
            "ICLR",
        ],
    ),
    ConferencePattern(
        name="AAAI",
        venue_patterns=[
            "AAAI Conference on Artificial Intelligence",
            "AAAI",
        ],
    ),
    ConferencePattern(
        name="IJCAI",
        venue_patterns=[
            "International Joint Conference on Artificial Intelligence",
            "IJCAI",
        ],
    ),
    ConferencePattern(
        name="KDD",
        venue_patterns=[
            "Knowledge Discovery and Data Mining",
            "KDD",
            "ACM SIGKDD",
        ],
    ),
    ConferencePattern(
        name="WWW",
        venue_patterns=[
            "The Web Conference",
            "WWW",
            "World Wide Web Conference",
        ],
    ),
    ConferencePattern(
        name="SIGIR",
        venue_patterns=[
            "Annual International ACM SIGIR Conference on Research and Development in Information Retrieval",
            "SIGIR",
        ],
    ),
]


def get_venue_to_conference_map() -> dict[str, str]:
    """Build a mapping from venue patterns to canonical conference names."""
    mapping: dict[str, str] = {}
    for conf in CONFERENCE_PATTERNS:
        for venue in conf.venue_patterns:
            mapping[venue] = conf.name
    return mapping
