# Multiagent PDF Processing Workflow

Proof-of-Concept multiagent workflow using LangGraph to orchestrate document extraction, classification, and reporting with human-in-the-loop interactivity.

> [!NOTE]
> This project was developed with assistance from AI tools.

## Overview

PDF documents go through a multi-step workflow designed for mortgage loan document classification. The workflow extracts content, classifies documents into mortgage-related categories, supports human-in-the-loop review for uncertain classifications, and generates a summary report.

### Architecture

```
                                   ┌─────────────────────┐
                                   │   Human Review      │
                                   │ (if unknown docs)   │
                                   └──────────┬──────────┘
                                              │
┌─────────┐    ┌─────────────────┐    ┌───────┴───────┐    ┌─────────────────┐    ┌─────────┐
│  START  │───▶│  PDF Extractor  │───▶│  Classifier   │───▶│ Report Generator│───▶│   END   │
└─────────┘    └─────────────────┘    └───────────────┘    └─────────────────┘    └─────────┘
                       │                      │
                       ▼                      ▼
               ┌────────────────┐      ┌────────────────┐
               │ Document Cache │      │ Document Cache │
               │  (extraction)  │      │(classification)│
               └────────────────┘      └────────────────┘
```

### Components

| Component | Type | Description |
|-----------|------|-------------|
| PDF Extractor | Agent | Extracts text from PDFs (with OCR fallback), generates summaries and key entities via LLM |
| Classifier | Agent | Categorizes documents into mortgage-related types with confidence scores |
| Human Review | Utility | Interactive CLI for manually classifying uncertain documents |
| Report Generator | Utility | Produces PDF report summarizing all processed documents |
| Document Cache | Utility | SQLite-based cache for LLM results, keyed by content hash |

## Installation

### Prerequisites

- Python 3.11+
- OpenAI API key (or compatible endpoint)
- CUDA-capable GPU (optional, for faster OCR)

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=sk-...

# Optional - Custom OpenAI-compatible endpoint
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Optional - LangFuse observability
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Optional - OCR settings
OCR_ENABLED=true
OCR_MIN_CHARS_PER_PAGE=50
OCR_MIN_FREE_VRAM_GB=3.0
```

## Usage

### Sample Data

Generate fictional document input set for testing:

```bash
python create_sample_pdfs.py
```

Creates 28 sample PDFs in `input_pdfs/`:
- 25 machine-generated PDFs covering all document categories
- 3 image-based PDFs (scanned documents) for OCR testing

File names omitted from context submitted for classification to better test models, but could easily be reintroduced to allow more probable scenarios.
### Basic Usage

```bash
# Place PDFs in input_pdfs/ directory, then:
python main.py

# Output report generated in output_reports/
```

### CLI Options

```bash
python main.py [OPTIONS]

Options:
  -i, --input-dir PATH      Input directory containing PDFs (default: ./input_pdfs)
  -o, --output-dir PATH     Output directory for reports (default: ./output_reports)
  --no-checkpointing        Disable LangGraph state checkpointing
  --thread-id ID            Thread ID for checkpointing (auto-generated if omitted)
  --session-id ID           Session ID for LangFuse tracking

Cache options:
  --cache-stats             Display cache statistics and exit
  --clear-cache             Clear document cache before processing
  --no-cache                Disable caching for this run
```

## Document Categories

Documents are classified into mortgage loan process categories:

| Category | Description |
|----------|-------------|
| Loan Application | Mortgage application forms, 1003/URLA forms |
| Pre-Approval Letter | Conditional approval letters from lenders |
| Income Verification | W-2 forms, pay stubs, 1099s, tax returns |
| Employment Verification | Employer letters confirming employment/salary |
| Bank Statement | Checking, savings, investment account statements |
| Credit Report | Credit scores, credit history, tri-merge reports |
| Property Appraisal | Property valuation reports, comparable sales |
| Title Report | Title search results, title insurance, lien searches |
| Homeowners Insurance | Insurance quotes, policy declarations |
| Closing Disclosure | Final loan terms, HUD-1 settlements, cost breakdowns |
| Loan Estimate | Initial loan terms and cost estimates |
| Deed/Mortgage Note | Property deeds, mortgage notes, trust deeds |
| HOA Documentation | HOA disclosures, CC&Rs, association financials |
| Gift Letter | Letters documenting gifted funds for down payment |
| Identity Verification | Driver's license, passport, government ID copies |
| Property Tax Statement | Tax assessments, property tax bills |
| Divorce Decree/Legal Judgment | Divorce papers, court orders, legal settlements |
| Bankruptcy Documentation | Bankruptcy filings, discharge papers |
| Unknown Relevance | Documents not fitting mortgage loan categories |

## Human-in-the-Loop Review

When documents are classified as "Unknown Relevance", the workflow prompts for manual review:

```
HUMAN REVIEW: Unknown Relevance Documents
--------------------------------------------------
Document: misc_document.pdf
Pages: 2
Summary: A document containing...
Key Entities: ...

Select category (1-18, or 0 to skip): 
```

Options:
- Select a category number to reclassify
- Confirm as "Unknown Relevance" (irrelevant to mortgage)
- Skip to keep AI classification

Human-reviewed documents are marked in the final report with their original AI classification noted.
