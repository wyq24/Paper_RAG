# Implementation and validation boundaries

The public package adapts the latest personal Scientific Library workflow into a configurable empty-library installation. It retains Docling parsing, LlamaIndex hierarchical nodes, BM25 and parent expansion; SHA-256 provenance; immutable version bundles and reversible activation; structured evidence checklists; original-page rendering; structural answer audits; bounded citation analysis; controlled full-text acquisition; and read-only MCP access.

The unsuccessful destructive field-first retrieval workflow is not included. No new broad RAG architecture or corpus migration is required. An optional `base_root` adapter can read the original historical corpus format; it is unnecessary for new users and is not a general database importer.

## What tests establish

Synthetic fixtures exercise actual PDF parsing and hierarchical retrieval, deduplication, activation, query caching, original-page rendering, source tamper rejection, wrong-document rejection, missing fields, fabricated quotes and path traversal. Mocked citation-provider tests verify exact shared-reference/citing IDs, normalized similarity, offline behavior and frozen snapshots. MCP transport tests check the actual exposed directory and calls.

These are software regression tests, not scientific accuracy measurements. In particular, a false statement attached to an authentic quote can pass literal matching. The suite explicitly preserves this limitation: audit reports semantic entailment and ownership as NOT_VERIFIED. Checklist completion also does not prove every scientifically relevant condition was enumerated.

## Remaining limits

- PDFs with poor text extraction, complex tables, formulas or supplementary-only definitions need original-page/manual review. OCR and table reconstruction are currently off.
- BM25 is terminology-sensitive; Chinese questions benefit from faithful English retrieval phrasing.
- Parent context is bounded; a user must follow pagination and inspect all relevant sections.
- Citation coverage is sampled and provider-dependent; current graph does not cover the entire literature.
- Full-text title verification is conservative and can reject legitimate documents. It is not a scientific validation of their contents.
- Exact quote and hash checks cannot certify causal claims, experimental equivalence, comparator attribution or generalization.
- MCP is read-only for the corpus, but queries/receipts contain potentially sensitive research interests and must remain private.

Historical project conclusions remain `CORE_GOLD_INCOMPLETE`, `ABSTENTION_UNRESOLVED`, `BENCHMARK_NOT_RUN`. Packaging does not change them or certify production readiness. Personal historical results and source documents are not published here.
