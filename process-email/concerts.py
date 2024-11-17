"""Extract concerts from emails."""

import argparse
import asyncio
import re
from collections.abc import Awaitable, Iterable, Sequence
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import backoff
import openai
import tiktoken
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, TypeAdapter
from rich.console import Console
from rich.table import Table
from tqdm.asyncio import tqdm_asyncio  # type: ignore

MODEL_SYNONYMS = {
    "4o-mini": "gpt-4o-mini-2024-07-18",
    "gpt-4o-mini": "gpt-4o-mini-2024-07-18",
    "4o": "gpt-4o-2024-08-06",
    "gpt-4o": "gpt-4o-2024-08-06",
}
# Include the synonyms and their keys in the allowed models
MODELS_ALLOWED = sorted(MODEL_SYNONYMS.keys() | MODEL_SYNONYMS.values())

# Cost in $ per 1M tokens: (input cost, output cost)
# From https://openai.com/api/pricing/
MODEL_COSTS = {
    "gpt-4o-mini-2024-07-18": (0.15, 0.6),
    "gpt-4o-2024-08-06": (2.5, 10),
}

REQUESTS_CONCURRENT_MAX = 10
SEMAPHORE = asyncio.Semaphore(REQUESTS_CONCURRENT_MAX)

GPT_TOKENISER = tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True, kw_only=True)
class GPTResult[T]:
    result: T | None
    cost: float


@backoff.on_exception(backoff.expo, openai.APIError, max_tries=5)
async def call_gpt[T: BaseModel](
    class_: type[T],
    client: AsyncOpenAI,
    system_prompt: str,
    user_prompt: str,
    model: str,
    *,
    seed: int,
    temperature: float = 0,
):
    async with SEMAPHORE:
        return await client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=class_,
            seed=seed,
            temperature=temperature,
        )


async def run_gpt[T: BaseModel](
    class_: type[T],
    client: AsyncOpenAI,
    system_prompt: str,
    user_prompt: str,
    model: str,
    *,
    seed: int,
    temperature: float = 0,
) -> GPTResult[T]:
    """Run OpenAI GPT with structured outputs. Returns the parsed output and cost."""

    completion = await call_gpt(
        class_,
        client,
        system_prompt,
        user_prompt,
        model,
        seed=seed,
        temperature=temperature,
    )
    try:
        result = completion.choices[0].message.parsed
    except Exception as e:
        print(f"Error when calling OpenAI: {e}")
        return GPTResult(result=None, cost=0)

    if (usage := completion.usage) and model in MODEL_COSTS:
        input_cost, output_cost = MODEL_COSTS[model]
        cost = (
            usage.prompt_tokens / 1e6 * input_cost
            + usage.completion_tokens / 1e6 * output_cost
        )
    else:
        cost = 0

    return GPTResult(result=result, cost=cost)


async def gather[T](tasks: Iterable[Awaitable[T]], **kwargs: Any) -> list[T]:
    return list(await tqdm_asyncio.gather(*tasks, **kwargs))  # type: ignore


class Contact(BaseModel):
    """Representation of a name and email address pair."""

    name: Annotated[str, Field(description="Name of the contact")]
    email: Annotated[str, Field(description="Email of the contact")]


class Email(BaseModel):
    """Representation of a cleaned email message."""

    from_: Annotated[
        Contact, Field(description="Contact information for the email sender")
    ]
    to: Annotated[
        Contact, Field(description="Contact information for the email receiver")
    ]
    subject: Annotated[str, Field(description="Subject of the email")]
    text: Annotated[str, Field(description="Email main body text")]


class EmailClassified(BaseModel):
    """Representation of the classification result for a concert email."""

    is_concert: Annotated[
        bool,
        Field(description="True if the email is about a concert that will be attended"),
    ]
    bands: Annotated[
        Sequence[str],
        Field(
            description="Names of the bands referenced in the email. If it's not a"
            " concert email, this should be empty."
        ),
    ]
    date: Annotated[
        str | None,
        Field(
            description="Date of the concert. If it's not a concert email, this should"
            " be None. In YYYY-MM-DD format."
        ),
    ]


