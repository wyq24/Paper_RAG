# Bounded citation discovery

Choose 2–20 coherent seeds from your own active library. Put their verified metadata in a private JSON array:

```json
[{"paper_id":"YOUR_ID_1","title":"Exact title one","doi":"10.xxxx/one"},
 {"paper_id":"YOUR_ID_2","title":"Exact title two","doi":"10.xxxx/two"}]
```

```bash
paper-rag-discover --seed-file /private/seeds.json --out /private/snapshots/run-001 --max-requests 150 --citers-per-order 50 --max-candidates 500 --queue-size 40
```

OpenAlex is the provider. Seed title/DOI matching is required; unresolved identities remain unresolved. Provider APIs can be unavailable or require account access: errors are retained, and no paid service fallback occurs. Candidate identity is provider-only until separately cross-checked. No external LLM is invoked.

Expansion is one bounded neighborhood: seed references and sampled citing works, with unexpanded reference stubs. Ranking computes weighted normalized bibliographic coupling, sampled co-citation, multi-seed links and seed-community bridges; exact supporting IDs are retained. FOUNDATIONAL, EMERGING, ADJACENT and BRIDGE queues have diversity controls. A TF-IDF/SVD title/abstract baseline is lexical-semantic, not an embedding-model benchmark. High citation count and citation edges do not establish scientific validity or methodological inheritance.

Outputs include graph/edge JSONL, candidate metadata SQLite, rankings CSV, per-candidate relations, topic communities, sampling coverage, request ledger, usage and hash manifest. Human relevance review is mandatory; insufficient metadata can result in fewer candidates than requested.

Rerun the same command to resume an **unfinished** run from cached requests; `--offline` prohibits uncached network calls. Completed snapshots are frozen and reject overwrite. Use a new output directory for an update; each snapshot is versioned independently. Failed cached responses remain preserved, so retry a changed provider condition in a new run. This is cached resumability, not automatic background synchronization or graph-delta scheduling.

To expose a completed snapshot through MCP, set `citation_snapshot` in your private configuration to its absolute directory. The reader validates manifest hashes. Existing snapshots remain untouched. Import selected candidates only after explicit user authorization, using acquisition/ingestion; discovery itself never writes papers into the core library.
