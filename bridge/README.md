# Codex Computer Use Bridge

This integration adds `Gemini 3.7 Flash`, `GPT-5.6 Sol Instant`, and
`GPT-5.6 Sol Low Fast` to the Codex model catalog. Gemini requests use the
authenticated Antigravity CLI. The two GPT planners use the official prepaid
OpenAI Responses API. Existing OpenAI models continue through the ChatGPT Codex
subscription endpoint.

Codex continues to own task history, native tool cards, permissions,
`node_repl`, `@oai/sky`, and Computer Use rendering. For Gemini, the router now
passes the active Codex instructions, conversation state, image attachments,
tool catalog, tool results, and response controls to one persistent Antigravity
planner session. Gemini can use normal function tools, custom tools,
namespaced MCP tools, and independent parallel tool calls through the standard
Codex Responses stream. The router binds only to `127.0.0.1`. The OpenAI API
key stays in the macOS Keychain and is never saved in this repository or
written to router logs.

Codex supplies the skill catalog in its normal instructions. Gemini reads the
complete selected `SKILL.md` through a Codex tool only when the task triggers
that skill. Deferred connector schemas use the same pattern: Gemini first asks
the router for the exact schema, then emits the real Codex tool call. Core tool
schemas stay exact from the first turn.

The router loads the installed native Computer Use skill once for each Gemini
planner session. This protected preload preserves the previously verified
Computer Use path while other skills remain lazy. The router keeps the
Antigravity `stream-json` process alive and sends only new conversation items
on later steps. Gemini chooses one action or an ordered action batch using the
same native skill judgment as an OpenAI model. The router validates every
action before it compiles the batch into one exact Sky call. It reads fresh
state after the batch. Gemini cannot supply arbitrary JavaScript.

The legacy personal `computer-use-gemini` skill is not part of this path. The
router loads the newest bundled Codex Computer Use skill directly. The small
router contract defines only the structured output format and action allowlist.

For both GPT API models, the router sends a compact task and state history to
the official Responses API. The API must return one strict action function or
one final-message function. The same allowlist validator and Sky compiler used
for Gemini then produces the native Codex tool call. No browser planner,
ChatGPT cookie, Codex OAuth token, or private ChatGPT backend is used.

The login LaunchAgent sets Swift's supported legacy executor mode in the macOS
GUI launch domain. ChatGPT starts each native Sky service from this domain, so
replacement services receive the setting before their first cursor action.
This avoids the cursor animation crash in Sky service builds `1000901` and
`1000919` on macOS 26. It does not change the app bundle, native binary, code
signature, or Computer Use tool path.

Installed files:

- `~/.codex/antigravity-router/`
- `~/.codex/skills/computer-use-chatgpt-instant/SKILL.md`
- `~/Library/LaunchAgents/com.tushar.codex-antigravity-router.plist`
- `~/Library/LaunchAgents/com.tushar.codex-sky-executor-compat.plist`
- Provider and catalog entries in `~/.codex/config.toml`

After installation, start a new task and select **Gemini 3.7 Flash** or
**GPT-5.6 Sol Instant** or **GPT-5.6 Sol Low Fast** from the normal model
picker. Restart Codex only if the picker does not refresh. The GPT entries
require the prepaid API key in the Keychain service
`computer-use-agnostic-openai-api-key`.

The native macOS Computer Use backend controls the live Mac. This router does
not create a separate virtual desktop. Codex still shows and approves the native
tool calls before it executes them.

Pointer movement is visible for mouse actions such as click and drag. Keyboard
and text-entry actions do not move the pointer.

Gemini can batch stable actions without another model turn. It ends the batch
when a later action needs fresh state, model judgment, or confirmation. This
matches the bundled skill instruction to perform one or more actions and then
fetch current state.

## GPT API status

`GPT-5.6 Sol Instant` maps to `chat-latest`. `GPT-5.6 Sol Low Fast` maps to
`gpt-5.6-sol` with low reasoning and `service_tier: fast`. Both use strict
function calls and the current bundled Computer Use skill. The adapter stops
with a clear error when the key is missing, API credit is unavailable, or a
response fails validation. It never changes to another model silently.

This repository is the canonical recovery copy. After a Codex update, run
`repair-after-codex-update.sh`, restart Codex once, and run one direct pointer
test. See [UPDATE_RECOVERY.md](docs/UPDATE_RECOVERY.md) for the persistence map and
the exact recovery procedure. To restore the exact Computer Use-only adapter
that was installed before the general Codex bridge, run
`rollback-to-computer-use-only.sh`.
