# Harness capability research

This matrix records the upstream source used for ReproForge's initial adapter decisions. Research snapshot: **2026-09-17**. ReproForge does not invent missing flags and does not assume editor extensions are automatically headless.

Installed versions are probed with `<executable> --version` when the user asks for host detection. The initial adapter policy targets the currently documented upstream CLI surface rather than pretending to support an unverified historic semver range.

| ID | Upstream repository | Verified integration | Capabilities / limitations |
| --- | --- | --- | --- |
| `codex` | https://github.com/openai/codex | `codex exec --json --ephemeral` | JSONL events; source also exposes resume/fork and MCP-related execution. Evidence: `codex-rs/exec/src/cli.rs`, `codex-rs/exec/src/exec_events.rs`. |
| `claude-code` | https://github.com/anthropics/claude-code | headless CLI with stream JSON | Stream JSON is a documented product surface. The public repo is not a complete mirror of every product component, so the adapter stays on CLI behavior. Goose's upstream Claude provider is additional source evidence for the stream JSON protocol. |
| `opencode` | https://github.com/anomalyco/opencode | `opencode run --format json` | Current source supports non-interactive run, JSON event output, model selection, session continuation, and server attach. The older `opencode-ai/opencode` repository is archived. |
| `pi` | https://github.com/earendil-works/pi | `pi --mode json -p ...` | Upstream documents interactive, print, JSON-event, and stdin/stdout RPC modes. Pi itself explicitly recommends external sandboxing for permission boundaries. |
| `gemini-cli` | https://github.com/google-gemini/gemini-cli | `gemini -p ... --output-format stream-json` | Official source/docs describe `json` and `stream-json`, with `-p/--prompt` as non-interactive mode. |
| `aider` | https://github.com/Aider-AI/aider | `aider --message ... --yes --no-auto-commits` | Official scripting docs verify one-shot messages and confirmation/auto-commit controls. ReproForge does not claim a structured event stream for this adapter. |
| `goose` | https://github.com/aaif-goose/goose | `goose run ... --output-format stream-json --no-session` | Official docs/source expose headless task execution, JSON/stream-JSON output, providers, recipes, and session management. |
| `cline` | https://github.com/cline/cline | `cline --json ...` | Current repo contains a real CLI/SDK. CLI README documents one-shot/headless CI use and NDJSON output. |
| `roo-code` | https://github.com/RooCodeInc/Roo-Code | archival/import only | Official repository is archived. Its current README states that the Roo Code extension was shut down on **May 15, 2026**. ReproForge therefore exposes no fake launcher. |
| `continue` | https://github.com/continuedev/continue | `cn -p ... --format json` | Official CLI docs/source describe headless print mode, JSON output, and MCP behavior. Model selection remains configuration-driven until a stable CLI flag is explicitly verified. |

## Version policy

A capability record says what ReproForge has verified, not what every historical release supports. Before widening a version range, add upstream evidence and compatibility tests. If an upstream CLI changes, detection should fail visibly rather than silently invoking a guessed replacement.

## Authentication

ReproForge's adapter registry describes invocation, not a promise that authentication is preconfigured. Harness containers do not receive the host home directory. Build a harness image with the executable and deliberately provide supported credentials through narrowly scoped configuration/environment mechanisms.
