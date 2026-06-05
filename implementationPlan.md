# Phase-Wise Implementation Plan: Groww FAQ Assistant

This document outlines the step-by-step, phase-wise implementation plan for constructing the **Groww FAQ Assistant (Mutual Funds & Stocks)**. It bridges the requirements from [problemStatement.txt](file:///c:/Users/hp/Documents/Mutual%20Fund%20Chatbot/docs/problemStatement.txt), [context.md](file:///c:/Users/hp/Documents/Mutual%20Fund%20Chatbot/context.md), and [architecture.md](file:///c:/Users/hp/Documents/Mutual%20Fund%20Chatbot/architecture.md).

---

## Plan Overview & Timeline

The development is divided into **seven (7) progressive phases**, focusing on building a solid foundation first and layering on guardrails, semantic search, and the frontend.

```mermaid
gantt
    title In-Memory Hybrid RAG Chatbot Implementation Roadmap
    dateFormat  YYYY-MM-DD
    section Backend Core
    Phase 1: Setup & Data Ingestion Pipeline        :active, p1, 2026-06-03, 3d
    Phase 2: Ingress Guardrails (PII & Refusals)    :        p2, after p1, 2d
    section RAG Engine
    Phase 3: Similarity Engine & Local Embedding    :        p3, after p2, 2d
    Phase 4: Prompt Engineering & Local LLM Setup   :        p4, after p3, 2d
    Phase 5: Background Scheduler & Hot-Reload      :        p5, after p4, 2d
    section Frontend & QA
    Phase 6: Groww Chat UI & Citation Badging       :        p6, after p5, 3d
    Phase 7: Testing & Verification Verification   :        p7, after p6, 2d
```

---

## Phase 1: Environment Setup & Data Ingestion (Offline Pipeline)

This phase builds the data extraction tooling to compile all public stock metrics and mutual fund brochures into the unified, lightweight `corpus.json` file.

### Step 1.1: Project Initialisation
*   Create a clean Python virtual environment.
*   Establish directory structure:
    ```text
    ├── backend/
    │   ├── ingestion/       # Scrapers, Parsers, Chunkers
    │   ├── app/             # FastAPI App, Guardrails, Search
    │   └── data/            # Local corpus.json and index caches
    ├── frontend/            # HTML, CSS, JS
    └── requirements.txt
    ```
*   Define dependencies in `requirements.txt`:
    `fastapi`, `uvicorn`, `numpy`, `beautifulsoup4`, `pypdf`, `apscheduler`, `requests` (to communicate with local embedding and Groq APIs).

### Step 1.2: Stock Scraping & Extraction Parser
*   Develop a scraping script utilizing `requests` and `BeautifulSoup` to fetch the 5 target URLs:
    1.  Max Financial Services Ltd
    2.  AU Small Finance Bank Ltd
    3.  The Federal Bank Ltd
    4.  Glenmark Pharmaceuticals Ltd
    5.  Indian Bank
*   Extract key statistical tables (P/E ratio, Dividend Yield, Market Cap, 52-week High/Low) and Company Management/Promoter profiles.

### Step 1.3: Mutual Fund PDF Extraction Parser
*   Write a PDF text extraction script utilizing `pypdf` targeting the downloaded AMC factsheets, SIDs, and KIMs.
*   Segment the extracted text based on key section headers to isolate standard scheme details and **Fund Management Data** (qualifications, tenures, other funds managed).

### Step 1.4: Chunking & Unified Schema Compiler
*   Implement a chunker that segments extracted text into ~500–700 characters with a 100-character overlap.
*   Tag each chunk with a distinct `type` (`mutual_fund` or `stock`), a `query_type` (e.g., `expense_ratio`, `exit_load`, `fund_manager_details`, `promoters`), and enriched `source_metadata`.
*   Export the structured array to `backend/data/corpus.json`.

---

## Phase 2: Ingress Guardrails (PII Redaction & Refusal Engine)

Build the defensive gateway layers to block user PII entries and deflect advisory questions instantly.

### Step 2.1: Regex PII Scanner
*   Create `backend/app/guardrails.py`.
*   Implement deterministic scanners using Python's `re` module for PAN, Aadhaar, phone numbers, and email patterns.
*   Write rejection handlers that block queries containing PII before they proceed to vectorization.

### Step 2.2: Advisory Keyword Deflector
*   Compile lists of forbidden tokens matching investment advisory intent:
    *   *Mutual Funds:* `"should I invest"`, `"returns comparison"`, `"buy fund X"`, `"recommend small cap"`.
    *   *Stocks:* `"should I buy AU bank"`, `"price prediction"`, `"is Federal better than Indian bank"`.
*   Develop a keyword token matcher that intercepts matches and returns a customized redirection text pointing to **Groww Academy** and **AMFI** educational portals.

---

## Phase 3: Hybrid Retrieval & Local Vector Index

Implement the local similarity engine to enable rapid, offline matching.

### Step 3.1: Local Embedding Vectorizer
*   Download and run the local embedding model `nomic-embed-text` in Ollama:
    `ollama pull nomic-embed-text`
*   Configure the application to generate 768-dimensional vector embeddings by calling the local Ollama embeddings endpoint (`http://localhost:11434/api/embeddings` or `/api/embed`).

### Step 3.2: In-Memory Cosine Similarity Store
*   Design a `SimilarityIndex` manager that vectorizes the static `corpus.json` at startup and caches the vectors in a NumPy matrix.
*   Write a similarity calculator using dot-product matrix operations to compute Cosine Similarity:
    ```python
    dot_product = np.dot(query_vector, corpus_matrix.T)
    ```
*   Implement the coordinator to fetch the Top-3 matching chunks + metadata.

---

## Phase 4: Groq Cloud LLM & Prompt Synthesis Integration

Connect the similarity matches to the Groq Cloud API to synthesize fact-based, cited responses.

### Step 4.1: Groq API Setup & Configuration
*   Register on the Groq Console (`https://console.groq.com`) and obtain a free API key.
*   Store the Groq API key securely in environment variables as `GROQ_API_KEY`.
*   Establish HTTP requests to Groq's OpenAI-compatible completions endpoint (`https://api.groq.com/openai/v1/chat/completions`) using the Llama 3.3 model (`llama-3.3-70b-versatile`).

### Step 4.2: Prompt Synthesis
*   Develop the system prompt builder that receives top-3 chunks and constructs a strict "answer-only-from-context" instructions template.
*   Enforce structured citations in the LLM instruction:
    *   Mutual Fund: `[Source: Document Title]`
    *   Stocks: `[Source: Stock Name (URL)]`

### Step 4.3: FastAPI Router Endpoints
*   Set up the main POST route `/api/chat` accepting `{ "message": "..." }`.
*   Integrate the PII Guard, Refusal Check, Semantic Search, and Groq API HTTP call.
*   Format the response to return a clean JSON payload:
    ```json
    {
      "status": "success",
      "answer": "...",
      "is_deflected": false,
      "contains_pii": false
    }
    ```

---

## Phase 5: Background Ingestion Scheduler (APScheduler)

Build the dynamic synchronization backend to keep the local corpus fresh.

### Step 5.1: APScheduler Setup
*   Configure `APScheduler` inside `backend/app/main.py` to trigger background sync tasks.
*   Establish a daily cron schedule matching stock market closures (daily at 18:30 IST) and a weekly schedule for mutual fund factsheet checks.

### Step 5.2: Hot-Reload Mechanism
*   Write a synchronization task that executes Phase 1 pipelines, scrapes/downloads fresh data, and rewrites `corpus.json`.
*   Implement an in-app signal to overwrite the runtime cached memory variables within the `SimilarityIndex` manager with the fresh vectors, enabling seamless hot-reloads without server downtime.

---

## Phase 6: Frontend UI & Citation Renderer

Build a sleek, premium, Groww-branded single-page interface with visual citation badges.

### Step 6.1: Sleek Conversational Layout
*   Design a responsive chat interface using pure HTML5 and Vanilla CSS.
*   Incorporate Groww's signature palette (sleek dark modes, deep gradients, clear typography, and subtle micro-animations).
*   Add a prominent, persistent **Facts-Only Disclaimer** and pre-configured **Example Question bubbles** matching the 11 MF query types and stock parameters.

### Step 6.2: Citation Badge Parser
*   Write a Vanilla JS parsing function that scans incoming chat text for `[Source: ...]` patterns.
*   Replace matches dynamically with visual badges:
    *   *Mutual Funds:* A solid, clean badge showing: `📄 Source: Axis Bluechip Fund SID (2024)`
    *   *Stocks:* A clickable hyperlink badge linking the user directly to the stock page: `📈 Source: The Federal Bank Ltd`

---

## Phase 7: Verification & Testing Plan

Verify the complete assembly against all defined success criteria.

### Step 7.1: Automated Unit Testing
*   Write unit tests to verify $100\%$ PII detection rate on multiple dummy PAN, Aadhaar, and phone inputs.
*   Write tests to verify deflection rates on advisory stock/fund questions.

### Step 7.2: RAG Accuracy & Citation Audits
*   Test factual queries matching each of the **11 mutual fund query types** and the **5 stock profiles**.
*   Manually audit the outputs, checking that:
    1.  The facts output by the LLM (Groq) are completely identical to the source data in `corpus.json`.
    2.  Hallucination temperature limits (e.g., setting Groq temperature parameter to `0.0`) are completely enforced.
    3.  Citations match the source chunk and resolve correctly in the UI.
