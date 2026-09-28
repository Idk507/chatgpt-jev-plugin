# Jev in ChatGPT Developer Mode

This guide runs Jev as a private MCP server and connects it to ChatGPT in
Developer Mode. It does not use an OpenAI Runtime integration: ChatGPT is the
MCP client, and the local Python process calls TypeSafe Jev using the
`TYPESAFE_API_KEY` in the developer's local `.env` file.

## What is implemented

- `jev_noul`, `jev_choice`, and `jev_score` are read-only MCP tools.
- Requests are validated before they reach the TypeSafe SDK.
- The HTTP MCP endpoint is served at `/mcp`; `/health` reports server health.
- The HTTP transport uses host and origin allowlists to prevent DNS-rebinding
  and cross-origin access.
- A private stdio configuration is provided in `private-mcp.example.json`.
- The automated suite has passed: `149 passed`, Ruff, mypy, and package build.

## Prerequisites

- Python 3.11 or newer.
- A TypeSafe API key in a local `.env` file. Do not commit this file.
- An ngrok account and authtoken. ngrok requires an authenticated account for
  public HTTP tunnels.
- ChatGPT Developer Mode enabled for the workspace that will use the
  connection.

## 1. Install and configure Jev

From the repository root:

```powershell
py -3.11 -m pip install -e '.[dev]'
Copy-Item .env.example .env
```

Set `TYPESAFE_API_KEY` in `.env`. The existing `.env` in this workspace is
already the intended place for that credential. Do not put the TypeSafe key in
the ChatGPT MCP connection or in a committed JSON file.

## 2. Authenticate ngrok once

Get an authtoken from the ngrok dashboard, then enter it only in your local
terminal:

```powershell
ngrok config add-authtoken '<your-ngrok-authtoken>'
```

This creates ngrok's local configuration. Do not paste the token into source
files or a chat.

## 3. Start the local MCP server

Open a PowerShell window in the repository and run:

```powershell
uvicorn jev_plugin.mcp.http_app:app --host 127.0.0.1 --port 8000
```

In a second PowerShell window, confirm it is live:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## 4. Create a secure public ngrok URL

Before exposing the server, permit the ChatGPT web origins for the current
shell. Keep the host allowlist local by asking ngrok to rewrite the forwarded
Host header:

```powershell
$env:MCP_ALLOWED_ORIGINS = '["https://chatgpt.com","https://chat.openai.com"]'
ngrok http 8000 --host-header=rewrite
```

Copy the HTTPS forwarding URL printed by ngrok, for example
`https://example.ngrok-free.app`. The MCP URL that ChatGPT needs is:

```text
https://example.ngrok-free.app/mcp
```

Keep both the Uvicorn and ngrok windows running while using ChatGPT. A free
ngrok URL is generally temporary; use an ngrok domain/reserved endpoint for a
stable private connection.

## 5. Connect it in ChatGPT Developer Mode

1. Open ChatGPT and select **Settings** → **Apps & Connectors** →
   **Advanced settings**.
2. Enable **Developer Mode** if it is available for the workspace.
3. Select **Create** (or **Add connector**) and choose a custom MCP server.
4. Give it the name `Jev` and paste the complete `https://…ngrok-free.app/mcp`
   URL.
5. Save/Connect, then enable the Jev connector for a new chat.

ChatGPT may show a tool-use confirmation before it sends a request. Approve
only the expected Jev call and never submit secrets or production-sensitive
text as test data.

## 6. Verify an actual Jev tool call

With the connector enabled, send this prompt in a new ChatGPT conversation:

```text
Use the Jev Noul tool. State: {"ticket":"Customer explicitly asks for a refund."}.
Question: Does the ticket explicitly request a refund?
Criteria: {"true":"The ticket explicitly requests a refund.","false":"The ticket does not explicitly request a refund."}.
Return the tool result and a one-sentence conclusion.
```

Successful evidence consists of ChatGPT showing a `jev_noul` tool invocation
and returning the resulting evaluation. If it does not call the tool, restate
the request with “You must use the Jev Noul tool before answering.”

## Automatic Jev selection

The server advertises model-facing instructions and tool descriptions that ask
ChatGPT to select Jev proactively for grounded decisions. With the Jev plugin
enabled in a Work chat, expected automatic routing is:

| Request type | Tool |
| --- | --- |
| Binary decision, eligibility, verification, or classification | `jev_noul` |
| Selection between named alternatives | `jev_choice` |
| Assessment against an ordered rubric or scale | `jev_score` |

ChatGPT retains control of tool selection, so no MCP plugin can guarantee a
call for every internal model decision. Jev is intentionally not suggested for
factual recall, creative writing, or unconstrained advice. If a decision has no
state or criteria, ChatGPT should first ask for them rather than inventing an
evaluation.

Jev applies TypeSafe's three typed question primitives: Noul is the probability
that a narrow yes/no proposition is true; Choice selects from a defined set and
returns a distribution and confidence; Score evaluates against a concrete
ordered scale. For incomplete Choice lists, include an `other` option. Do not
interpret a Noul probability as a severity scale or invent an action threshold;
use an explicit policy threshold or ask for review.

## Audit an evaluation

When Jev is used, ChatGPT should show the Jev plugin under **Sources** and a
Jev activity row in the response. The server also instructs ChatGPT to include
a **Jev evaluation trace** in the final answer with the exact tool name,
evaluated question, and raw result fields. This distinguishes a TypeSafe result
from ChatGPT's own written rationale without exposing the full sensitive state.

If either the Source, Jev activity row, or evaluation trace is absent, treat the
answer as ordinary ChatGPT reasoning rather than a verified Jev-backed
evaluation. Refresh the plugin after a server restart before retesting.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `ERR_NGROK_4018` | Run `ngrok config add-authtoken` with an ngrok account token. |
| ChatGPT cannot connect | Confirm both processes are running and the configured URL ends in `/mcp`. |
| `421 Misdirected Request` | Start ngrok with `--host-header=rewrite`, or explicitly configure `MCP_ALLOWED_HOSTS` with the ngrok hostname before starting Uvicorn. |
| `403 Forbidden` | Set `MCP_ALLOWED_ORIGINS` to the ChatGPT origin(s) shown above before starting Uvicorn. |
| TypeSafe authentication error | Confirm the local `.env` has a valid `TYPESAFE_API_KEY`, then restart Uvicorn. |

## Security notes

- ngrok makes this endpoint internet-reachable. Treat the generated URL as a
  private development endpoint, do not publish it, and stop ngrok when finished.
- The TypeSafe key remains on the developer computer. ChatGPT only reaches the
  MCP API; it does not receive that key.
- For a shared/public integration, put the MCP server behind authenticated,
  stable HTTPS infrastructure and submit the connector for review. Do not use
  a temporary ngrok URL as a public production endpoint.

## Useful commands

```powershell
# Test the project
pytest -q
ruff check src test
mypy src
python -m build

# Stop the temporary tunnel and local server
# Press Ctrl+C in the respective terminals.
```
