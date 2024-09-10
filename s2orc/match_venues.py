"""Match conference names from input file and write matches to output file."""

import argparse
import re
from typing import TextIO

# fmt: off
ACL_CONFERENCES = [
    "acl", "association for computational linguistics",
    "aacl", "asia-pacific chapter of the association for computational linguistics",
    "anlp", "applied natural language processing",
    "cl", "computational linguistics",
    "conll", "conference on computational natural language learning",
    "eacl", "european chapter of the association for computational linguistics",
    "emnlp", "empirical methods in natural language processing", "empirical methods in nlp",
    "findings", "findings of acl", "findings of the association for computational linguistics",
    "iwslt", "international workshop on spoken language translation",
    "naacl", "north american chapter of the association for computational linguistics",
    "semeval", "semantic evaluation",
    "*sem", "star sem", "joint conference on lexical and computational semantics",
    "tacl", "transactions of the association for computational linguistics",
    "wmt", "workshop on machine translation",
    "ws", "workshop",
    "alta", "australasian language technology association",
    "amta", "association for machine translation in the americas",
    "ccl", "chinese computational linguistics",
    "coling", "international conference on computational linguistics",
    "eamt", "european association for machine translation",
    "hlt", "human language technology",
    "ijclclp", "international journal of computational linguistics and chinese language processing",
    "ijcnlp", "international joint conference on natural language processing",
    "jep/taln/recital", "journées d'études sur la parole", "traitement automatique des langues naturelles", "rencontre des étudiants chercheurs en informatique pour le traitement automatique des langues",
    "konvens", "konferenz zur verarbeitung natürlicher sprache",
    "lilt", "linguistic issues in language technology",
    "lrec", "language resources and evaluation conference",
    "mtsummit", "machine translation summit",
    "muc", "message understanding conference",
    "nejlt", "northern european journal of language technology",
    "paclic", "pacific asia conference on language, information and computation",
    "ranlp", "recent advances in natural language processing",
    "rocling", "rocling conference on computational linguistics",
    "tal", "traitement automatique des langues",
    "tinlap", "theoretical issues in natural language processing",
    "tipster", "text information processing system"
]
# fmt: on


def normalize_text(text: str) -> str:
    """Remove non-alphanumeric characters and convert to lowercase."""
    return re.sub(r"[^a-z0-9\s]", "", text.lower())


def main(infile: TextIO, outfile: TextIO) -> None:
    normalized_conferences = {normalize_text(conf) for conf in ACL_CONFERENCES}

    for line in infile:
        normalized_line = normalize_text(line.strip())
        if any(conf in normalized_line for conf in normalized_conferences):
            outfile.write(line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_file",
        type=argparse.FileType("r"),
        help="Input file containing conference names",
    )
    parser.add_argument(
        "output_file",
        type=argparse.FileType("w"),
        help="Output file where matches will be written",
    )

    args = parser.parse_args()
    main(args.input_file, args.output_file)
