# Initial release validation

Validated locally on macOS arm64, Python 3.12, 2026-10-28:

- 20 automated tests passed, including actual Docling PDF parsing, LlamaIndex retrieval, source integrity checks, acquisition rejection, citation graph mocks, isolated answer/auth/usage mocks, and a real MCP STDIO session exposing all seven tools.
- Separate loopback Streamable HTTP smoke test exposed all seven tools and successfully called `list_papers` on an isolated empty library.
- Codex skill passed `quick_validate.py`.
- Python modules compiled and wheel/source distribution built successfully.
- Publication scan excluded private PDFs, databases, API keys, local configuration, personal filesystem paths and historical scientific artifacts.

No live answer-model invocation or paid API call was made for these tests. Mock usage values are fixtures, not measured scientific-call consumption. Coordinator token consumption is unavailable in this release record and is not represented as zero. No scientific benchmark or broad corpus evaluation was run.

GitHub Actions reruns the synthetic test suite in Linux/Python 3.12; its status is separate from this local validation. Transitive dependency resolution and parser model downloads can change environment behavior. Only direct dependencies are version constrained; this is not a fully hermetic build.
