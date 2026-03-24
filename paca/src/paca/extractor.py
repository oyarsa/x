"""LLM-based extraction of appointment details using the OpenAI Responses API."""

import logging
from typing import Any, cast

from openai import OpenAI
from openai.types.responses import ResponseInputParam

from paca.input_capture import CapturedInput, InputKind
from paca.schema import ExtractionResult

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT: str = """\
You are extracting exactly one calendar event from the provided text or image.

Rules:
- Prefer precision over creativity.
- Do not invent missing data.
- If uncertain, leave the field null and add a warning.
- Preserve institutional names faithfully.
- Separate title from location where possible.
- If only one time is present, treat it as start time.
- If "Booked appointment" or similar generic text appears, ignore it as a title \
unless there is no better option.
- If weekday and numeric date disagree, warn rather than silently correcting.
- Return only valid JSON matching the schema.
"""
"""System prompt sent to the LLM for appointment extraction."""

type ExtractionInput = list[dict[str, Any]]


def build_extraction_input(captured: CapturedInput) -> list[dict[str, Any]]:
    """Build the input content list for the Responses API.

    The Responses API takes `input` as a list of content items, not
    Chat Completions-style message dicts with roles.

    Args:
        captured: The captured input (text or image).

    Returns:
        List of content item dicts for the Responses API `input` parameter.
    """
    if captured.kind == InputKind.IMAGE and captured.image_base64:
        return [
            {
                "type": "input_image",
                "image_url": f"data:{captured.image_media_type or 'image/png'};base64,{captured.image_base64}",
            },
        ]

    return [
        {
            "type": "input_text",
            "text": captured.text or "",
        },
    ]


def extract(captured: CapturedInput, *, model: str = "gpt-4o") -> ExtractionResult:
    """Send captured input to the OpenAI Responses API and parse the result.

    Uses structured output with a JSON schema to get reliable extraction.

    Args:
        captured: Text or image input to extract from.
        model: OpenAI model to use.

    Returns:
        Parsed ExtractionResult.

    Raises:
        ValueError: If the API response cannot be parsed.
    """
    client = OpenAI()
    input_items = build_extraction_input(captured)

    response = client.responses.create(
        model=model,
        instructions=EXTRACTION_SYSTEM_PROMPT,
        input=cast(ResponseInputParam, input_items),
        text={
            "format": {
                "type": "json_schema",
                "name": "extraction_result",
                "schema": ExtractionResult.model_json_schema(),
                "strict": True,
            },
        },
    )

    return ExtractionResult.model_validate_json(response.output_text)