class Concert(BaseModel):
    """Represents a single concert, with a single band and the date."""

    band: Annotated[str, Field(description="Name of a single band in the concert")]
    date: Annotated[
        str, Field(description="Date when the concert happens, in YYYY-MM-DD format")
    ]


class ConcertSummary(BaseModel):
    """Representation of the final output with consolidated concerts.

    Concerts with many bands must be separated, with each band and date having a separate
    record in the output.
    """

    concerts: Annotated[
        Sequence[Concert],
        Field(description="Unique concerts extracted from the email data"),
    ]


async def classify_email(
    client: AsyncOpenAI, email: Email, seed: int, model: str
) -> GPTResult[EmailClassified]:
    """Classify an email and extract concert-related information."""
    system_prompt = """\
You are an AI that classifies emails to determine if they are related to concerts \
and extracts relevant information.
"""
    user_prompt = f"""\
Given the following email information, determine whether it contains information about \
a concert that I will attend.

Extract relevant information such as the band names and concertg date. A concert will \
have multiple bands attached to it, but share the same date.

Note that I'm only interested in concerts I'm going to. This means confirmation of \
tickets purchased and show reminders. You should not count promotional emails announcing \
concerts.

Here are some examples of sentences that we are NOT interested in, as they only offer
promotional information, but do not show that I will attend the concert:

1. Join us online and be part of the celebration! VIEW THIS EMAIL IN YOUR BROWSER ** - 20TH ANNIVERSARY STREAMING EVENT - ** EPICA TO STREAM THEIR SOLD-OUT 20TH ANNIVERSARY LIVE SHOW! ** While we would love to see all your faces in the crowd during our 20th Anniversary Show on September 3, we are aware that not every one is able to attend the SOLD-OUT party live in Tilburg. Therefore, we're happy to offer you the chance to be part of th e celebrations and join us right from your living room through an exclusive pro-shot live stream of the entire show that will contain plenty of surprises, guests and spectacular stage effects! "We are extremely happy to be able to share our anniversary - not only with the lucky ones who got a ticket - but also with everybody else in the world! Our loyal fanbase is everywhere around this planet and through this live stream we can let everyone be part of this party. It wouldn't be a birthday bash without you! So, grab your drinks and warn the neighbors, because this is going to be a noisy night! " - Coen Janssen ** In addition, you will witness the return of SAHARA DUST - a band that disappeared from the face of the earth for 20 years, emerging for a one-off live performance as the opening act on this special night. ** Don't miss their show, because although you might have never heard of them, their history is heavily interwoven with Epica's inception, and you will surely be able to sing along a few of their songs. . . ** Starting live at 19:30 CEST, the shows will remain online for 72 hours to re-watch in your account at any time within that period. ** Early bird tickets are available until August 12, and you can also get bundles with exclusive anniversary show merchandise that will only be available with the stream and at the show in Tilburg, so don't miss out! GET EARLY BIRD TICKETS + BUNDLES
2. Check out the best upcoming shows in Leamington Spa this month THIS MONTH'S TOP PICKS THE MAGIC OF MOTOWN 02. 02. 19 BRAINIAC DETECTIVE ACADEMY 17 - 20. 02. 19 HOLY HOLY FEATURING WOODY WOODMANSEY & TONY VISCONTI 23. 02. 19 THE CORAL 15. 03. 19 FEBRUARY 01 H OSPITALITY LEAMINGTON SPA 02 T HE MAGIC OF MOTOWN 02 P LAY THAT FUNKY MUSIC (MOTOWN AFTER PARTY) 02 U 2 BABY 08 B ONGO'S BINGO [SOLD OUT] 15 I NNOVATION - VALENTINES SPECIAL 17 BRAINIAC DETECTIVE ACADEMY 18 BRAINIAC DETECTIVE ACADEMY 19 BRAINIAC DETECTIVE ACADEMY 20 BRAINIAC DETECTIVE ACADEMY 22 F ATHERSON 23 H OLY HOLY MARCH 01 BONGO'S BINGO [SOLD OUT] 02 FM 03 RAVER TOTS 08 UFO - LAST ORDERS 50TH ANNIVERSARY TOUR 08 CRUCAST TAKEOVER 09 UK FOO FIGHTERS 14 EMBRACE [SOLD OUT] 15 THE CORAL 15 A NTARCTIC MONKEYS 16 THE VARUKERS - 40TH ANNIVERSARY HOMETOWN SHOW 22 MARTIN KEMP - THE ULTIMATE BACK TO THE 80'S DJ SET 23 DOORS ALIVE 24 DAVID FORD 29 BONGO'S BINGO [SOLD OUT] 30 THE BRITPOP REBOOT 2019 W/ BLUR2 / THE VERVE EXPERIENCE / PULP'D COMING SOON BENJAMIN FRANCIS LEFTWICH | THE WALL: LIVE EXTRAVAGANZA | SLEAFORD MODS UB40 | MOTT THE HOOPLE | SHALAMAR | MIDGE URE AND MUCH MORE Copyright 2019 MJR Group Main, All rights reserved. You are receiving this email because you have purchased a ticket from Eventbrite. Our mailing address is: MJR Group Main 86 QUANTOCK ROAD BRISTOL, Bristol BS3 4PE United Kingdom Want to change how you receive these emails? You can ** update your preferences or ** unsubscribe from this list.

Here are examples of what we ARE interested in. These include event reminders and
confirmations:

1. Day of event =Get ready for Xandria = Your tickets only work in the app, so make sure your phone is charged. View tickets *Bring your photo ID* Some venues need to see it for entry == Xandria = Make sure you've downloaded DICE and your phone's charged Download DICE from App Store or Google Play You have to show your tickets on the DICE app to access this event Ticket details Ticket type General Admission Quantity 1 Venue The Dome 2A Dartmouth Park Hill, London NW5 1HL Date & time Mon 27 Nov, 7:00 PM GMT Name on ticket Italo Da Silva Need help? Let's get you sorted. Check out our Help Centre and FAQs. For anything urgent, get in touch. Download the DICE app DICE FM UK Ltd Registered in England: No. 14373641 98 De Beauvoir Road, London N1 4EN
2. To view this email as a web page, go here. Italo Luis, You're In! Order #17-48333/UK1 Lo Moon The Lexington, London Tue 14 Nov 2023 @ 7:30 pm Your Order 1x Postal Delivery Ticket View Tickets Full Price Ticket Price Level 1, Unreserved Standing THIS EMAIL CANNOT BE USED FOR ENTRY Payment Summary 1 Full Price Ticket 12. 50 Per Item Fees 1. 25 (Service Charge Full Price Ticket) x1 1. 25 Order Processing Fees Handling Fee (2. 50) 2. 50 Delivery Charge 0. 45 Total 16. 70 Your Tickets are Insured Thank you for purchasing ticket insurance for this event, provided by Allianz Assistance. If you have any questions regarding your insurance, or if you do not receive a confirmation email containing the details of your policy, please contact Allianz Assistance. Missed Event Insurance 2. 73 Total 2. 73 Payment: VISA 2. 73 Postal Tickets You chose: Standard Post For more information on your chosen delivery type, view our Delivery Types Guide. Ticketmaster | Contact us This email confirms your ticket order, so print/save it for future reference. All purchases are subject to credit card approval, billing address verification and Terms and Conditions as set out in our Purchase Policy. We make every effort to be accurate, but we cannot be responsible for changes, cancellations, or postponements announced after this email is sent. (c) 2023 Ticketmaster. All rights reserved. Ticketmaster UK Limited. Registered in England, company number 02662632. Registered Office: 30 St John Street, London EC1M 4AY Please do not reply to this email. Replies to this email will not be responded to or read. If you have any questions or comments, contact us.
3. Purchase confirmation == Nice one, Italo = You're going to VISIONS OF ATLANTIS == VISIONS OF ATLANTIS = Your tickets are stored securely in the DICE app to prevent touting Download DICE from App Store or Google Play You have to show your tickets on the DICE app to access this event View tickets Ticket details Ticket type General Admission Quantity 2 Venue The Underworld 174 Camden High St, London NW1 0NE Date & time Fri 04 Oct, 6:00 PM GMT+1 Name on ticket Italo Da Silva Total price 63. 66 Need help? Let's get you sorted. Check out our Help Centre and FAQs. For anything urgent, get in touch. Download the DICE app DICE FM UK Ltd Registered in England: No. 14373641 98 De Beauvoir Road, London N1 4EN

---

Email information:

From: {email.from_.name} <{email.from_.email}>
To: {email.to.name} <{email.to.email}>
Subject: {email.subject}
Body text:
{email.text}

Output:
"""

    return await run_gpt(
        class_=EmailClassified,
        client=client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        seed=seed,
    )


