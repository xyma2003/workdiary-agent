# Configuration and local setup

[Back to the project overview](../README.md)

The app supports SiliconFlow, OpenAI, other OpenAI-compatible endpoints, and
Anthropic. Choose one provider and supply credentials for that provider. The
model names below are the defaults in the current code, not recommendations or
guarantees of availability for your account.

## Quick start

This path uses Python 3.12 and the SiliconFlow configuration already present in
[`.env.example`](../.env.example). Use an installed Python 3.12 or later interpreter;
the commands below name `python3.12` explicitly. Git is needed to clone the project
and to use optional commit enrichment.

Run these commands in a terminal on macOS or Linux:

```bash
git clone https://github.com/xyma2003/workdiary-agent.git
cd workdiary-agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit the new `.env` file in the repository root. Replace the placeholder key with
your own SiliconFlow key; keep only the provider configuration you intend to use:

```dotenv
LLM_PROVIDER=siliconflow
SILICONFLOW_API_KEY=replace-with-your-siliconflow-key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=Qwen/Qwen3-32B
WORKDIARY_TIMEZONE=Asia/Shanghai
```

Start the app from the same directory and activated environment:

```bash
streamlit run app.py
```

Open [localhost:8501](http://localhost:8501). Enter a short work description and
click **生成日报** to make the first model requests. Opening the UI by itself does
not demonstrate that your credentials, model, or endpoint work.

On Windows, create the environment with `py -3.12 -m venv .venv`, activate it with
`.venv\Scripts\Activate.ps1` in PowerShell, and copy the example with
`Copy-Item .env.example .env`. The installation and Streamlit commands are the same.
For an existing checkout, edit your existing `.env` instead of overwriting it.

## Environment precedence and provider selection

The app loads `.env` with `load_dotenv(override=False)`. Variables already present
in the shell or deployment environment take precedence over the file, including
`LLM_PROVIDER`, keys, and endpoint settings. Restart Streamlit after changing the
configuration or runtime data location.

Set `LLM_PROVIDER` explicitly to one of `siliconflow`, `openai`,
`openai-compatible`, or `anthropic`. If it is absent or empty, the code infers a
provider from credentials in this order:

1. `SILICONFLOW_API_KEY` → SiliconFlow.
2. `OPENAI_API_KEY` → OpenAI.
3. `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` → Anthropic.

An explicit provider prevents an unrelated key in your shell from selecting a
different backend. A missing required credential produces a local configuration
error before generation; a nonempty placeholder is not a valid credential check.

## Provider configurations

Replace the placeholder values below. Select one configuration rather than
combining the snippets in the same file.

### SiliconFlow

```dotenv
LLM_PROVIDER=siliconflow
SILICONFLOW_API_KEY=replace-with-your-siliconflow-key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=Qwen/Qwen3-32B
```

`SILICONFLOW_API_KEY` is required. The endpoint and model shown above are defaults
when their variables are omitted. This mode reads its own key and explicitly
passes its endpoint to the OpenAI-compatible client; it does not use
`OPENAI_API_KEY` for SiliconFlow.

### OpenAI

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=replace-with-your-openai-key
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_API_KEY` is required; the model defaults to `gpt-4o-mini`. For the direct
OpenAI API, leave both `OPENAI_API_BASE` and `OPENAI_BASE_URL` unset in your file
**and** shell. The app honors `OPENAI_API_BASE` even in `openai` mode, and the
underlying client can also inherit `OPENAI_BASE_URL`. Provider selection does not
override a custom endpoint or prevent credentials from being sent to that endpoint.

### Other OpenAI-compatible endpoints

```dotenv
LLM_PROVIDER=openai-compatible
OPENAI_API_KEY=replace-with-this-endpoints-key
OPENAI_API_BASE=https://provider.example.com/v1
OPENAI_MODEL=provider-model-name
```

Both `OPENAI_API_KEY` and `OPENAI_API_BASE` are required in this mode. Supply the
key and model identifier issued by that endpoint, rather than reusing credentials
for another provider. Choose a model/endpoint that supports the structured output
used by the extraction node. Local configuration validation does not check that
capability. If `OPENAI_MODEL` is omitted, the code still defaults to `gpt-4o-mini`,
which may not be a model name your endpoint accepts.

### Anthropic with an API key

```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=replace-with-your-anthropic-key
ANTHROPIC_MODEL=claude-sonnet-4-5
```

The model defaults to `claude-sonnet-4-5`. Leave `ANTHROPIC_BASE_URL`,
`ANTHROPIC_AUTH_TOKEN`, and `ANTHROPIC_CUSTOM_HEADERS` unset for the standard direct
API setup. A custom `ANTHROPIC_BASE_URL` is honored by the Anthropic client.

