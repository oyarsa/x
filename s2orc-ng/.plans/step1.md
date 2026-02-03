# Step 1: Dataset Processing Plan

## Objective
Convert S2ORC full text into structured paper graphs with LLM-extracted facets.

## Input Data
- `s2orc_filtered.jsonl.gz` - Full text records from s2orc_v2 (format TBD after extraction completes)
- `papers/metadata.jsonl` - Paper metadata (title, abstract, year, venue, etc.)
- `citations/references.jsonl` - Citation relationships (ground truth already computed)

## Output Artifacts
```
data/
├── papers/
│   ├── paper_graphs.jsonl    # Hierarchical structure: paper -> sections -> paragraphs
│   └── facets.jsonl          # LLM-extracted facets per paper
├── ground_truth/
│   └── training_pairs.jsonl  # Query → positive pairs for training
└── processed/
    └── step1_progress.txt    # Tracking for resumability
```

## Architecture

### Phase 1: Full Text Parsing
Parse s2orc_v2 records into structured paper graphs.

**If s2orc_v2 has pre-parsed annotations:**
- Extract section boundaries from annotations
- Map annotation types to standard sections (abstract, introduction, method, results, etc.)

**If s2orc_v2 is raw text:**
- Use heuristics to detect section headers (numbered sections, ALL CAPS, etc.)
- Split into paragraphs by blank lines

**Output schema:**
```json
{
  "corpusid": 12345,
  "sections": [
    {
      "type": "abstract",
      "heading": "Abstract",
      "paragraphs": ["paragraph 1 text...", "paragraph 2 text..."]
    },
    {
      "type": "introduction",
      "heading": "1. Introduction",
      "paragraphs": [...]
    }
  ]
}
```

### Phase 2: Facet Extraction (OpenAI API)
Use GPT-4o-mini to extract representative snippets for each paper.

**Facet types:**
- `problem`: What problem does this paper address?
- `method`: What approach/method is proposed?
- `results`: What are the key findings?
- `contribution`: What is the main contribution?

**Input:** Full text, truncated to fit context window (128k tokens for GPT-4o-mini).

**Prompt template:**
```
Given a scientific paper, extract concise facets (< 512 tokens each).

Paper Title: {title}
Abstract: {abstract}
Full Text: {full_text_truncated}

Extract:
1. Problem: What problem does this paper address?
2. Method: What approach or method is proposed?
3. Results: What are the key findings?
4. Contribution: What is the main contribution?

Respond in JSON format.
```

**Output schema:**
```json
{
  "corpusid": 12345,
  "facets": {
    "problem": "This paper addresses...",
    "method": "We propose...",
    "results": "Our experiments show...",
    "contribution": "The main contribution is..."
  }
}
```

### Phase 3: Ground Truth Compilation
Compile citation relationships into training signal format.

**Input files (from Step 0):**
- `citations/references.jsonl` - paper_id → [cited_paper_ids]
- `citations/co_citations.jsonl` - co-citation pairs with counts
- `citations/bib_coupling.jsonl` - bib coupling pairs with shared ref counts

**Training pairs format:**
```json
{
  "query_id": 12345,
  "positives": {
    "cited": [111, 222, 333],           # Direct citations (strongest signal)
    "co_cited": [444, 555],              # Co-cited papers (count >= threshold)
    "bib_coupled": [666, 777]            # Bib-coupled papers (shared >= threshold)
  }
}
```

**Output:** `ground_truth/training_pairs.jsonl`

**Configurable thresholds:**
- `--min-co-citations 3` - Minimum co-citation count to be considered positive
- `--min-shared-refs 5` - Minimum shared references for bib coupling

### Phase 4: Validation
- Sample 50-100 papers for manual inspection
- Check section parsing quality
- Verify facet extraction coherence
- Verify ground truth pairs make sense

## Implementation

### New file: `step1_process.py`

**Commands:**
- `parse` - Parse full text into paper graphs
- `extract` - Extract facets using OpenAI API
- `ground-truth` - Compile citation data into training pairs
- `validate` - Sample papers for manual review
- `all` - Run full pipeline

**CLI examples:**
```bash
# Parse full text into structured graphs
uv run step1_process.py parse data/s2orc-nlp/

# Extract facets (requires OPENAI_API_KEY)
uv run step1_process.py extract data/s2orc-nlp/ --batch-size 50 --concurrent 10

# Compile ground truth training pairs
uv run step1_process.py ground-truth data/s2orc-nlp/ --min-co-citations 3 --min-shared-refs 5

# Sample validation
uv run step1_process.py validate data/s2orc-nlp/ --sample 100
```

**Key features:**
- Resumable processing with progress tracking (`processed_*.txt` pattern)
- Configurable batch size for API calls
- Rate limiting for OpenAI API (respects TPM/RPM limits)
- Async processing for throughput
- Joins fulltext + metadata by corpusid

**Code structure:**
```python
# Data loading
def load_fulltext(path: Path) -> dict[int, dict]  # corpusid -> record
def load_metadata(path: Path) -> dict[int, dict]  # corpusid -> metadata

# Phase 1: Parsing
def parse_paper(record: dict) -> PaperGraph
def detect_sections(text: str) -> list[Section]  # heuristic fallback

# Phase 2: Facet Extraction
async def extract_facets(paper: PaperGraph, client: AsyncOpenAI) -> Facets
async def extract_batch(papers: list[PaperGraph], client: AsyncOpenAI) -> list[Facets]

# Phase 3: Ground Truth
def load_citations(path: Path) -> dict[int, list[int]]  # references
def load_co_citations(path: Path) -> dict[tuple[int,int], int]  # pair -> count
def compile_training_pairs(refs, co_cites, bib_coupling, thresholds) -> list[TrainingPair]

# CLI commands using typer (same pattern as pipeline.py)
```

### Dependencies
Add to pyproject.toml:
- `openai` - OpenAI API client
- `tiktoken` - Token counting for context limits

## Decisions
- **Model**: GPT-4o-mini (lower cost, good quality for extraction)
- **Missing data**: Strict - only process papers with full text available

## Cost Estimate
- ~70k papers in corpus (fewer if many lack full text)
- ~5,000 tokens input per paper (title + abstract + truncated full text)
- ~200 tokens output per paper (facets)
- GPT-4o-mini: ~$0.15/1M input tokens, ~$0.60/1M output tokens
- Input: 70k × 5k = 350M tokens → ~$52
- Output: 70k × 200 = 14M tokens → ~$8
- Estimated cost: **~$60-70 for full corpus** (varies with actual paper lengths)

## Verification
1. Run `parse` on sample of 100 papers, inspect output
2. Run `extract` on same sample, review facet quality
3. If quality is good, run on full corpus
4. Run `validate` for final spot-check

## Open Questions
1. Exact s2orc_v2 field structure (will inspect after extraction completes)
