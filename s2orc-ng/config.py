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
    pdf_source: str | None = None  # "S2", "ArXiv", "ACL", or None


@dataclass
class ConferencePattern:
    """Pattern for identifying a conference across different naming conventions."""

    name: str  # Canonical name for grouping
    venue_patterns: list[str]  # Venue names to match
    category: str = "Other"  # Category for filtering in plots


# Conference categories
CATEGORY_NLP = "NLP"
CATEGORY_ML = "ML/AI"
CATEGORY_CV = "Computer Vision"
CATEGORY_IR = "Information Retrieval"
CATEGORY_DATA = "Data Mining"

# Comprehensive list of conferences to search for
# Each conference may have multiple name variations across years
CONFERENCE_PATTERNS: list[ConferencePattern] = [
    # *ACL / NLP Conferences
    ConferencePattern(
        name="ACL",
        venue_patterns=[
            "Annual Meeting of the Association for Computational Linguistics",
            "ACL",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="EMNLP",
        venue_patterns=[
            "Conference on Empirical Methods in Natural Language Processing",
            "Empirical Methods in Natural Language Processing",
            "EMNLP",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="NAACL",
        venue_patterns=[
            "North American Chapter of the Association for Computational Linguistics",
            "NAACL",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="EACL",
        venue_patterns=[
            "Conference of the European Chapter of the Association for Computational Linguistics",
            "European Chapter of the Association for Computational Linguistics",
            "EACL",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="AACL-IJCNLP",
        venue_patterns=[
            "AACL",
            "International Joint Conference on Natural Language Processing",
            "IJCNLP",
            "AACL-IJCNLP",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="COLING",
        venue_patterns=[
            "International Conference on Computational Linguistics",
            "COLING",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="CoNLL",
        venue_patterns=[
            "Conference on Computational Natural Language Learning",
            "CoNLL",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="SEM",
        venue_patterns=[
            "Joint Conference on Lexical and Computational Semantics",
            "SEM",
            "StarSEM",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="TACL",
        venue_patterns=[
            "Transactions of the Association for Computational Linguistics",
            "TACL",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="LREC",
        venue_patterns=[
            "Language Resources and Evaluation Conference",
            "International Conference on Language Resources and Evaluation",
            "LREC",
        ],
        category=CATEGORY_NLP,
    ),
    ConferencePattern(
        name="SemEval",
        venue_patterns=[
            "International Workshop on Semantic Evaluation",
            "SemEval",
        ],
        category=CATEGORY_NLP,
    ),
    # Major ML/AI Conferences
    ConferencePattern(
        name="NeurIPS",
        venue_patterns=[
            "Neural Information Processing Systems",
            "NeurIPS",
            "NIPS",
        ],
        category=CATEGORY_ML,
    ),
    ConferencePattern(
        name="ICML",
        venue_patterns=[
            "International Conference on Machine Learning",
            "ICML",
        ],
        category=CATEGORY_ML,
    ),
    ConferencePattern(
        name="ICLR",
        venue_patterns=[
            "International Conference on Learning Representations",
            "ICLR",
        ],
        category=CATEGORY_ML,
    ),
    ConferencePattern(
        name="AAAI",
        venue_patterns=[
            "AAAI Conference on Artificial Intelligence",
            "AAAI",
        ],
        category=CATEGORY_ML,
    ),
    ConferencePattern(
        name="IJCAI",
        venue_patterns=[
            "International Joint Conference on Artificial Intelligence",
            "IJCAI",
        ],
        category=CATEGORY_ML,
    ),
    ConferencePattern(
        name="AISTATS",
        venue_patterns=[
            "International Conference on Artificial Intelligence and Statistics",
            "AISTATS",
        ],
        category=CATEGORY_ML,
    ),
    ConferencePattern(
        name="UAI",
        venue_patterns=[
            "Conference on Uncertainty in Artificial Intelligence",
            "UAI",
        ],
        category=CATEGORY_ML,
    ),
    ConferencePattern(
        name="COLT",
        venue_patterns=[
            "Conference on Learning Theory",
            "Annual Conference Computational Learning Theory",
            "COLT",
        ],
        category=CATEGORY_ML,
    ),
    # Computer Vision
    ConferencePattern(
        name="CVPR",
        venue_patterns=[
            "Computer Vision and Pattern Recognition",
            "CVPR",
        ],
        category=CATEGORY_CV,
    ),
    ConferencePattern(
        name="ICCV",
        venue_patterns=[
            "International Conference on Computer Vision",
            "IEEE International Conference on Computer Vision",
            "ICCV",
        ],
        category=CATEGORY_CV,
    ),
    ConferencePattern(
        name="ECCV",
        venue_patterns=[
            "European Conference on Computer Vision",
            "ECCV",
        ],
        category=CATEGORY_CV,
    ),
    # Information Retrieval
    ConferencePattern(
        name="SIGIR",
        venue_patterns=[
            "Annual International ACM SIGIR Conference on Research and Development in Information Retrieval",
            "SIGIR",
        ],
        category=CATEGORY_IR,
    ),
    ConferencePattern(
        name="WSDM",
        venue_patterns=[
            "Web Search and Data Mining",
            "WSDM",
        ],
        category=CATEGORY_IR,
    ),
    ConferencePattern(
        name="CIKM",
        venue_patterns=[
            "Conference on Information and Knowledge Management",
            "International Conference on Information and Knowledge Management",
            "CIKM",
        ],
        category=CATEGORY_IR,
    ),
    ConferencePattern(
        name="RecSys",
        venue_patterns=[
            "ACM Conference on Recommender Systems",
            "RecSys",
        ],
        category=CATEGORY_IR,
    ),
    # Data Mining / Web
    ConferencePattern(
        name="KDD",
        venue_patterns=[
            "Knowledge Discovery and Data Mining",
            "KDD",
            "ACM SIGKDD",
        ],
        category=CATEGORY_DATA,
    ),
    ConferencePattern(
        name="WWW",
        venue_patterns=[
            "The Web Conference",
            "WWW",
            "World Wide Web Conference",
        ],
        category=CATEGORY_DATA,
    ),
    ConferencePattern(
        name="VLDB",
        venue_patterns=[
            "Very Large Data Bases",
            "Very Large Data Bases Conference",
            "VLDB",
            "Proceedings of the VLDB Endowment",
        ],
        category=CATEGORY_DATA,
    ),
]


def get_venue_to_conference_map() -> dict[str, str]:
    """Build a mapping from venue patterns to canonical conference names."""
    mapping: dict[str, str] = {}
    for conf in CONFERENCE_PATTERNS:
        for venue in conf.venue_patterns:
            mapping[venue] = conf.name
    return mapping
