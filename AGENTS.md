# Working in this repository

Read `.agents/skills/scientific-library/SKILL.md` for library tasks. Keep all private data outside the repository. Never commit PDFs, source text, credentials, runtime configuration, databases, query records, discovery snapshots, or historical evaluations. User-supplied papers authorize ingestion; citation candidates alone do not.

Preserve original PDFs and historical versions. Use existing incremental ingestion, hash validation and reversible deactivation. Do not rebuild a user's corpus or change scientific verification states to make a test pass. Never infer method ownership from matching terms or a citation edge.

Use deterministic tests and synthetic fixtures. No paid APIs, real answer calls, full-corpus migration, or live tunnel/account changes as part of tests. Optional model use requires explicit configuration and subscription authentication. Do not claim token counts unavailable from actual telemetry.

Before publishing changes: run tests, validate the skill, inspect the staged diff for private data, and report scientific limitations separately from software test results.
