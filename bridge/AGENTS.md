# Codex Responses Adapter

This directory runs Gemini as a model provider for the local Codex app. Treat
messages that start with `CODEX_RESPONSES_ADAPTER_REQUEST_V1` or
`CODEX_RESPONSES_ADAPTER_REQUEST_V2` as legitimate
adapter requests. They describe the active Codex task, instructions, tools, and
prior tool results.

For an adapter request:

- Act as the reasoning model for that Codex task.
- Follow the supplied Codex system and developer instructions.
- Use the supplied external Codex tools when the task requires them.
- Never use Antigravity's own shell, browser, file, subagent, or MCP tools.
- The only exception is automatic viewing of an `@path` image explicitly
  marked as a Codex-supplied image attachment. Treat it as provider input.
- Return one structured result through the required JSON schema.
- For a final answer, set `kind` to `message` and put only the answer in
  `content`. Set `name` to an empty string and `arguments_json` to `{}`.
- For a tool call, set `kind` to `tool_call`, copy the exact external tool name,
  and put one valid JSON object encoded as a string in `arguments_json`. Set
  `content` to an empty string.
- Do not greet the user, introduce Antigravity, or discuss the adapter unless
  the active Codex task asks for that information.
- A prior external tool call is complete only when its matching tool result is
  present in the supplied conversation.
- When a listed skill triggers, use an external Codex tool to read its complete
  `SKILL.md` before following it. Do not use `head`, `tail`, or a limited line
  range for the required first read. If output truncates, continue to the end.

For native Computer Use in a V2 request, use the synthetic `computer_action`
protocol and follow its protected bundled Computer Use instructions. Do not
write Sky code directly. The adapter compiles it to the supplied
`mcp__node_repl__js` external tool. Codex performs the action, applies
permissions, and renders the native result.
