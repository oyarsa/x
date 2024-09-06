import argparse
import sys
import time
from typing import Any, TextIO

from openai import OpenAI


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def chunk_text(text: str, chunk_size: int = 3000) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_count = 0

    for word in words:
        if current_count + len(word) > chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_count = len(word)
        else:
            current_chunk.append(word)
            current_count += len(word) + 1  # +1 for the space

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def process_chunk(client: OpenAI, chunk: str, model: str) -> str:
    prompt = """
    Reformat the following text to be more readable. Remove any email headers, make the titles proper headings, make the paper descriptions bold, make the links obvious and remove extraneous content. The goal is to take this raw email content and transform it into something easy to read.
    """

    user_input = f"{prompt}\n\nInput content:\n{chunk}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that reformats text.",
            },
            {"role": "user", "content": user_input},
        ],
    )

    output_content = response.choices[0].message.content
    if output_content is None:
        raise ValueError("No output received.")

    return output_content


def main(input_file: TextIO, output_file: TextIO, model: str) -> None:
    input_content = input_file.read()
    chunks = chunk_text(input_content)

    client = OpenAI()  # Assumes you have set the OPENAI_API_KEY environment variable

    start_time = time.time()

    for i, chunk in enumerate(chunks):
        eprint(f"Processing chunk {i+1}/{len(chunks)}...")
        try:
            output_chunk = process_chunk(client, chunk, model)
            output_file.write(output_chunk)
            output_file.write("\n\n")  # Add some separation between chunks
        except Exception as e:
            eprint(f"Error processing chunk {i+1}: {e!s}")

    end_time = time.time()

    eprint(f"Time taken: {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transform raw input to formatted output using OpenAI API."
    )
    parser.add_argument(
        "input",
        type=argparse.FileType("r"),
        help="Input file (use '-' for stdin)",
    )
    parser.add_argument(
        "output",
        type=argparse.FileType("w"),
        help="Output file (use '-' for stdout)",
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model to use")
    args = parser.parse_args()
    main(args.input, args.output, args.model)