async def summarise_concerts(
    client: AsyncOpenAI,
    classified_emails: Sequence[EmailClassified],
    seed: int,
    model: str,
) -> GPTResult[ConcertSummary]:
    """Summarise all classified emails into a final concert summary."""
    system_prompt = """\
You are an AI that consolidates concert information into a structured format.
"""

    emails_prompts = [
        f"""\
Bands: {", ".join(concert_email.bands)}
Date: {concert_email.date}
"""
        for concert_email in classified_emails
    ]
    user_prompt = f"""
Given the following information about concerts, your task is to consolidate them into
a list of unique concerts with the band name and date. \
For concerts with multiple bands, each band must have a separate concert record. \
This means that a single input element may create multiple output items. \
If a given band has mulitiple concerts in different dates, each must have a separate \
record. Each concert of a given band in a date must only appear once. When deciding \
whether two bands are the same, you should not consider capitalisation or stopwords.

Concert information:

{"\n\n".join(emails_prompts)}
"""
    print("Summarisation prompt tokens:", num_tokens(system_prompt, user_prompt))

    return await run_gpt(
        ConcertSummary, client, system_prompt, user_prompt, model, seed=seed
    )


def num_tokens(system: str, user: str) -> int:
    return len(GPT_TOKENISER.encode(system + user))


