# Generative Retrieval for Scientific Paper Recommendation

## Implementation Plan / Specification

---

## Step 0: Dataset Acquisition

### Objective
Download and prepare the raw dataset from S2ORC (Semantic Scholar Open Research Corpus) with all required fields for the generative retrieval pipeline.

### Data Source
- **Primary source**: S2ORC (Semantic Scholar Open Research Corpus)
- **API access**: Semantic Scholar Academic Graph API

### Filtering Criteria

#### 0.1 Venue Selection
Target papers from NLP, ML, AI, and IR conferences, including:
- ACL, EMNLP, NAACL, EACL, CoNLL, *SEM
- NeurIPS, ICML, ICLR
- AAAI, IJCAI
- SIGIR, WSDM, CIKM, WWW
- CVPR, ICCV, ECCV (for multimodal)

#### 0.2 Temporal Filtering
- **Training set**: 2020-2023 (~65k papers)
- **Dev/Test set**: 2024-2025 (~36k papers)
- Target total corpus size: **< 100k papers**

#### 0.3 Availability Requirements
- Must have **open access PDF** available
- Must have **full text content** in S2ORC
- Must have **parsed references** with resolved paper IDs

### Required Data Fields

| Field | Description | Used In |
|-------|-------------|---------|
| `paper_id` | Unique S2ORC/Semantic Scholar identifier | All steps |
| `title` | Paper title | DocID (optional), baselines |
| `abstract` | Paper abstract text | Facet extraction |
| `full_text` | Complete paper text with sections | Step 1: paper graph |
| `pdf_url` | Link to open access PDF | Step 5: figure/table extraction |
| `authors` | Author list with IDs | Metadata |
| `year` | Publication year | Train/test split |
| `venue` | Conference/journal name | Filtering |
| `references` | List of cited paper IDs | Ground truth: direct citations |
| `citations` | List of papers citing this one | Ground truth: co-citations |
| `s2_fields_of_study` | Research field tags | Filtering |

### Tasks

#### 0.4 Data Download
- Query S2ORC API with venue and year filters
- Download paper metadata in bulk
- Retrieve full text content for filtered papers
- Download or generate PDF links for open access papers

#### 0.5 Citation Graph Construction
Build citation relationships needed for ground truth:
- **Direct citations**: For each paper, store list of `references`
- **Incoming citations**: For each paper, store list of `citations`
- **Co-citation pairs**: Papers frequently cited together (compute from citation overlap)
- **Bibliographic coupling**: Papers sharing common references (compute from reference overlap)

#### 0.6 Data Validation
- Verify PDF availability for all papers
- Check full text parsing quality (section boundaries, etc.)
- Ensure citation graph connectivity (filter isolates if needed)
- Validate train/test split has no temporal leakage

### Output Artifacts
```
data/
├── papers/
│   ├── metadata.jsonl      # Paper metadata (id, title, abstract, year, venue)
│   ├── full_text.jsonl     # Full text with section boundaries
│   └── pdfs/               # Downloaded PDFs (for Step 5)
├── citations/
│   ├── references.jsonl    # paper_id -> [cited_paper_ids]
│   ├── citations.jsonl     # paper_id -> [citing_paper_ids]
│   ├── co_citations.jsonl  # Precomputed co-citation pairs
│   └── bib_coupling.jsonl  # Precomputed bibliographic coupling
└── splits/
    ├── train.txt           # Paper IDs for training (2020-2023)
    ├── dev.txt             # Paper IDs for dev (2024)
    └── test.txt            # Paper IDs for test (2025)
```

---

## Step 1: Dataset Processing

### Objective
Prepare the scientific paper corpus for generative retrieval training.

### Tasks

#### 1.1 PDF to Structured Paper Graph
Convert raw PDF documents into a hierarchical graph structure:
- **Paper node**: Root-level representation of the entire document
- **Section nodes**: Major structural divisions (abstract, methodology, experiments, results, etc.)
- **Paragraph leaf nodes**: Fine-grained text chunks used as evidence

#### 1.2 Facet Extraction
Extract representative snippets for each paper section:
- Generate short snippets, limited to **< 512 tokens**
- Cover multiple aspects: abstract, problem, method, results
- Include table/figure cards where applicable

#### 1.3 Ground Truth Compilation
Build the training signal from citation relationships:
- **Direct citations**: Papers explicitly cited by the source paper
- **Co-citations**: Papers frequently cited together with the source
- **Bibliographic coupling**: Papers that share common references

#### 1.4 Validation
- Perform small-scale validation of automated extraction results
- Verify quality of facet extraction and ground truth labels

---

## Step 2: Baseline - Text-Only, CE-Only Loss

