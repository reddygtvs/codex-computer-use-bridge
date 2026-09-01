# Installed-path test results

Test date: 2026-08-29

## Native Antigravity resume limit fix

Test date: 2026-08-31

The router now captures the `conversation_id` from the Antigravity
`stream-json` initialization event. Worker restarts and pool eviction resume
the same native conversation and send only the newest Codex delta. A missing
conversation uses a bounded checkpoint with exact active user text and newest
native state.

The local regression suite passed 67 tests. The added tests cover process
resume, pool eviction, a long Codex history, invalid conversation IDs,
instruction and tool changes, and exact recovery text. A live no-turn CLI
smoke test created and resumed the same Antigravity conversation ID.

## Initial adapter smoke tests

| Check | Result | Wall time |
| --- | --- | ---: |
| Native model picker list | Passed. Gemini and seven OpenAI models were listed. | 0.2 s |
| Gemini native `mcp__node_repl` call | Passed. Codex showed the native tool start and completion events. | 16.08 s |
| GPT-5.6 Sol Low subscription passthrough | Passed. | 3.24 s |
| GPT-5.6 Chat alias on Codex subscription endpoint | Rejected as unsupported. | 2.0 s |
| Python syntax and LaunchAgent plist validation | Passed. | under 0.1 s |

## Paired speed sample

| Task | Gemini 3.7 Flash Low | GPT-5.6 Sol Low |
| --- | ---: | ---: |
| Exact direct response | 6.92 s | 3.24 s |
| One native `node_repl` action and final response | 16.08 s | 14.20 s |

GPT-5.6 Sol Low was 3.68 s faster for the direct response and 1.88 s faster
for the native tool loop. These are single-run transport samples. They are not
a quality benchmark. No live desktop actions were used for these checks.

## Persistent planner update

| Check | Cold turn | Reused turn |
| --- | ---: | ---: |
| Antigravity planner | 5.82 s | 1.21 s |
| Full Codex CLI | 7.71 s | 2.93 s |
| Direct HTTP adapter test | 4.69 s | 1.02 s |
| Planner input | about 20,900 tokens | about 4,900 new tokens |

The update also passed these checks:

- The router rejected the obsolete `index` action field.
- The router compiled `element_index` and `super+l` correctly.
- A `response.created` event arrived before Gemini completed planning.
- GPT-5.6 Sol Low subscription passthrough completed in 3.38 seconds.
- Model picker discovery, Python syntax, and LaunchAgent validation passed.

## Native Sky cursor regression and recovery

The successful GPT task on 2026-08-26 used Codex Computer Use service build
`1000816`. Current Gemini and GPT tasks used service build `1000901`. Both
models reached the same native `node_repl` and Sky path. Both models also
failed when Sky tried to animate its cursor.

The `1000901` crash reports resolve to
`Animation.DisplayLinkAnimationDriver.displayLinkDidFire`, source line 42.
The callback ran on the `Window Bounds Observer` queue. The new build checks
for its Swift actor executor and raises `SIGTRAP` when the queues do not match.
The working `1000816` function has no executor check. The newer signed Codex
build `26.825.41651` includes Sky service `1000919` and retains the same check.

Swift provides `SWIFT_IS_CURRENT_EXECUTOR_LEGACY_MODE_OVERRIDE=legacy` for
this compatibility case. A login LaunchAgent sets this value in the macOS GUI
launch domain. ChatGPT-launched Sky replacement processes now inherit it.
Codex still executes every action through its normal `node_repl` and
`@oai/sky` path.

A later task at 18:23 found a lifecycle gap. The signed prewarmer client stayed
open, but ChatGPT started a replacement Sky service without the setting. A
second task at 18:37 proved that a keepalive could not control the service used
by Codex. Its `set_value` and `click` calls crashed Sky in 206 ms and 122 ms.
The router prewarmer was removed. The GUI launch-domain setting now covers the
service that ChatGPT starts and all later replacements.

The newest Gemini task was continued as a delegated test. Its native Calculator
mouse calls completed in 0.70 to 0.72 seconds. A later Sky restart inherited
the same launch-domain setting and completed another native click. A direct
desktop test first raised Calculator and then clicked it. The virtual cursor
window was on screen with alpha 1 and was ordered above Calculator. No new
crash report appeared. Gemini still made an unnecessary Divide click before
button 7. This is a planner quality defect. The native Sky transport passed
every post-fix call.

