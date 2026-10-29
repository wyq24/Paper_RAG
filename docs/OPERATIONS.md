# Daily operations

Activate the installation's virtual environment first. All commands use the same private config (`PAPER_RAG_CONFIG`, or `paper-rag --config /absolute/config.json`).

```bash
paper-rag status
paper-rag list 'title or DOI'
paper-rag ingest /absolute/paper.pdf --title 'Verified title' --doi '10.xxxx/example'
paper-rag sync-inbox
paper-rag retrieve 'English scientific retrieval terms' --paper-id PAPER_ID
paper-rag deactivate PAPER_ID
paper-rag restore PAPER_ID
```

Ingestion retains original input, saves a source copy and hashes, Docling documents/chunks, hierarchical nodes and a receipt. Identical files deduplicate by SHA-256. Different versions remain distinguishable; do not assume title similarity establishes version identity. Index cache fingerprints change with active corpus contents. The MCP reads current active records; adding papers normally requires no tool-schema redeployment.

## Acquire requested papers

Resolve bibliographic identity before downloading. Prepare a private JSON array:

```json
[{"title":"Exact verified article title","doi":"10.xxxx/example","pmcid":"PMC1234567","pdf_urls":[{"url":"https://publisher.example/paper.pdf","doi":"10.xxxx/example","version":"published"}]}]
```

Omit fields you cannot verify. `pdf_urls` and/or `pmcid` supply full-text routes; bioRxiv DOI entries also have a direct preprint route. This is not an unrestricted literature search engine.

```bash
paper-rag-acquire --help
paper-rag-acquire /private/requested-papers.json
```

The downloader uses HTTPS and bounded requests/download sizes; verifies title against PDF opening pages; checks existing records; and preserves per-item success/failure receipts. Wrong-title PDFs are not indexed. Unavailable full text remains unavailable, never an abstract silently substituted as full text. Current PMC public S3 metadata is supported; licensing remains the document owner's responsibility. An inactive existing record is reported, not silently restored.

## Optional standalone answer generation

Retrieval and MCP need no LLM credentials. Prefer your chat client's model with MCP. The optional `paper-rag ask` uses a fresh Codex CLI process only after configuring `enable_codex_answer: true` and an explicit available `answer_model` in your private config. Set `answer_effort` as appropriate. It requires `codex login status` to report ChatGPT authentication, rejects OpenAI/Azure API-key environment variables, and never falls back to a paid endpoint.

```bash
paper-rag ask 'Your question' --search-query 'Faithful English retrieval terms'
```

Each invocation writes evidence, first-pass output, events, usage and validation status. No automatic score-improving retries. The caller must review measured usage after each call. Subscription quotas and model availability are account-specific; this package cannot translate tokens into a universal subscription percentage. No live answer-model call is required or exercised by the test suite.

For a Chinese question use faithful English search terms, retaining the original question; do not add expected answer facts. Fetch full parent sections and inspect page images before interpreting formulas or table columns. Explicitly separate direct evidence, inference, missing information, and unresolved ownership.