### Anthropic-compatible proxy

```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_BASE_URL=https://your-proxy.example.com
ANTHROPIC_AUTH_TOKEN=replace-with-your-proxy-token
ANTHROPIC_MODEL=your-proxy-model-name
```

Use the endpoint, token, and model identifier provided by your proxy. Leave
`ANTHROPIC_API_KEY` unset for token authentication. When an auth token is present
and an API key is absent, the app adds an `Authorization: Bearer ...` header unless
you supplied an `Authorization` header yourself. When both credentials are set,
the app passes the API key and does not add that token header.

If your proxy requires extra headers, `ANTHROPIC_CUSTOM_HEADERS` accepts
newline-separated `Key: Value` pairs. For example, a quoted multiline `.env` value:

```dotenv
ANTHROPIC_CUSTOM_HEADERS="X-Route: example
X-Client: workdiary"
```

These settings configure an existing Anthropic-compatible proxy; the application
does not provide or deploy one.

## Timeouts, retries, and a local configuration check

| Variable | Default | Accepted value |
| --- | --- | --- |
| `LLM_TIMEOUT_SECONDS` | `60` | A finite number greater than zero |
| `LLM_MAX_RETRIES` | `2` | An integer greater than or equal to zero |

These options are passed to the model client. Retries are client-level retries,
not the number of human revision rounds. The timeout is not a deadline for the
whole report: a report uses multiple model calls, and retries can extend elapsed
time. Human revisions remain limited to three rounds.

From the repository root, this command loads `.env` and checks provider selection,
required variable presence, and numeric settings without calling a model:

```bash
python -c 'from dotenv import load_dotenv; from workdiary_agent.utils import validate_llm_configuration; load_dotenv(override=False); print(validate_llm_configuration())'
```

It does not authenticate a key, contact an endpoint, or verify model availability.

## Work date, Git sources, and runtime files

Set `WORKDIARY_TIMEZONE` to an IANA timezone such as `Asia/Shanghai`. The UI uses it
as the initial work-day setting and lets you change it before generation. With no
configured timezone, the app uses the system timezone; an unrecognized timezone
also falls back to the system timezone and writes a warning to the application log.

For Git enrichment, enter a repository path on the machine running Streamlit and
an author name or email. If the author is left blank, the app tries the effective
Git configuration (`user.email`, then `user.name`), including inherited system or
user settings. It checks exact author identity
within the report day's timezone boundaries; it does not attribute all contributors'
commits to you. Missing Git access or an unresolved author does not stop text-only
generation. New runs freeze the selected source material before the first model
stage, so a retry does not silently read newer commits.

By default, runtime files live at the installed source package's project root
(the repository root in this checkout), independently of the launch directory:

| Path | Contents |
| --- | --- |
| `graph_state.db` | LangGraph checkpoints for unfinished runs and review recovery |
| `history.db` | Saved reports, immutable source snapshots, and pending export-cleanup tasks |
| `exports/` | Markdown exports of saved reports |

For a durable writable directory, set an absolute path before starting Streamlit:

```dotenv
WORKDIARY_DATA_DIR=/absolute/path/to/workdiary-data
```

The same directory contains both databases and `exports/`. `~` is expanded; a
relative path resolves against the process's working directory, so use an absolute
path when launching from different locations. Changing this setting selects a
different storage location; it does not migrate existing reports or checkpoints.
History and unfinished work depend on these local files surviving app restarts.

## Credentials and data boundaries

- Keep real keys and tokens in `.env` or your deployment environment. `.env`, the
  default databases, and `exports/` are excluded by the repository's `.gitignore`;
  that is not encryption or access control for the files.
- Work descriptions, pasted metrics, and selected Git commit subjects are sent
  to the configured provider. Common credential formats are redacted before model
  calls and in new snapshots, but redaction is best-effort. Submit only material
  your chosen provider is allowed to process.
- History, unfinished checkpoints, and exports can contain sensitive work notes,
  earlier inputs, and later manual edits. The app does not claim to encrypt these
  files. Protect the runtime directory and any backups accordingly.
- Saved model metadata includes allowlisted configuration for successfully
  completed stages. API keys and headers are excluded; endpoint identifiers keep
  only the origin, without credentials, paths, queries, or fragments. This is not
  a provider-side model-version attestation or a complete request/retry audit.
- Repository paths are local filesystem access, not a sandbox. Keep the app local
  or supply deployment-level access controls before exposing it to other users.

Configuration behavior is implemented in [`utils.py`](../workdiary_agent/utils.py),
[`paths.py`](../workdiary_agent/paths.py), and
[`time_utils.py`](../workdiary_agent/time_utils.py). The complete variable template
is [`.env.example`](../.env.example).