The delegated task did not prove PiP visibility. Codex marked that task hidden,
and the running app kept the PiP connection for the Sky process that crashed at
18:37. The replacement service captured a composite frame that included both
Calculator and the software cursor, but Codex did not publish that frame. One
Codex restart is required after this repair so the app connects PiP to the
stable service from its first launch.

| Check | Result |
| --- | --- |
| GUI launch-domain inheritance | Passed. Replacement service build `1000901` inherited the compatibility setting. |
| Code signature | Passed. `com.openai.sky.CUAService`, OpenAI team `2DC432GLL2`. |
| Native element click | Passed in Calculator through Codex `node_repl` and `@oai/sky`. |
| Cursor service stability | Passed. Same service PID remained active and no new crash report appeared. |

Post-install Gemini verification used the existing Gemini task:

| Task | End-to-end | Native calls | Result |
| --- | ---: | ---: | --- |
| Clear Calculator and enter `123` | 16.65 s | 3 | Passed. No native failures. |
| Explicit mouse click ending at `1,237` | 15.34 s | 5 | Passed. All three mouse clicks completed in 0.70 to 0.76 s. |

The second task took extra planner steps because Gemini first selected button 8,
then corrected the Calculator state and selected button 7. Native cursor speed
was under one second per click. Planner choice and repeated model turns now
account for most of the end-to-end time.

## Successful native PiP test after Codex restart

Task `01a05060-9f98-7d62-821b-74df9b9c650f` ran after the repaired Codex
process started. Gemini used the normal model-provider path and native
`node_repl` plus `@oai/sky` calls.

- The first search completed in 15.71 seconds.
- A second request opened a practice form and filled six fields without
  submission in 26.31 seconds.
- Six `set_value` calls completed in 0.67 to 1.11 seconds.
- The gender mouse click completed in 0.86 seconds.
- The user confirmed that the native PiP and moving software pointer were
  visible.

This test proves the full visible path after restart: Gemini planner, Codex tool
surface, signed Sky service, software cursor, composite capture, and Codex PiP.

## Native action batching

The router previously forced one Gemini action per model turn. This adapter-only
restriction was removed on 2026-08-29. Gemini can now choose a single action or
an ordered batch under the bundled native Computer Use skill.

The complete batch is validated before any code is returned. The compiler
accepts only the existing Sky action allowlist, emits sequential `await sky.*`
calls, and performs one final `get_app_state`. Invalid, empty, oversized, and
mixed-observation batches are rejected. Sixteen local regression tests passed.

The live Antigravity planner independently chose a three-action Calculator batch
in 9.82 seconds. The generated native call contained three action calls and one
state read.

The full Codex comparison used the same Calculator app, initial display `987`,
prompt, project, and Low reasoning setting:

| Model | Total | Inspections | Action tool calls | Actions in final call | Final call |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gemini 3.7 Flash Low | 16.40 s | 1 | 1 | 4 | 0.58 s |
| GPT-5.6 Sol Low | 23.27 s | 2 | 1 | 4 | 2.29 s |

Gemini task `01a0507b-1cc4-7863-a833-fe6d263b5e56` used `Escape`, `1`, `2`,
and `3` as four keyboard actions in one `node_repl` call. GPT task
`01a0507b-a804-7751-9204-cff45a8f260d` used Clear, 1, 2, and 3 as four mouse
clicks in one `node_repl` call. Both models batched the complete stable sequence
and verified that the final display was `123`.

## Supervised GPT-5.6 Sol Instant timing

Test date: 2026-08-30

ChatGPT was opened through the normal signed-in web interface. GPT-5.6 Sol was
set to **Instant, 1 of 5**. The planner received a compact Computer Use contract
and the same Calculator accessibility state used above. It returned JSON only.
Codex validated the action list and executed it through the bundled `@oai/sky`
backend. The native pointer moved for every click, and the final display was
`123` in all trials.

| Trial | First visible plan | Plan complete | Native Sky execution | Total | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | 3.85 s | 6.06 s | 1.03 s | 7.09 s | Passed |
| 2 | 2.53 s | 4.60 s | 1.03 s | 5.63 s | Passed |
| 3 | 2.43 s | 4.65 s | 1.03 s | 5.68 s | Passed |
| Median | 2.53 s | 4.65 s | 1.03 s | 5.68 s | Passed |

