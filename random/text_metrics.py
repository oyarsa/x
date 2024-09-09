# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "nltk",
#     "rouge-score",
# ]
# ///
"""Calculate similarity metrics (Exact Match, F1 score, and ROUGE-L) between two strings.

This module provides functionality to compute Exact Match (EM), F1 scores, and ROUGE-L
scores between two strings. The EM score checks for an exact match including word order,
the F1 score uses a bag-of-words representation disregarding word order, and ROUGE-L
is based on the Longest Common Subsequence. Common stopwords are removed during
tokenisation for EM and F1 calculations, but not for ROUGE-L.
"""

# pyright: basic
import argparse
from collections import Counter
from dataclasses import dataclass

import nltk  # type: ignore
from rouge_score import rouge_scorer  # type: ignore


@dataclass(frozen=True)
class Metrics:
    exact_match: bool
    token_f1_score: float
    rouge_l_precision: float
    rouge_l_recall: float
    rouge_l_f1: float


_STOPWORDS = set(nltk.corpus.stopwords.words("english"))


def tokenise(text: str) -> list[str]:
    """Tokenise a string using NLTK, removing stopwords and converting to lowercase."""
    tokens = nltk.tokenize.word_tokenize(text.lower())
    return [token for token in tokens if token not in _STOPWORDS]


def calculate_f1_score(tokens1: list[str], tokens2: list[str]) -> float:
    """Calculate the F1 score between two lists of tokens.

    The F1 score is based on an order-invariant bag-of-words representation.
    """
    bag1 = Counter(tokens1)
    bag2 = Counter(tokens2)

    true_positives = sum((bag1 & bag2).values())
    precision = true_positives / len(tokens2) if tokens2 else 0
    recall = true_positives / len(tokens1) if tokens1 else 0

    return 2 * (precision * recall) / (precision + recall) if precision + recall else 0


def calculate_rouge_l(text1: str, text2: str) -> rouge_scorer.scoring.Score:
    """Calculate ROUGE-L scores between two strings."""
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    scores = scorer.score(text1, text2)
    return scores["rougeL"]


def get_metrics(text1: str, text2: str) -> Metrics:
    """Calculate similarity metrics between two strings.

    This function tokenises the input strings and calculates Exact Match (EM),
    token-based F1 score, and ROUGE-L scores.
    """
    tokens1 = tokenise(text1)
    tokens2 = tokenise(text2)

    em_score = tokens1 == tokens2
    token_f1_score = calculate_f1_score(tokens1, tokens2)
    rouge_l_scores = calculate_rouge_l(text1, text2)

    return Metrics(
        exact_match=em_score,
        token_f1_score=token_f1_score,
        rouge_l_precision=rouge_l_scores.precision,
        rouge_l_recall=rouge_l_scores.recall,
        rouge_l_f1=rouge_l_scores.fmeasure,
    )


def main(text1: str, text2: str) -> None:
    nltk.download("punkt", quiet=True)
    nltk.download("stopwords", quiet=True)

    metrics = get_metrics(text1, text2)
    print(f"Exact Match: {metrics.exact_match}")
    print(f"Token F1 Score: {metrics.token_f1_score:.4f}")
    print("ROUGE-L Scores:")
    print(f"  Precision: {metrics.rouge_l_precision:.4f}")
    print(f"  Recall: {metrics.rouge_l_recall:.4f}")
    print(f"  F1: {metrics.rouge_l_f1:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("text1", help="First input string")
    parser.add_argument("text2", help="Second input string")
    args = parser.parse_args()

    main(args.text1, args.text2)
