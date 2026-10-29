---
name: scientific-library
description: Build and maintain a personal source-first scientific literature RAG from supplied PDFs or verified paper links, with incremental ingestion, deduplication, evidence-grounded questions, original-page checks, citation discovery and read-only MCP. Use for requests to add papers to this library, search or ask its RAG, or set up its MCP; do not apply to unrelated uploads or automatically import discovered citations.
---

# Scientific Library

Use the repository's installed `paper-rag` tools. Read [operations](../../../docs/OPERATIONS.md) for command details, [MCP](../../../docs/MCP.md) for connectors and [discovery](../../../docs/DISCOVERY.md) for citation analysis.

## Initialize safely

1. Read the repository README and AGENTS.md. Locate the active Python environment and `PAPER_RAG_CONFIG`; do not assume the author's filesystem, corpus or model availability.
2. Install the package if needed and run `paper-rag init`. Default private state lives outside the repository. Existing configuration must not be overwritten.
3. Keep PDFs, databases, credentials, source text, query records and historical artifacts out of Git. Never rebuild an existing library to perform an incremental operation.

## Add supplied papers

A user's request to add a paper authorizes normal local ingestion. Verify title/DOI/version; inspect existing records; obtain accessible full text without bypassing access controls. Use `paper-rag ingest` for a PDF or the bounded `paper-rag-acquire` manifest workflow for links. Do not invent missing metadata or index an abstract as full text. Preserve failed downloads and receipts. Report added, already present and unavailable items separately. Verify retrieval after ingestion. No automatic citation-candidate promotion.

## Answer a scientific question

1. Identify relevant papers, formulate faithful search terms and create an evidence checklist with question-specific required conditions.
2. Search and fetch parent sections, including method definitions and comparison headings. Follow pagination.
3. Distinguish the author's method, comparison baseline, cited work and unresolved attribution. Matching terms or citation links are not proof of ownership.
4. For tables, equations, figures and ambiguous definitions inspect `source_page`; disclose extraction or visual-review gaps.
5. Compose only from delivered evidence. Provide title, DOI/source, page and heading; distinguish observations from hypotheses. State missing evidence and assumptions.
6. Audit every checklist field using literal quotes or explicitly missing/not-applicable reasons. Report structural validation separately from semantic judgment. An audit success is not scientific certification.

Prefer the current chat's model with MCP. Optional standalone `ask` requires explicit model configuration and subscription authentication; no paid API fallback. Inspect real usage after each call and preserve first-pass outputs. Do not claim unavailable token telemetry.

## Discover and share

Use bounded citation discovery only when requested. Preserve identity confidence, sampling coverage, snapshot dates and exact shared IDs; human review decides relevance. Keep code in GitHub and data in private storage. For a new user repository, honor their destination and sharing request; do not publish data or credentials. Do not automatically alter a running tunnel or workspace permissions.

Stop after the requested operation. Do not launch benchmarks, gold generation, corpus expansion or review loops as incidental verification.

## User selection labels

Directly supplied papers are labeled `manual` by default and receive a 1.10 multiplier when reranking already retrieved candidates. For citation-discovery batches explicitly use `--selection-label citation_discovery` (acquisition manifest: `"selection_label": "citation_discovery"`). Never equate permission to import a discovered batch with individual manual curation. Existing directly requested papers can be marked with `paper-rag mark PAPER_ID --label manual`. Labels are reversible private overlays; they never change scientific verification status. Use `retrieve --label manual` only when the user asks to restrict scope. Keep uncertain historical provenance unclassified/historical rather than inventing manual labels.