Every trial independently chose one stable mouse batch: Clear, 1, 2, and 3.
Against the earlier single native Codex sample, the Instant median total was
4.10 times faster than GPT-5.6 Sol Low at 23.27 seconds and 2.89 times faster
than Gemini 3.7 Flash Low at 16.40 seconds.

These ratios are exploratory. Instant used the visible ChatGPT transport and a
1,921-character inline planner contract. The native Codex samples used the
full bundled skill and normal model-provider loop. A separate Instant run sent
the full 15,539-character prompt as a markdown attachment and took about 53.1
seconds before native execution. That attachment-path result measures web file
processing as well as model planning, so it is excluded from the median.

This test confirms that Instant can produce the same correct batch and that
Codex can execute it with the native Sky pointer.

## Instant model-picker bridge

Integration date: 2026-08-30

The local catalog now includes `GPT-5.6 Sol Instant`. One native Browser call
connects the trusted runtime and starts the first nonce-bound plan. Later plan
steps reuse the loaded helper, page, and planner contract. The adapter validates
each visible ChatGPT result and emits the normal native Sky tool call.

Validation results:

| Check | Result |
| --- | --- |
| Python syntax | Passed |
| Browser helper JavaScript syntax | Passed |
| Instant skill validation | Passed |
| Single and batch action compiler tests | Passed |
| Browser bootstrap, strict result parsing, and recovery tests | Passed |
| Bootstrap to planner to Sky state-machine test | Passed |
| Model catalog picker slug and label | Passed |

A strict live ChatGPT Instant JSON probe completed in 3.88 seconds. Temporary
Chat was enabled. The result matched the nonce and parsed without repair. No
browser cookie, token, storage value, or private backend request was read.

The final end-to-end picker-path probe used the full compact planner contract.
Instant returned a valid direct action object in 6.21 seconds with no repair.
The router compiled one four-click Sky batch for Clear, 7, 8, and 9. Native Sky
completed the call in 2.2 seconds and fresh Calculator state showed `789`.

## Codex 0.151.0 post-update recovery

Recovery date: 2026-08-30

Codex updated the Browser plugin to `26.825.51511` and Computer Use to
`1.0.1000919`. The catalog, provider, LaunchAgents, skills, and repository copy
survived. The repair script rebuilt and reinstalled all user-owned files.

The updated ChatGPT page exposed the Instant control after a short load delay.
The first bridge check stopped safely before sending a prompt. The helper uses
one 5-second page-control readiness deadline and a 20-second response deadline.
It has no second readiness wait and does not call `waitForLoadState`.

After the fix, Instant returned the correct Clear, 4, 5, and 6 mouse batch in
5.49 seconds with no repair. Native Sky changed Calculator from `789` to `456`.
Gemini returned the correct Clear, 1, 2, and 3 mouse batch in 10.7 seconds, and
native Sky changed Calculator from `456` to `123`.

## Instant warm-page and native retry hardening

Hardening date: 2026-08-30

The helper now tags its planner tab, marks it for handoff, and reclaims only the
tagged tab in a later Codex task. It opens a fresh Temporary Chat by direct URL
when a new task reuses the page. It now enforces this with the router `SESSION`
value even when the same Browser runtime and helper module stay alive. This
prevents earlier tasks from increasing context latency or affecting actions.

Exact full-contract live timings:

| Check | Prepare | Submit | Model response | Total | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| First plan in fresh task context | 1.405 s | 0.175 s | 3.914 s | 5.494 s | Passed, no repair |
| Next plan on warm page | 0.033 s | 0.201 s | 2.538 s | 2.772 s | Passed, no repair |
| Warm native click planner | 0.032 s | 0.232 s | 4.040 s | 4.304 s | Correct three-click batch |
| Explicit session-isolation check | 1.131 s | 0.354 s | 5.018 s | 6.858 s | Passed, fresh Temporary Chat |
| Same-session warm check | 0.034 s | 0.393 s | 1.632 s | 2.059 s | Passed, no repair |

