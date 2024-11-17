import argparse
from pathlib import Path

from pydantic import BaseModel, TypeAdapter


class Contact(BaseModel):
    """Representation of a name and email address pair."""

    name: str
    email: str


class Email(BaseModel):
    """Representation of a cleaned email message."""

    from_: Contact
    to: Contact
    subject: str
    text: str


def is_concert_related(email: Email) -> bool:
    """Check if an email is related to concerts based on sender domain and subject."""
    # Songkick doesn't count
    if (
        "songkick" in email.from_.name.lower()
        or "songkick" in email.from_.email.lower()
    ):
        return False

    ticket_vendors = [
        "ticketmaster",
        "gigantic",
        "dice",
        "ticketweb",
        "roundhouse",
        "livenation",
        "axs",
        "eventbrite",
        "seetickets",
    ]

    # Check sender domaikn
    sender_email = email.from_.email.lower()
    if any(vendor in sender_email for vendor in ticket_vendors):
        return True

    # Check subject and text
    combined_text = f"{email.subject.lower()} {email.text.lower()}"
    return any(vendor in combined_text for vendor in ticket_vendors)


def filter_concert_emails(input_file: Path, output_file: Path) -> None:
    """
    Read emails from input JSON file, filter concert-related ones, and save to output file.
    """
    emails = TypeAdapter(list[Email]).validate_json(input_file.read_bytes())

    concert_emails = [email for email in emails if is_concert_related(email)]
    output_file.write_bytes(
        TypeAdapter(list[Email]).dump_json(concert_emails, indent=2)
    )

    print(f"Processed {len(emails)} emails")
    print(f"Found {len(concert_emails)} concert-related emails")
    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_file", type=Path, help="Path to processed emails JSON file."
    )
    parser.add_argument(
        "output_file", type=Path, help="Path to output filtered emails file."
    )
    args = parser.parse_args()

    filter_concert_emails(args.input_file, args.output_file)
