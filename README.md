# Paper RAG · Scientific Library

Build your own source-first scientific literature library with Codex. Incrementally ingest your PDFs, retrieve complete source sections, inspect original PDF pages, audit citation anchors, and explore bounded citation networks through seven MCP tools.

**Research Preview.** This is a reusable implementation, not a certified scientific QA system. Literal quotation checks do **not** establish semantic entailment or correct method ownership. No personal papers, databases, credentials, or historical evaluation records are distributed.

## Quick start

Requires Python 3.11–3.13 on macOS or Linux (Windows: WSL), disk space for parser models, and internet for initial dependency/model downloads. No paid LLM API is required.

```bash
git clone https://github.com/wyq24/Paper_RAG.git
cd Paper_RAG
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
paper-rag init
paper-rag ingest /absolute/path/paper.pdf --title 'Verified paper title' --doi '10.xxxx/example'
paper-rag retrieve 'What are the label definitions and exclusion criteria?'
```

The default private library is `~/.local/share/paper-rag`; configuration is `~/.config/paper-rag/config.json`. Keep data outside this checkout. `PAPER_RAG_CONFIG` selects a different configuration. `init` never replaces an existing configuration. Parsing may download Docling model weights on first use. Image-only PDFs and undecoded formulas can remain inaccessible: current ingestion disables OCR and table reconstruction.

## Use with Codex

Open this repository in Codex. Its repository skill lives at [.agents/skills/scientific-library/SKILL.md](.agents/skills/scientific-library/SKILL.md). Ask:

> Use the scientific-library skill. Initialize my own private library and add these PDFs. Preserve originals and show ingestion receipts.

> Search my library for evidence about this question. Fetch full parent sections, distinguish author methods from comparators, show missing evidence, and audit citations.

The skill is an agent workflow, **not a background watcher**. Supplied papers are ingested when you ask the agent; `paper-rag sync-inbox` processes PDFs placed in the configured library's `inbox` when invoked. Discovery candidates require explicit import instructions.

Use GitHub **Use this template** to create your own repository, or fork it to maintain your own code, or clone it and ask Codex to configure your preferred new repository. Your library remains private and separate from the Git repository.

## MCP: connect your existing chat model

```bash
# STDIO, for a local MCP client
paper-rag-mcp
# Streamable HTTP, loopback only
paper-rag-mcp --transport streamable-http
```

The HTTP URL is `http://127.0.0.1:8765/mcp`. Set `PAPER_RAG_PORT` to change it. [MCP and private tunnel setup](docs/MCP.md) explains ChatGPT access. GitHub hosts **code**, not the running server. Your computer must run the service/tunnel. The chat application's selected model composes the answer; these MCP tools do not invoke another model.

| Tool | Purpose |
|---|---|
| `list_papers` | Find active papers and IDs |
| `search` | BM25 + hierarchical source-first evidence |
| `fetch` | Parent sections with provenance and hash validation |
| `evidence_checklist` | Explicit required fields and missing evidence |
| `audit_answer` | Field accounting, literal quote anchors, source integrity |
| `source_page` | Original PDF page text and optional image |
| `citation_network` | Read a configured frozen citation snapshot |

Manually supplied papers carry a `manual` label and receive a modest 10% boost within retrieved candidates. Citation-discovery imports retain a separate label. These preferences never raise scientific verification status.

## Other workflows

- [Daily operations, acquisition and optional answers](docs/OPERATIONS.md)
- [Bounded citation discovery and incremental snapshots](docs/DISCOVERY.md)
- [Architecture, verification boundaries and testing](docs/VALIDATION.md)
- [Privacy and contribution rules](AGENTS.md)

```bash
python -m unittest discover -s tests -v
```

Tests use synthetic papers and mocked citation providers. They do not ingest a research corpus or run a scientific benchmark. Parsing tests use actual Docling/LlamaIndex; initial model download may be needed.

## 中文说明

这是最新版科研文献工作流的可复用代码版本：增量入库、全文获取与去重、父章节检索、证据完整性检查、原始 PDF 页面取证、引用网络，以及七个 MCP 接口。新用户从空库建立自己的知识库，不依赖作者的 87 篇历史语料。

使用 Codex 打开仓库并调用仓库中的 scientific-library skill 即可按需执行。论文全文、数据库、问题记录和引文快照存放在私有数据目录，不能提交到 GitHub。审计通过只说明字段和原文锚点检查通过，不代表科学结论、方法归属或整体准确率得到认证。原项目的未完成金标准与未运行 benchmark 状态没有被这次软件打包改变。

License: MIT for this repository's code. Dependencies and downloaded documents retain their respective licenses.