The first fully cold page sample took 10.137 seconds. Page preparation used
6.710 seconds and the model response used 3.259 seconds. The warm sample shows
that browser preparation is 33 ms after handoff and reuse. The helper does not
read or replay a ChatGPT cookie, token, storage value, or private backend call.

The installed picker endpoint returned both `gemini-3.7-flash-low` and
`gpt-5.6-sol-instant`. The Instant SSE response forwarded the user task and
emitted the combined Browser bootstrap and first planner call with a 30-second
tool bound. Twenty-nine local regression tests passed.

Native Sky live checks also passed. A Calculator mouse batch used the native
pointer and fresh accessibility diff. A stopped Chess app launched and became
observable in 2.8 seconds through the bounded startup retry. An Instant-planned
Calculator batch produced three ordered native clicks and fresh state showed
`12`.

## Official API and native-control Webb benchmark

Test date: 2026-08-30

The task opened the James Webb Space Telescope article in Chrome, selected and
copied the first Mission goals paragraph, and calculated `2021 + 5 * 12` in the
native Calculator. The strict control required visible Calculator button
clicks. Total time includes model startup, planning, native Sky work, and final
response.

| Route | Total | Planner turns | Native tool calls | Result |
| --- | ---: | ---: | ---: | --- |
| Gemini 3.7 Flash Low, custom Antigravity picker | 103.50 s | 14 interaction steps | 66 Sky calls reported by the model, in 16 Codex tool envelopes | Passed, strict mouse-click run |
| GPT-5.6 Sol Low, default Codex subscription subagent | 149.91 s | Native Codex loop | 37 Sky calls reported by the model | Passed, strict mouse-click run |
| GPT-5.6 Sol Instant, `chat-latest` prepaid API planner | 132.69 s | 21 accepted API turns | 20 Codex tool calls | Passed |
| GPT-5.6 Sol Low Fast, `gpt-5.6-sol` prepaid API planner | 129.15 s | 18 API turns | 17 Codex tool calls | Passed |

The strict Gemini run was 30.96 percent faster than default Sol Low. Gemini
used larger native click batches. An earlier 34.21-second Gemini sample was
excluded from the strict comparison because it typed the Calculator formula
instead of using button clicks.

The successful Instant run spent 52.012 seconds in accepted planner calls and
73.984 seconds in native Sky calls. Sol Low Fast spent 64.078 seconds in
planner calls and 63.011 seconds in native Sky calls. Direct single-step API
probes completed in 1.597 to 3.718 seconds for Instant and 2.109 seconds for
Sol Low Fast. The full-task delay came mainly from repeated plan and UI cycles.

A later Instant reliability run failed after 121.53 seconds when the model
returned an empty key value and repeated Calculator inspections. The API tool
schema now rejects empty required text at generation time. The mixed-observe
boundary is also normalized before native execution. Twenty-eight regression
tests passed after these fixes. A post-fix live Instant probe completed in
2.325 seconds, returned a valid native Sky tool call, and used 4,248 tokens.

The refreshed prepaid balance was `$3.20` after the tests. Auto-reload remained
off.

## Full Codex behavior for Gemini

Implementation date: 2026-08-30

The Gemini picker now receives the active Codex instructions, new conversation
items, image attachments, full tool manifest, tool results, tool-choice state,
and parallel-call setting. Core function, custom, and MCP namespace calls use
their native Responses output items. Connector schemas and non-Computer Use
skills load only when required. The current bundled Computer Use skill remains
preloaded as a protected compatibility block.

Validation results:

| Check | Result |
| --- | --- |
| Python and shell syntax | Passed |
| Protocol and Computer Use unit tests | 47 passed |
| Exact working Computer Use compiler comparison | All 3 compiler functions match |
| General `exec_command` task | Passed |
| Custom `apply_patch`, verify, and final response | Passed |
| Google Drive MCP call with deferred schema | Passed |
| Complete lazy `openai-docs` skill read | Passed |
| Two independent calls from one planner turn | Passed |
| Attached image recognition and clean text stream | Passed twice |
| Native Calculator Computer Use after all changes | Passed, result `42` |

The final isolated Calculator run took 15.03 seconds. It used the native Sky
tool surface, one inspect call, one type-and-observe call, and returned `42`.
The image checks returned `Trash can` in 8.12 and 10.80 seconds of planner time
with no raw JSON or stream mismatch.