async def main(
    input_file: Path,
    output_dir: Path,
    limit: int | None,
    seed: int,
    model: str,
    summarise_mode: str,
) -> None:
    """Main function to process emails and output concert summaries."""

    client = AsyncOpenAI()
    model = MODEL_SYNONYMS.get(model, model)
    output_dir.mkdir(parents=True, exist_ok=True)

    emails = TypeAdapter(Sequence[Email]).validate_json(input_file.read_bytes())
    emails = emails[:limit]

    # Filter out Songkick emails: they contain concert information, but are not
    # indicative of whether I went to them.
    emails_filtered = [
        email
        for email in emails
        if all(
            "songkick" not in e.lower() for e in [email.from_.name, email.from_.email]
        )
    ]

    email_tasks = [
        classify_email(client, email, seed, model) for email in emails_filtered
    ]
    emails_result = await gather(email_tasks, desc="Classifying emails")
    class_cost = sum(r.cost for r in emails_result)

    emails_classified = [
        email.result for email in emails_result if email.result is not None
    ]

    emails_file = output_dir / "emails_classified.json"
    emails_file.write_bytes(
        TypeAdapter(Sequence[EmailClassified]).dump_json(emails_classified, indent=2)
    )
    emails_concert = [
        c for c in emails_classified if c.is_concert and c.bands and c.date
    ]
    emails_concert_file = output_dir / "emails_concert.json"
    emails_concert_file.write_bytes(
        TypeAdapter(Sequence[EmailClassified]).dump_json(emails_concert, indent=2)
    )

    print("Summarising concerts")
    if summarise_mode == "gpt":
        summary_concerts, summary_cost = await summarise_gpt(
            client, emails_concert, seed, model
        )
    else:
        summary_concerts = summarise_auto(emails_concert)
        summary_cost = 0

    summary_file = output_dir / "summary.json"
    summary_type = type(summary_concerts[0])
    summary_file.write_bytes(
        TypeAdapter(Sequence[summary_type]).dump_json(summary_concerts, indent=2)
    )
    print("Summaries saved to:", summary_file)

    table = Table("Item", "Value")
    table.add_row("Emails all", str(len(emails)))
    table.add_row("Emails filtered", str(len(emails_filtered)))
    table.add_row("Emails classified", str(len(emails_classified)))
    table.add_row("Concerts summarised", str(len(summary_concerts)))
    table.add_section()
    table.add_row("Classification cost", f"${class_cost:.10f}")
    table.add_row("Summarisation cost", f"${summary_cost:.10f}")
    table.add_row("Total cost", f"${class_cost + summary_cost:.10f}")

    console = Console()
    console.print(table)