### Objective
Establish a working baseline generative retrieval system using cross-entropy loss only.

### Tasks

#### 2.1 DocID Assignment
- Assign term-set DocIDs to papers and nodes from extracted terms
- Build hierarchical DocID structure: `<PAPER> {paper terms} <END_PAPER> <ASPECT=X> {aspect terms} <END_ASPECT>`

#### 2.2 Constrained Decoding Setup
- Implement inverted index for term-set constrained decoding
- Set up beam-over-sets decoding infrastructure
- Build postings lists for paper-level and aspect-level terms

#### 2.3 Generator Training
- Train generator model with **pure cross-entropy loss**
- Joint training on both retrieval and indexing tasks
- Use facet summaries/pseudo-queries as inputs (no raw paper text)

#### 2.4 Evaluation
- Perform small-scale evaluation of retrieval results
- Measure initial Recall@k metrics

---

## Step 3: Better Training

### Objective
Improve training with advanced loss functions and scoring mechanisms.

### Tasks

#### 3.1 Step Prefix Loss
- Add penalty to training loss where **earlier mistakes cost more**
- Implement weighted loss that decreases for later decoding steps
- Ensure tokens keeping positive candidates alive have higher probability

#### 3.2 Candidate Set Penalty
- Add penalty on too-large candidate sets
- Penalize DocIDs that don't narrow down the candidate pool effectively
- Encourage discriminative term selection

#### 3.3 Generator Scoring
Implement scoring function combining:
- **Model score**: Log probability from the generator
- **Token uniqueness**: Inverse document frequency or similar measure

#### 3.4 Evaluation
- Evaluate retrieval recall with the new scoring mechanism
- Compare against Step 2 baseline

---

## Step 4: Reranking

### Objective
Add a second-stage reranker to improve final ranking quality.

### Tasks

#### 4.1 Reranker Architecture
- Implement cross-encoder reranker
- Inputs:
  - Paper facets from both query and candidate documents
  - Text leaf nodes (evidence from selected sections)

#### 4.2 Training Data
- **Positive pairs**: Cited papers, co-citations, bibliographic coupling
- **Negative pairs**: Papers not in general vicinity (e.g., not cited by cited papers)
- Consider using retrieved papers from Semantic Scholar or SPECTER embeddings

#### 4.3 Two-Stage Pipeline
- Stage 1: Generator for candidate generation + weak scoring + evidence nodes
- Stage 2: Reranker for final ranking on top-K candidates

#### 4.4 Evaluation
- Evaluate ranking score (nDCG@k)
- Measure improvement over generator-only scoring

---

## Step 5: Multimodal

### Objective
Extend the system to handle figures and tables from papers.

### Tasks

#### 5.1 Visual Content Processing
- Apply OCR for images and tables
- Generate pseudo-queries from extracted visual content
- Convert table/figure content to textual representations

#### 5.2 Table/Figure Aspect
- Add new aspect type for tables and figures
- Assign aspect-specific DocID terms for visual content
- Integrate into the hierarchical DocID structure

#### 5.3 Evaluation
- Conduct ablation studies to measure impact of multimodal features
- Compare performance with/without figures and tables
- Analyze which query types benefit most from visual information

---

## Step 6: Baseline Comparisons

### Objective
Benchmark against established retrieval methods.

### Tasks

#### 6.1 Baseline Implementation
Run the following baselines on the same dataset:
- **BM25**: Using title + abstract (optionally full text)
- **SPECTER**: Paper-to-paper embedding nearest neighbors
- **Citation-based heuristics**: Simple citation graph traversal

#### 6.2 Human Evaluation
- Pool top K predictions from each method
- Manually assign relevance ranks to pooled results
- Form a small but high-quality evaluation set

#### 6.3 Final Evaluation
Compare all methods using:
- **Recall@k** at various cutoffs
- **nDCG@k** for ranking quality
- Ablation results across all configurations

---

## Summary of Deliverables

| Step | Primary Output |
|------|----------------|
| 0 | Raw dataset from S2ORC with papers, full text, PDFs, and citation graph |
| 1 | Processed dataset with paper graphs, facets, and ground truth |
| 2 | Working baseline with CE loss and constrained decoding |
| 3 | Improved generator with prefix loss and scoring |
| 4 | Two-stage retrieval pipeline with reranker |
| 5 | Multimodal support for figures and tables |
| 6 | Comprehensive evaluation against baselines |

---

## Ablation Studies (Planned)

- Remove aspects (single DocID per paper)
- Remove ordered segments (flat term sets)
- Greedy vs unordered decoding
- With/without reranker
- With/without figures/tables
