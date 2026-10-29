# MCP and ChatGPT access

Run `paper-rag init` and import your papers before connecting. Example local client configuration (replace paths):

```json
{"mcpServers":{"scientific-library":{"command":"/absolute/Paper_RAG/.venv/bin/paper-rag-mcp","env":{"PAPER_RAG_CONFIG":"/absolute/private/config.json"}}}}
```

For Streamable HTTP use `paper-rag-mcp --transport streamable-http`; the listener binds only 127.0.0.1. This server implements no independent public HTTP authentication. Do not expose it directly to the internet.

## OpenAI private tunnel

Follow the current [official secure MCP tunnel documentation](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) for account availability, client installation and workspace authorization. The runtime connects outbound; GitHub is only the code repository.

1. Create a tunnel in your OpenAI Platform organization and authorize the **ChatGPT workspace actually using the connector**. Organization membership alone does not grant workspace access.
2. Install the official `tunnel-client`; create its runtime credential privately.
3. With this repository's virtual environment active, run:

```bash
python scripts/connect_tunnel.py --client /absolute/path/tunnel-client
```

4. Enter the tunnel ID and hidden runtime key locally. The helper does not save the key. Create/select the ChatGPT MCP connector using the tunnel. This MCP implementation has no application-level OAuth; select no additional authentication only where the authorized tunnel supplies access control. Never paste the runtime credential into chat or the MCP URL.
5. In a fresh chat inspect the tool directory and test all seven tools. After changing tool definitions refresh/reconnect the connector; active chats can retain stale tool lists.

The helper uses the runtime CLI's `runtimes connect` and `runtimes status` commands. Client versions can differ; consult `--help` and the official documentation if unsupported. It does not change workspace permissions or turn off network restrictions. Your Mac/Linux runtime must stay online.

## Acceptance prompt

> List the actual Scientific Library tools available. Find one paper in my library. Create an evidence checklist, retrieve a methodological question, fetch its parent section, and inspect an original PDF page. Audit every field with exact quotes or explicitly missing evidence. Query citation_network; if no snapshot is configured, report that. Do not interpret audit success as semantic certification, or citation relationships as method ownership. Report actual failures without inventing tool results.

No ingestion endpoint is exposed through MCP. Import through the local CLI/skill; remote clients receive read-only library tools (query/audit logs are still written locally).
