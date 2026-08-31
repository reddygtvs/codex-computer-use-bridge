# Codex Update Recovery

This directory is the canonical recovery package for the working full Codex
Gemini adapter, GPT-5.6 Sol None API, and GPT-5.6 Sol Low Fast API Computer Use
integrations.
It contains no OpenAI API key, ChatGPT credential, Codex credential, or
Antigravity session credential.

## What an app update does

A Codex app update replaces `/Applications/ChatGPT.app`. It can replace the
signed Sky service and the bundled Computer Use skill. The update does not
normally remove these user-owned files:

- `~/.codex/config.toml`
- `~/.codex/antigravity-router/`
- the OpenAI API key in macOS Keychain service
  `computer-use-agnostic-openai-api-key`
- `~/Library/LaunchAgents/com.tushar.codex-antigravity-router.plist`
- `~/Library/LaunchAgents/com.tushar.codex-sky-executor-compat.plist`
- this repository

The router finds the newest bundled Computer Use skill at runtime. This lets it
use the skill from the updated app without copying or modifying the app bundle.
The legacy personal Gemini Computer Use skill is not required by the model-picker
integration.

The full Gemini bridge is in user-owned router files. It passes Codex
instructions, state, images, function tools, custom tools, MCP namespaces, and
lazy skill reads through the normal Responses stream. An app update does not
normally replace these files.

## After each Codex update

Run:

```sh
./bridge/repair-after-codex-update.sh
```

The command refreshes the merged model catalog, restores the two LaunchAgents,
restores the router, writes the provider settings through Codex app-server,
checks the app signature, and runs local health checks. It saves a timestamped
backup of `~/.codex/config.toml` before it writes provider settings.
The checks include the single-action and multi-action batch compiler, strict API
schemas, direct API worker loop, Keychain entry, and all picker catalog entries.

Restart Codex once after the command. Test **Gemini 3.7 Flash** with one mouse
click. Then run the same test with **GPT-5.6 Sol None** and
**GPT-5.6 Sol Low Fast**. Confirm that native PiP and the software cursor appear
in all tasks.

## Quick check without repair

Run:

```sh
./bridge/verify.sh
```

If the check passes and the direct pointer test passes, no recovery action is
necessary.

## Update-sensitive points

- A new Sky build can fix or change the Swift cursor crash. Keep the compatibility
  LaunchAgent until a direct test proves that the new build works without it.
- The Codex model catalog can change. The repair command rebuilds the merged
  catalog from `~/.codex/models_cache.json`.
- The bundled Computer Use plugin version can change. The router selects the
  newest installed version.
- OpenAI can change API model aliases, strict schema rules, or Fast tier access.
  Unit tests detect local protocol regressions. A direct API probe detects model,
  credit, and service-tier failures.
- An Antigravity CLI update can change the model name or stream protocol. The
  health check detects process and catalog failures, and a direct task detects
  planning protocol failures.

No recovery step modifies, copies, patches, or signs a file inside the Codex app
bundle.

## Exact Computer Use rollback

The pre-bridge adapter and its Antigravity instructions are stored in:

```text
bridge/snapshots/pre-general-tools/
```

Run this command to restore that exact installed version and restart only the
local router:

```sh
./bridge/rollback-to-computer-use-only.sh
```

This rollback does not change the Codex app, model catalog, Sky service,
Computer Use plugin, or user configuration. Run `install.sh` to return to the
full Gemini bridge.