async def summarise_gpt(
    client: AsyncOpenAI,
    emails_concert: Sequence[EmailClassified],
    seed: int,
    model: str,
) -> tuple[Sequence[Concert], float]:
    result = await summarise_concerts(client, emails_concert, seed, model)
    if summary := result.result:
        return summary.concerts, result.cost
    return [], result.cost


def summarise_auto(emails_concert: Sequence[EmailClassified]) -> Sequence[Concert]:
    # Split multi-band events into multiple concerts
    concerts_all = [
        Concert(band=band, date=concert_combo.date)
        for concert_combo in emails_concert
        for band in concert_combo.bands
        if concert_combo.date
    ]
    return deduplicate_concerts(concerts_all)


class DedupedConcert(Concert):
    """Represents a deduplicated concert entry with original band name variations."""

    names: Sequence[str]
    clean_name: str


def clean_band_name(name: str) -> str:
    """Clean up a band name.

    1. Converting to lowercase
    2. Removing extra whitespace
    3. Removing special characters
    4. Standardising spaces around common separators
    """
    name = name.lower()
    name = " ".join(name.split())

    # Remove or standardize special characters
    name = re.sub(r"[^\w\s&-]", "", name)
    # Standardize spaces around & and -
    name = re.sub(r"\s*&\s*", " & ", name)
    name = re.sub(r"\s*-\s*", " - ", name)

    return name.strip()


def deduplicate_concerts(concerts: Sequence[Concert]) -> Sequence[DedupedConcert]:
    """
    Deduplicate concert entries based on cleaned band names and dates.
    Returns a list of DedupedConcert objects with original name variations.
    """
    # Dictionary to store unique concerts, keyed by (cleaned_name, date)
    unique_concerts: defaultdict[tuple[str, str], set[str]] = defaultdict(set)

    for concert in concerts:
        cleaned_name = clean_band_name(concert.band)
        unique_concerts[cleaned_name, concert.date].add(concert.band)

    result = [
        DedupedConcert(
            band=names[0],  # Use first encountered name as the canonical name
            date=date,
            names=names,
            clean_name=clean_name,
        )
        for (clean_name, date), names_ in unique_concerts.items()
        if (names := sorted(names_))
    ]

    return sorted(result, key=lambda x: (x.date, x.band))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path, help="Input file with the email data.")
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory to save classified emails and concerts.",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Maximum number of emails to process. If None, process all.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed to pass to the model for reproducbility.",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        choices=MODELS_ALLOWED,
        default="gpt-4o-mini",
        help="Model to use.",
    )
    parser.add_argument(
        "--summary",
        type=str,
        choices=["gpt", "auto"],
        default="auto",
        help="How to merge multiple events into a single summary",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            args.input_file,
            args.output_dir,
            args.limit,
            args.seed,
            args.model,
            args.summary,
        )
    )
