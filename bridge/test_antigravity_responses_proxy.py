#!/usr/bin/env python3
"""Regression tests for validated native Computer Use batching."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import antigravity_responses_proxy as proxy
import build_model_catalog as catalog_builder


class ComputerActionBatchTests(unittest.TestCase):
    def test_single_action_remains_compatible(self) -> None:
        code, title = proxy._compile_computer_actions(
            {"action": "click", "app": "Calculator", "element_index": 20}
        )
        self.assertEqual(title, "Click in Calculator")
        self.assertEqual(code.count("await sky.click("), 1)
        self.assertEqual(code.count("await sky.get_app_state("), 1)

    def test_batch_compiles_in_order_with_one_final_observation(self) -> None:
        code, title = proxy._compile_computer_actions(
            {
                "actions": [
                    {"action": "click", "app": "Calculator", "element_index": 20},
                    {"action": "click", "app": "Calculator", "element_index": 21},
                    {"action": "press_key", "app": "Calculator", "key": "Return"},
                ]
            }
        )
        self.assertEqual(title, "Use 3 actions in Calculator")
        self.assertLess(code.index('"element_index":20'), code.index('"element_index":21'))
        self.assertLess(code.index('"element_index":21'), code.index("sky.press_key"))
        self.assertEqual(code.count("await sky.get_app_state("), 1)

    def test_batch_can_switch_apps_and_observes_last_app(self) -> None:
        code, title = proxy._compile_computer_actions(
            {
                "actions": [
                    {"action": "type_text", "app": "TextEdit", "text": "hello"},
                    {"action": "type_text", "app": "Calculator", "text": "123"},
                ]
            }
        )
        self.assertEqual(title, "Use 2 Computer Use actions")
        self.assertIn('let target = "Calculator";', code)

    def test_observe_retries_native_app_start_without_finder(self) -> None:
        code, title = proxy._compile_computer_actions(
            {"action": "observe", "app": "Google Chrome"}
        )
        self.assertEqual(title, "Inspect Google Chrome")
        self.assertIn("Running application not found", code)
        self.assertIn("await sky.list_apps()", code)
        self.assertIn("setTimeout", code)
        self.assertIn(f"attempt < {proxy.APP_START_RETRY_COUNT}", code)
        self.assertNotIn("Finder", code)

    def test_common_key_aliases_are_canonicalized(self) -> None:
        for alias in ("ENTER", "enter", "return", "Return"):
            code, _ = proxy._compile_computer_actions(
                {"action": "press_key", "app": "Finder", "key": alias}
            )
            self.assertIn('"key":"Return"', code)
        code, _ = proxy._compile_computer_actions(
            {"action": "press_key", "app": "Finder", "key": "Command+L"}
        )
        self.assertIn('"key":"super+l"', code)

    def test_unsupported_action_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            proxy._compile_computer_actions(
                {
                    "action": "press_key",
                    "app": "Finder",
                    "key": "Return",
                    "modifiers": ["command"],
                }
            )

    def test_scroll_requires_a_native_target(self) -> None:
        with self.assertRaisesRegex(ValueError, "element_index or x and y"):
            proxy._compile_computer_actions(
                {"action": "scroll", "app": "Google Chrome", "direction": "down", "pages": 1}
            )

    def test_coordinate_scroll_compiles_for_current_sky(self) -> None:
        code, title = proxy._compile_computer_actions(
            {
                "action": "scroll",
                "app": "Google Chrome",
                "x": 800,
                "y": 600,
                "direction": "down",
                "pages": 1,
            }
        )
        self.assertEqual(title, "Scroll Google Chrome")
        self.assertIn('"x":800', code)
        self.assertIn('"y":600', code)

    def test_normalizer_emits_one_native_tool_call_for_batch(self) -> None:
        normalized = proxy._normalize_proposal(
            {
                "kind": "tool_call",
                "content": "",
                "name": "computer_action",
                "arguments_json": json.dumps(
                    {
                        "actions": [
                            {"action": "click", "app": "Calculator", "element_index": 20},
                            {"action": "click", "app": "Calculator", "element_index": 21},
                        ]
                    }
                ),
            }
        )
        self.assertEqual(normalized["name"], "mcp__node_repl__js")
        arguments = json.loads(normalized["arguments_json"])
        self.assertEqual(arguments["title"], "Use 2 actions in Calculator")
        self.assertEqual(arguments["code"].count("await sky.click("), 2)

    def test_empty_batch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            proxy._compile_computer_actions({"actions": []})

    def test_observe_inside_batch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "single-action form"):
            proxy._compile_computer_actions(
                {
                    "actions": [
                        {"action": "click", "app": "Calculator", "element_index": 20},
                        {"action": "observe", "app": "Calculator"},
                    ]
                }
            )

    def test_single_observe_uses_single_action_form(self) -> None:
        with self.assertRaisesRegex(ValueError, "single-action form"):
            proxy._compile_computer_actions(
                {"actions": [{"action": "observe", "app": "Calculator"}]}
            )

    def test_invalid_later_action_rejects_complete_batch(self) -> None:
        with self.assertRaisesRegex(ValueError, "not allowed"):
            proxy._compile_computer_actions(
                {
                    "actions": [
                        {"action": "click", "app": "Calculator", "element_index": 20},
                        {"action": "run_javascript", "app": "Calculator", "code": "bad"},
                    ]
                }
            )

    def test_batch_size_has_a_resource_limit(self) -> None:
        actions = [
            {"action": "click", "app": "Calculator", "element_index": 20}
            for _ in range(proxy.MAX_COMPUTER_ACTIONS + 1)
        ]
        with self.assertRaisesRegex(ValueError, "exceeds"):
            proxy._compile_computer_actions({"actions": actions})


class NativeCodexProtocolTests(unittest.TestCase):
    @staticmethod
    def tools() -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "name": "exec_command",
                "description": "Run a command.",
                "parameters": {
                    "type": "object",
                    "properties": {"cmd": {"type": "string"}},
                    "required": ["cmd"],
                },
                "strict": False,
            },
            {
                "type": "namespace",
                "name": "mcp__codex_app",
                "description": "Codex app tools.",
                "tools": [
                    {
                        "type": "function",
                        "name": "list_threads",
                        "description": "List tasks.",
                        "parameters": {
                            "type": "object",
                            "properties": {"limit": {"type": "integer"}},
                        },
                        "strict": False,
                    }
                ],
            },
            {
                "type": "namespace",
                "name": "mcp__node_repl",
                "tools": [
                    {
                        "type": "function",
                        "name": "js",
                        "description": "Run JavaScript.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string"},
                                "title": {"type": "string"},
                            },
                            "required": ["code"],
                        },
                        "strict": False,
                    }
                ],
            },
            {
                "type": "custom",
                "name": "apply_patch",
                "description": "Apply one patch.",
                "format": {
                    "type": "grammar",
                    "syntax": "lark",
                    "definition": "start: /[\\s\\S]+/",
                },
            },
            {"type": "web_search"},
        ]

    def catalog(self) -> tuple[str, dict[str, dict[str, object]], str]:
        return proxy._flatten_tool_catalog(self.tools(), "auto", True)

    def test_catalog_flattens_namespaces_and_keeps_exact_definitions(self) -> None:
        manifest, specs, signature = self.catalog()
        self.assertEqual(
            set(specs),
            {
                "exec_command",
                "mcp__codex_app__list_threads",
                "mcp__node_repl__js",
                "apply_patch",
            },
        )
        parsed = json.loads(manifest)
        self.assertTrue(parsed["parallel_tool_calls"])
        self.assertEqual(
            parsed["provider_hosted_tools_unavailable_in_this_adapter"],
            [{"type": "web_search", "name": ""}],
        )
        self.assertEqual(len(signature), 64)
        listed = {
            item["canonical_name"]: item
            for item in parsed["callable_tools"]
        }
        self.assertEqual(
            listed["mcp__codex_app__list_threads"]["definition"]["parameters"],
            self.tools()[1]["tools"][0]["parameters"],
        )
        self.assertEqual(
            parsed["synthetic_compatibility_tools"][0]["canonical_name"],
            "computer_action",
        )

    def test_exact_tool_description_is_serialized_once_without_data_loss(self) -> None:
        description = "UNIQUE EXACT TOOL DESCRIPTION"
        tool = {
            "type": "namespace",
            "name": "mcp__codex_app",
            "tools": [{
                "type": "function",
                "name": "example",
                "description": description,
                "parameters": {"type": "object", "properties": {}},
            }],
        }
        original = json.loads(json.dumps(tool))
        manifest, specs, _ = proxy._flatten_tool_catalog([tool])
        entry = json.loads(manifest)["callable_tools"][0]
        self.assertEqual(manifest.count(description), 1)
        self.assertNotIn("description", {
            key: value for key, value in entry.items() if key != "definition"
        })
        self.assertEqual(entry["definition"]["description"], description)
        self.assertEqual(
            specs["mcp__codex_app__example"]["definition"]["description"],
            description,
        )
        self.assertEqual(tool, original)

    def test_prompt_budget_defers_exact_schema_and_preserves_active_task(self) -> None:
        def child(name: str, marker: str) -> dict[str, object]:
            return {
                "type": "function",
                "name": name,
                "description": f"Use {name}.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "payload": {
                            "type": "string",
                            "description": marker * 6000,
                        },
                    },
                    "required": ["payload"],
                },
            }

        tools = [{
            "type": "namespace",
            "name": "mcp__codex_app",
            "tools": [child("tool_a", "A"), child("tool_b", "B")],
        }]
        request = {
            "instructions": "Follow the task.",
            "tools": tools,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
        }
        delta = "USER:\nACTIVE_USER_TASK_SENTINEL\nLATEST_TOOL_RESULT_SENTINEL"
        with mock.patch.object(proxy, "_load_computer_use_skill", return_value="CU"):
            manifest, _, _ = proxy._flatten_tool_catalog(tools)
            unbounded = proxy._gemini_prompt(
                request,
                delta,
                manifest,
                include_contract=True,
                include_instructions=True,
                include_tools=True,
            )
            maximum = len(unbounded) - 1000
            packed = proxy._pack_gemini_prompt(
                request,
                delta,
                include_contract=True,
                include_instructions=True,
                include_tools=True,
                maximum_bytes=maximum,
            )
        prompt, packed_manifest, specs, _, deferred = packed
        name = "mcp__codex_app__tool_a"
        self.assertLessEqual(proxy._utf8_size(prompt), maximum)
        self.assertTrue(prompt.endswith(delta))
        self.assertEqual(prompt.count("ACTIVE_USER_TASK_SENTINEL"), 1)
        self.assertEqual(prompt.count("LATEST_TOOL_RESULT_SENTINEL"), 1)
        self.assertEqual(deferred, {name})
        entries = {
            entry["canonical_name"]: entry
            for entry in json.loads(packed_manifest)["callable_tools"]
        }
        self.assertEqual(set(entries), {
            "mcp__codex_app__tool_a",
            "mcp__codex_app__tool_b",
        })
        self.assertEqual(entries[name]["schema_mode"], "inspect_before_call")
        self.assertNotIn("definition", entries[name])
        proposal = {
            "kind": "tool_call",
            "content": "",
            "name": name,
            "arguments_json": '{"payload":"value"}',
        }
        with self.assertRaisesRegex(ValueError, "inspect_tools"):
            proxy._normalize_proposal(proposal, specs)
        inspected: set[str] = set()
        inspection = proxy._tool_inspection_prompt(
            {
                "kind": "tool_call",
                "name": "inspect_tools",
                "arguments_json": json.dumps({"names": [name]}),
            },
            specs,
            inspected,
        )
        self.assertIn("A" * 100, inspection)
        normalized = proxy._normalize_proposal(
            proposal,
            specs,
            inspected_tools=inspected,
        )
        self.assertEqual(normalized["name"], name)

    def test_tool_change_recomputes_budget_deferred_modes(self) -> None:
        def tools(schema_padding: int) -> list[dict[str, object]]:
            return [{
                "type": "namespace",
                "name": "mcp__codex_app",
                "tools": [{
                    "type": "function",
                    "name": "large_tool",
                    "description": "Use the tool.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "value": {
                                "type": "string",
                                "description": "X" * schema_padding,
                            },
                        },
                    },
                }],
            }]

        first_request = {
            "instructions": "Rules.",
            "tools": tools(8000),
            "input": [{
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "First."}],
            }],
        }
        with mock.patch.object(proxy, "_load_computer_use_skill", return_value="CU"):
            manifest, _, _ = proxy._flatten_tool_catalog(first_request["tools"])
            unbounded = proxy._gemini_prompt(
                first_request,
                "USER:\nFirst.",
                manifest,
                include_contract=True,
                include_instructions=True,
                include_tools=True,
            )
            maximum = len(unbounded) - 1000
            worker = proxy.AgyWorker("budget-mode-test")
            process = mock.Mock()
            process.poll.return_value = None
            worker.process = process
            worker._turn = mock.Mock(side_effect=[
                ({
                    "kind": "message",
                    "content": "First done.",
                    "name": "",
                    "arguments_json": "{}",
                }, {}),
                ({
                    "kind": "message",
                    "content": "Second done.",
                    "name": "",
                    "arguments_json": "{}",
                }, {}),
            ])
            with mock.patch.object(proxy, "MAX_GEMINI_PROMPT_BYTES", maximum):
                worker.call(first_request)
                self.assertEqual(
                    worker.deferred_tool_names,
                    {"mcp__codex_app__large_tool"},
                )
                second_user = {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Second."}],
                }
                worker.call({
                    **first_request,
                    "tools": tools(10),
                    "input": [first_request["input"][0], second_user],
                })
        self.assertEqual(worker.deferred_tool_names, set())
        second_prompt = worker._turn.call_args_list[1].args[0]
        self.assertIn("EXTERNAL TOOL CATALOG", second_prompt)

    def test_unfit_protected_prompt_fails_before_planner_turn(self) -> None:
        worker = proxy.AgyWorker("budget-failure-test")
        process = mock.Mock()
        process.poll.return_value = None
        worker.process = process
        worker._turn = mock.Mock()
        request = {
            "instructions": "Rules.",
            "tools": self.tools(),
            "input": [{
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "ACTIVE_TASK"}],
            }],
        }
        with (
            mock.patch.object(proxy, "_load_computer_use_skill", return_value="CU"),
            mock.patch.object(proxy, "MAX_GEMINI_PROMPT_BYTES", 500),
        ):
            with self.assertRaisesRegex(proxy.PromptBudgetError, "safe limit"):
                worker.call(request)
        worker._turn.assert_not_called()
        self.assertFalse(worker.seeded)
        self.assertEqual(worker.seen, set())

    def test_turn_rejects_oversized_schema_before_stdin_write(self) -> None:
        worker = proxy.AgyWorker("turn-budget-test")
        process = mock.Mock()
        process.poll.return_value = None
        worker.process = process
        with mock.patch.object(proxy, "MAX_GEMINI_PROMPT_BYTES", 10):
            with self.assertRaisesRegex(proxy.PromptBudgetError, "safe limit"):
                worker._turn("X" * 11)
        process.stdin.write.assert_not_called()

    def test_prompt_budget_counts_utf8_bytes(self) -> None:
        request = {"instructions": "é" * 100}
        with mock.patch.object(proxy, "_load_computer_use_skill", return_value="CU"):
            prompt = proxy._gemini_prompt(
                request,
                "USER:\nTask.",
                "{}",
                include_contract=False,
                include_instructions=True,
                include_tools=False,
            )
            with self.assertRaisesRegex(proxy.PromptBudgetError, "bytes"):
                proxy._pack_gemini_prompt(
                    request,
                    "USER:\nTask.",
                    include_contract=False,
                    include_instructions=True,
                    include_tools=False,
                    maximum_bytes=len(prompt),
                )

    def test_prompt_budget_can_cross_one_time_lazy_catalog_overhead(self) -> None:
        def child(name: str) -> dict[str, object]:
            return {
                "type": "function",
                "name": name,
                "description": "D",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string",
                            "description": "X" * 10,
                        },
                    },
                },
            }

        tools = [{
            "type": "namespace",
            "name": "mcp__codex_app",
            "tools": [child(f"tool_{letter}") for letter in "abcd"],
        }]
        request = {"instructions": "I", "tools": tools}
        delta = "USER:\nT"
        first = {"mcp__codex_app__tool_a"}
        first_two = first | {"mcp__codex_app__tool_b"}
        with mock.patch.object(proxy, "_load_computer_use_skill", return_value="CU"):
            base_manifest, _, _ = proxy._flatten_tool_catalog(tools)
            one_manifest, _, _ = proxy._flatten_tool_catalog(
                tools,
                deferred_tools=first,
            )
            two_manifest, _, _ = proxy._flatten_tool_catalog(
                tools,
                deferred_tools=first_two,
            )
            prompts = [
                proxy._gemini_prompt(
                    request,
                    delta,
                    manifest,
                    include_contract=True,
                    include_instructions=True,
                    include_tools=True,
                )
                for manifest in (base_manifest, one_manifest, two_manifest)
            ]
            base_bytes, one_bytes, two_bytes = map(proxy._utf8_size, prompts)
            self.assertGreater(one_bytes, base_bytes)
            self.assertLess(two_bytes, base_bytes)
            packed = proxy._pack_gemini_prompt(
                request,
                delta,
                include_contract=True,
                include_instructions=True,
                include_tools=True,
                maximum_bytes=two_bytes,
            )
        prompt, _, _, _, deferred = packed
        self.assertLessEqual(proxy._utf8_size(prompt), two_bytes)
        self.assertEqual(deferred, first_two)

    def test_turn_does_not_silently_start_an_unseeded_process(self) -> None:
        worker = proxy.AgyWorker("dead-process-test")
        process = mock.Mock()
        process.poll.return_value = 1
        worker.process = process
        worker._start = mock.Mock()
        with self.assertRaisesRegex(proxy.AgyProcessError, "unavailable"):
            worker._turn("warm delta")
        worker._start.assert_not_called()

    def test_process_restart_forgets_prior_schema_inspection(self) -> None:
        large_tool = {
            "type": "namespace",
            "name": "mcp__codex_app",
            "tools": [{
                "type": "function",
                "name": "large_tool",
                "description": "Use the tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string",
                            "description": "X" * 8000,
                        },
                    },
                    "required": ["value"],
                },
            }],
        }
        request = {
            "instructions": "Rules.",
            "tools": [large_tool],
            "input": [{
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Run it."}],
            }],
        }
        with mock.patch.object(proxy, "_load_computer_use_skill", return_value="CU"):
            manifest, _, _ = proxy._flatten_tool_catalog(request["tools"])
            unbounded = proxy._gemini_prompt(
                request,
                "USER:\nRun it.",
                manifest,
                include_contract=True,
                include_instructions=True,
                include_tools=True,
            )
        maximum = len(unbounded) - 1000
        worker = proxy.AgyWorker("restart-inspection-test")
        live_process = mock.Mock()
        live_process.poll.return_value = None
        worker.process = live_process
        direct_call = {
            "kind": "tool_call",
            "content": "",
            "name": "mcp__codex_app__large_tool",
            "arguments_json": '{"value":"ok"}',
        }

        def turn(prompt: str, *_: object) -> tuple[dict[str, str], dict[str, int]]:
            call_number = worker._turn.call_count
            if call_number == 1:
                return ({
                    "kind": "tool_call",
                    "content": "",
                    "name": "inspect_tools",
                    "arguments_json": json.dumps({
                        "names": ["mcp__codex_app__large_tool"],
                    }),
                }, {})
            if call_number == 2:
                dead_process = mock.Mock()
                dead_process.poll.return_value = 1
                worker.process = dead_process
                raise RuntimeError("planner process closed")
            if call_number == 3:
                return direct_call, {}
            return ({
                "kind": "message",
                "content": "Recovered.",
                "name": "",
                "arguments_json": "{}",
            }, {})

        def restart() -> None:
            replacement = mock.Mock()
            replacement.poll.return_value = None
            worker.process = replacement

        worker._turn = mock.Mock(side_effect=turn)
        worker._start = mock.Mock(side_effect=restart)
        with (
            mock.patch.object(proxy, "_load_computer_use_skill", return_value="CU"),
            mock.patch.object(proxy, "MAX_GEMINI_PROMPT_BYTES", maximum),
        ):
            proposal, _ = worker.call(request)
        self.assertEqual(proposal["content"], "Recovered.")
        self.assertEqual(worker._turn.call_count, 4)
        restart_prompt = worker._turn.call_args_list[2].args[0]
        self.assertIn("CODEX_RESPONSES_ADAPTER_REQUEST_V2", restart_prompt)
        self.assertIn("Run it.", restart_prompt)
        repair_prompt = worker._turn.call_args_list[3].args[0]
        self.assertIn("REPAIR_RESPONSE_V2", repair_prompt)

    def test_general_function_call_is_validated_and_preserved(self) -> None:
        _, specs, _ = self.catalog()
        normalized = proxy._normalize_proposal(
            {
                "kind": "tool_call",
                "content": "",
                "name": "exec_command",
                "arguments_json": '{"cmd":"pwd"}',
            },
            specs,
        )
        self.assertEqual(normalized["tool_type"], "function")
        self.assertIsNone(normalized["namespace"])
        self.assertEqual(json.loads(normalized["arguments_json"]), {"cmd": "pwd"})

    def test_namespaced_function_uses_canonical_name(self) -> None:
        _, specs, _ = self.catalog()
        normalized = proxy._normalize_proposal(
            {
                "kind": "tool_call",
                "content": "",
                "name": "mcp__codex_app__list_threads",
                "arguments_json": '{"limit":5}',
            },
            specs,
        )
        self.assertEqual(normalized["namespace"], "mcp__codex_app")
        self.assertEqual(normalized["wire_name"], "list_threads")

    def test_undeclared_tool_is_rejected(self) -> None:
        _, specs, _ = self.catalog()
        with self.assertRaisesRegex(ValueError, "undeclared"):
            proxy._normalize_proposal(
                {
                    "kind": "tool_call",
                    "content": "",
                    "name": "hidden_tool",
                    "arguments_json": "{}",
                },
                specs,
            )

    def test_direct_sky_code_is_forced_through_protected_compiler(self) -> None:
        _, specs, _ = self.catalog()
        with self.assertRaisesRegex(ValueError, "computer_action"):
            proxy._normalize_proposal(
                {
                    "kind": "tool_call",
                    "content": "",
                    "name": "mcp__node_repl__js",
                    "arguments_json": json.dumps({
                        "code": 'const {sky}=await import("@oai/sky");',
                    }),
                },
                specs,
            )

    def test_custom_tool_keeps_raw_input(self) -> None:
        _, specs, _ = self.catalog()
        raw_patch = "*** Begin Patch\n*** End Patch"
        normalized = proxy._normalize_proposal(
            {
                "kind": "tool_call",
                "content": "",
                "name": "apply_patch",
                "arguments_json": raw_patch,
            },
            specs,
        )
        self.assertEqual(normalized["tool_type"], "custom")
        self.assertEqual(normalized["arguments_json"], raw_patch)

    def test_parallel_independent_calls_are_supported(self) -> None:
        _, specs, _ = self.catalog()
        calls = [
            {"name": "exec_command", "arguments_json": '{"cmd":"pwd"}'},
            {
                "name": "mcp__codex_app__list_threads",
                "arguments_json": '{"limit":3}',
            },
        ]
        normalized = proxy._normalize_proposal(
            {
                "kind": "tool_call",
                "content": "",
                "name": "parallel_tools",
                "arguments_json": json.dumps(calls),
            },
            specs,
            allow_parallel=True,
        )
        self.assertEqual(normalized["kind"], "tool_calls")
        self.assertEqual(len(normalized["calls"]), 2)
        events = proxy._sse_events(
            normalized,
            {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        )
        completed = next(
            event for event in events if event["type"] == "response.completed"
        )
        self.assertEqual(len(completed["response"]["output"]), 2)

    def test_sse_keeps_namespace_and_custom_protocol(self) -> None:
        _, specs, _ = self.catalog()
        namespaced = proxy._normalize_proposal(
            {
                "kind": "tool_call",
                "content": "",
                "name": "mcp__codex_app__list_threads",
                "arguments_json": "{}",
            },
            specs,
        )
        events = proxy._sse_events(namespaced, {})
        done = next(
            event
            for event in events
            if event["type"] == "response.function_call_arguments.done"
        )
        self.assertEqual(done["name"], "list_threads")
        self.assertEqual(done["namespace"], "mcp__codex_app")

        custom = proxy._normalize_proposal(
            {
                "kind": "tool_call",
                "content": "",
                "name": "apply_patch",
                "arguments_json": "*** Begin Patch\n*** End Patch",
            },
            specs,
        )
        custom_events = proxy._sse_events(custom, {})
        event_types = [event["type"] for event in custom_events]
        self.assertIn("response.custom_tool_call_input.delta", event_types)
        self.assertIn("response.custom_tool_call_input.done", event_types)
        completed = next(
            event
            for event in custom_events
            if event["type"] == "response.completed"
        )
        self.assertEqual(completed["response"]["output"][0]["type"], "custom_tool_call")

    def test_custom_calls_and_outputs_are_kept_in_step_state(self) -> None:
        rendered = proxy._serialize_input([
            {
                "type": "custom_tool_call",
                "name": "apply_patch",
                "call_id": "call_1",
                "input": "patch",
            },
            {
                "type": "custom_tool_call_output",
                "call_id": "call_1",
                "output": "Done!",
            },
        ])
        self.assertIn("apply_patch", rendered)
        self.assertIn("patch", rendered)
        self.assertIn("Done!", rendered)

    def test_prompt_has_codex_instructions_tools_and_protected_cu(self) -> None:
        manifest, _, _ = self.catalog()
        prompt = proxy._gemini_prompt(
            {
                "instructions": "Follow Codex developer rules.",
                "tool_choice": "auto",
                "parallel_tool_calls": True,
            },
            "USER:\nRun pwd.",
            manifest,
            include_contract=True,
            include_instructions=True,
            include_tools=True,
        )
        self.assertIn("CODEX_RESPONSES_ADAPTER_REQUEST_V2", prompt)
        self.assertIn("Follow Codex developer rules", prompt)
        self.assertIn("mcp__codex_app__list_threads", prompt)
        self.assertIn("NATIVE COMPUTER USE SKILL (PROTECTED PRELOAD)", prompt)
        self.assertIn("Computer Use Confirmations Policy", prompt)
        self.assertIn("another\nskill", prompt)

    def test_worker_seeds_once_and_reuses_codex_state(self) -> None:
        worker = proxy.AgyWorker("protocol-test")
        process = mock.Mock()
        process.poll.return_value = None
        worker.process = process
        worker._turn = mock.Mock(side_effect=[
            (
                {
                    "kind": "tool_call",
                    "content": "",
                    "name": "exec_command",
                    "arguments_json": '{"cmd":"pwd"}',
                },
                {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            ),
            (
                {
                    "kind": "message",
                    "content": "Done.",
                    "name": "",
                    "arguments_json": "{}",
                },
                {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            ),
        ])
        user = {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Run pwd."}],
        }
        request = {
            "instructions": "Developer rules.",
            "tools": self.tools(),
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "input": [user],
        }
        first, _ = worker.call(request)
        self.assertEqual(first["name"], "exec_command")
        result = {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "cwd",
        }
        second, _ = worker.call({**request, "input": [user, result]})
        self.assertEqual(second["content"], "Done.")
        first_prompt = worker._turn.call_args_list[0].args[0]
        second_prompt = worker._turn.call_args_list[1].args[0]
        self.assertIn("EXTERNAL TOOL CATALOG", first_prompt)
        self.assertNotIn("EXTERNAL TOOL CATALOG", second_prompt)
        self.assertNotIn("CODEX_RESPONSES_ADAPTER_REQUEST_V2", second_prompt)
        self.assertIn("cwd", second_prompt)

    def test_deferred_connector_schema_is_inspected_before_call(self) -> None:
        tools = [{
            "type": "namespace",
            "name": "mcp__codex_apps__drive",
            "tools": [{
                "type": "function",
                "name": "search",
                "description": "Search Drive.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            }],
        }]
        manifest, specs, _ = proxy._flatten_tool_catalog(tools)
        name = "mcp__codex_apps__drive__search"
        entry = json.loads(manifest)["callable_tools"][0]
        self.assertEqual(entry["schema_mode"], "inspect_before_call")
        self.assertNotIn("definition", entry)
        proposal = {
            "kind": "tool_call",
            "content": "",
            "name": name,
            "arguments_json": '{"query":"test"}',
        }
        with self.assertRaisesRegex(ValueError, "inspect_tools"):
            proxy._normalize_proposal(proposal, specs)
        inspected: set[str] = set()
        inspection = proxy._tool_inspection_prompt(
            {
                "kind": "tool_call",
                "name": "inspect_tools",
                "arguments_json": json.dumps({"names": [name]}),
            },
            specs,
            inspected,
        )
        self.assertIn('"query"', inspection)
        normalized = proxy._normalize_proposal(
            proposal,
            specs,
            inspected_tools=inspected,
        )
        self.assertEqual(normalized["name"], name)

    def test_deferred_description_change_does_not_reload_catalog(self) -> None:
        first = [{
            "type": "namespace",
            "name": "mcp__codex_apps__drive",
            "tools": [{
                "type": "function",
                "name": "search",
                "description": "Search Drive before connection resolution.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            }],
        }]
        second = json.loads(json.dumps(first))
        second[0]["tools"][0]["description"] = "Search Drive after connection resolution."
        _, _, first_signature = proxy._flatten_tool_catalog(first)
        _, _, second_signature = proxy._flatten_tool_catalog(second)
        self.assertEqual(first_signature, second_signature)

    def test_partial_skill_read_is_rejected(self) -> None:
        _, specs, _ = self.catalog()
        with self.assertRaisesRegex(ValueError, "must be complete"):
            proxy._normalize_proposal(
                {
                    "kind": "tool_call",
                    "name": "exec_command",
                    "arguments_json": json.dumps({
                        "cmd": "head -n 20 /tmp/example/SKILL.md",
                    }),
                },
                specs,
            )
        normalized = proxy._normalize_proposal(
            {
                "kind": "tool_call",
                "name": "exec_command",
                "arguments_json": json.dumps({
                    "cmd": "cat /tmp/example/SKILL.md",
                }),
            },
            specs,
        )
        self.assertEqual(normalized["name"], "exec_command")

    def test_adapter_object_text_parser_handles_plain_and_fenced_json(self) -> None:
        expected = {
            "arguments_json": "{}",
            "content": "Hello\nMoon \u263a \U0001f600",
            "kind": "message",
            "name": "",
        }
        encoded = json.dumps(expected)
        self.assertEqual(proxy._parse_adapter_object_text(encoded), expected)
        self.assertEqual(
            proxy._parse_adapter_object_text(f"```json\n{encoded}\n```"),
            expected,
        )
        self.assertEqual(
            proxy._parse_adapter_object_text(json.dumps(encoded)),
            expected,
        )
        self.assertIsNone(proxy._parse_adapter_object_text('{"answer": 42}'))

    def test_adapter_stream_prefix_waits_for_safe_classification(self) -> None:
        self.assertIsNone(proxy._classify_adapter_stream_prefix("Tra"))
        self.assertEqual(
            proxy._classify_adapter_stream_prefix("Trash can is the central object in the icon."),
            "message",
        )
        self.assertEqual(
            proxy._classify_adapter_stream_prefix('{"kind":"message"'),
            "candidate",
        )
        self.assertEqual(
            proxy._classify_adapter_stream_prefix('"{\\"kind\\":\\"message\\"'),
            "candidate",
        )

    def test_normalizer_unwraps_nested_adapter_message(self) -> None:
        normalized = proxy._normalize_proposal({
            "kind": "message",
            "content": json.dumps({
                "arguments_json": "{}",
                "content": "Cockatiel",
                "kind": "message",
                "name": "",
            }),
            "name": "",
            "arguments_json": "{}",
        })
        self.assertEqual(normalized["content"], "Cockatiel")

    def test_streamed_message_completion_does_not_repeat_delta(self) -> None:
        events = proxy._sse_events(
            {"kind": "message", "content": "Hello"},
            {},
            streamed_message_id="msg_streamed",
            streamed_message_text="Hello",
        )
        event_types = [event["type"] for event in events]
        self.assertNotIn("response.output_text.delta", event_types)
        done = next(
            event for event in events if event["type"] == "response.output_text.done"
        )
        self.assertEqual(done["item_id"], "msg_streamed")
        completed = next(
            event for event in events if event["type"] == "response.completed"
        )
        self.assertEqual(
            completed["response"]["output"][0]["phase"],
            "final_answer",
        )

    @staticmethod
    def tool_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        return {
            "kind": "tool_call",
            "content": "",
            "name": name,
            "wire_name": name,
            "arguments_json": json.dumps(arguments),
            "tool_type": "function",
            "namespace": None,
        }

    def test_streamed_commentary_precedes_one_tool_call(self) -> None:
        events = proxy._sse_events(
            self.tool_call("exec_command", {"cmd": "pwd"}),
            {},
            response_id="resp_test",
            include_created=False,
            streamed_message_id="msg_streamed",
            streamed_message_text="I will inspect the workspace.",
        )
        completed_events = [
            event for event in events if event["type"] == "response.completed"
        ]
        self.assertEqual(len(completed_events), 1)
        output = completed_events[0]["response"]["output"]
        self.assertEqual([item["type"] for item in output], ["message", "function_call"])
        self.assertEqual(output[0]["phase"], "commentary")
        self.assertEqual(output[0]["content"][0]["text"], "I will inspect the workspace.")
        done_indices = [
            event["output_index"]
            for event in events
            if event["type"] == "response.output_item.done"
        ]
        self.assertEqual(done_indices, [0, 1])

    def test_streamed_commentary_precedes_parallel_tool_calls(self) -> None:
        events = proxy._sse_events(
            {
                "kind": "tool_calls",
                "calls": [
                    self.tool_call("exec_command", {"cmd": "pwd"}),
                    self.tool_call("list_threads", {"limit": 3}),
                ],
            },
            {},
            response_id="resp_test",
            include_created=False,
            streamed_message_id="msg_streamed",
            streamed_message_text="I will inspect both sources.",
        )
        completed = next(
            event for event in events if event["type"] == "response.completed"
        )
        output = completed["response"]["output"]
        self.assertEqual(
            [item["type"] for item in output],
            ["message", "function_call", "function_call"],
        )
        self.assertEqual(output[0]["phase"], "commentary")
        added_indices = [
            event["output_index"]
            for event in events
            if event["type"] == "response.output_item.added"
        ]
        self.assertEqual(added_indices, [1, 2])

    def test_tool_only_output_keeps_zero_index(self) -> None:
        events = proxy._sse_events(
            self.tool_call("exec_command", {"cmd": "pwd"}),
            {},
            response_id="resp_test",
            include_created=False,
        )
        item_events = [
            event
            for event in events
            if event["type"] in (
                "response.output_item.added",
                "response.output_item.done",
            )
        ]
        self.assertTrue(item_events)
        self.assertTrue(all(event["output_index"] == 0 for event in item_events))
        completed = next(
            event for event in events if event["type"] == "response.completed"
        )
        self.assertEqual(
            [item["type"] for item in completed["response"]["output"]],
            ["function_call"],
        )

    def test_image_data_becomes_private_antigravity_attachment(self) -> None:
        payload = b"\x89PNG\r\n\x1a\nunit-test-image"
        image_url = "data:image/png;base64," + base64.b64encode(payload).decode()
        with tempfile.TemporaryDirectory() as directory:
            prepared = proxy._prepare_gemini_input(
                [{
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": "auto",
                    }],
                }],
                Path(directory),
            )
            text = prepared[0]["content"][0]["text"]
            self.assertTrue(text.startswith("@" + directory))
            self.assertNotIn("base64", text)
            path = Path(text.splitlines()[0][1:])
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class ModelCatalogTests(unittest.TestCase):
    def test_sol_none_clones_stock_codex_model(self) -> None:
        source = [{
            "slug": "gpt-5.6-sol",
            "display_name": "GPT-5.6 Sol",
            "tool_mode": "code_mode_only",
            "include_skills_usage_instructions": True,
            "supported_reasoning_levels": [{"effort": "low"}],
        }]
        custom = [{
            "clone_from": "gpt-5.6-sol",
            "slug": "gpt-5.6-sol-none",
            "display_name": "GPT-5.6 Sol None",
            "default_reasoning_level": "none",
            "supported_reasoning_levels": [{"effort": "none"}],
        }]
        expanded = catalog_builder.expand_custom_models(source, custom)
        self.assertEqual(len(expanded), 1)
        model = expanded[0]
        self.assertEqual(model["slug"], "gpt-5.6-sol-none")
        self.assertEqual(model["tool_mode"], "code_mode_only")
        self.assertTrue(model["include_skills_usage_instructions"])
        self.assertEqual(
            model["supported_reasoning_levels"],
            [{"effort": "none"}],
        )
        self.assertNotIn("clone_from", model)
        self.assertEqual(source[0]["slug"], "gpt-5.6-sol")

    def test_picker_catalog_replaces_instant_with_sol_none(self) -> None:
        catalog = json.loads(
            Path(proxy.__file__).with_name("model-catalog.json").read_text()
        )
        models = {model["slug"]: model for model in catalog["models"]}
        self.assertIn(proxy.SOL_NONE_MODEL, models)
        self.assertNotIn("gpt-5.6-sol-instant", models)
        sol_none = models[proxy.SOL_NONE_MODEL]
        self.assertEqual(sol_none["clone_from"], "gpt-5.6-sol")
        self.assertEqual(sol_none["default_reasoning_level"], "none")


class OpenAIAPIPlannerTests(unittest.TestCase):
    @staticmethod
    def output_item(call_id: str, text: str) -> dict[str, object]:
        return {
            "type": "function_call_output",
            "call_id": call_id,
            "output": [{"type": "input_text", "text": text}],
        }

    @staticmethod
    def api_response(name: str, arguments: dict[str, object]) -> dict[str, object]:
        return {
            "id": "resp_api_test",
            "status": "completed",
            "service_tier": "priority",
            "output": [
                {
                    "type": "function_call",
                    "name": name,
                    "arguments": json.dumps(arguments),
                }
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
        }

    def test_sol_none_keeps_stock_codex_request(self) -> None:
        request = {
            "model": proxy.SOL_NONE_MODEL,
            "instructions": "Follow all Codex instructions.",
            "input": [{"type": "message", "role": "user", "content": []}],
            "tools": [{"type": "namespace", "name": "mcp__node_repl"}],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "reasoning": {"effort": "low", "summary": "none"},
            "service_tier": "priority",
            "stream": True,
            "store": False,
        }
        payload = proxy._direct_api_request(proxy.SOL_NONE_MODEL, request)
        self.assertEqual(payload["model"], "gpt-5.6-sol")
        self.assertEqual(
            payload["reasoning"],
            {"effort": "none", "summary": "none"},
        )
        for name in (
            "instructions",
            "input",
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "service_tier",
            "stream",
            "store",
        ):
            self.assertEqual(payload[name], request[name])
        self.assertEqual(request["model"], proxy.SOL_NONE_MODEL)
        self.assertEqual(request["reasoning"]["effort"], "low")
        self.assertNotIn("chat-latest", json.dumps(payload).lower())

    def test_sol_fast_payload_uses_low_reasoning_and_fast_tier(self) -> None:
        payload = proxy._api_request_payload(
            proxy.SOL_FAST_MODEL,
            "USER TASK:\nOpen Calculator.",
        )
        self.assertEqual(payload["model"], "gpt-5.6-sol")
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertEqual(payload["service_tier"], "fast")

    def test_action_tool_schema_is_strict_and_bounded(self) -> None:
        tool = proxy._api_tools()[0]
        schema = tool["parameters"]
        variants = schema["properties"]["actions"]["items"]["anyOf"]
        self.assertTrue(tool["strict"])
        self.assertFalse(schema["additionalProperties"])
        self.assertGreaterEqual(len(variants), 10)
        for action in variants:
            self.assertFalse(action["additionalProperties"])
            self.assertEqual(
                set(action["required"]),
                set(action["properties"]),
            )
        self.assertEqual(
            schema["properties"]["actions"]["maxItems"],
            proxy.MAX_COMPUTER_ACTIONS,
        )

    def test_required_api_text_fields_reject_empty_strings(self) -> None:
        tools = proxy._api_tools()
        variants = tools[0]["parameters"]["properties"]["actions"]["items"]["anyOf"]
        for variant in variants:
            for name, field in variant["properties"].items():
                if field.get("type") == "string" and "enum" not in field:
                    self.assertEqual(field.get("minLength"), 1, name)
        final_content = tools[1]["parameters"]["properties"]["content"]
        self.assertEqual(final_content.get("minLength"), 1)

    def test_contract_loads_native_skill_for_action_judgment(self) -> None:
        contract = proxy._instant_contract()
        self.assertIn("Call exactly one supplied function", contract)
        self.assertIn("NATIVE COMPUTER USE SKILL", contract)
        self.assertIn("Computer Use Confirmations Policy", contract)
        self.assertIn("Do not return JavaScript", contract)

    def test_wrapped_app_name_is_normalized_before_sky(self) -> None:
        code, title = proxy._compile_computer_actions(
            {"action": "click", "app": "Google\n Chrome", "element_index": 9}
        )
        self.assertEqual(title, "Click in Google Chrome")
        self.assertIn('"app":"Google Chrome"', code)
        self.assertNotIn("Google\n Chrome", code)

    def test_instant_input_removes_injected_app_context(self) -> None:
        raw = (
            "<recommended_plugins>large list</recommended_plugins>\n"
            "# AGENTS.md instructions\n<INSTRUCTIONS>reporting</INSTRUCTIONS>\n"
            "<environment_context>paths</environment_context>\n"
            "Open Chrome and search for native computer use."
        )
        cleaned = proxy._clean_instant_user_text(raw)
        self.assertEqual(cleaned, "Open Chrome and search for native computer use.")

    def test_large_native_state_keeps_start_and_focused_tail(self) -> None:
        text = "Window: Applications\n" + ("middle row\n" * 2000) + "The focused UI element is 42"
        compact = proxy._compact_instant_text(text, 1000)
        self.assertLessEqual(len(compact), 1000)
        self.assertTrue(compact.startswith("Window: Applications"))
        self.assertIn("focused UI element is 42", compact)
        self.assertIn("Middle of large native state omitted", compact)

    def test_valid_api_batch_compiles_to_native_sky(self) -> None:
        response = self.api_response(
            "computer_action",
            {
                "actions": [
                    {
                        "action": "click",
                        "app": "Calculator",
                        "element_index": 20,
                        "x": None,
                    },
                    {
                        "action": "click",
                        "app": "Calculator",
                        "element_index": 21,
                        "x": None,
                    },
                ]
            },
        )
        normalized = proxy._parse_api_plan(response)
        self.assertEqual(normalized["name"], "mcp__node_repl__js")
        code = json.loads(normalized["arguments_json"])["code"]
        self.assertEqual(code.count("await sky.click("), 2)
        self.assertEqual(code.count("await sky.get_app_state("), 1)

    def test_single_observe_is_not_compiled_as_a_batch(self) -> None:
        response = self.api_response(
            "computer_action",
            {"actions": [{"action": "observe", "app": "Calculator"}]},
        )
        normalized = proxy._parse_api_plan(response)
        code = json.loads(normalized["arguments_json"])["code"]
        self.assertIn("await sky.get_app_state", code)
        self.assertEqual(json.loads(normalized["arguments_json"])["title"], "Inspect Calculator")

    def test_observe_stops_a_mixed_api_batch_safely(self) -> None:
        response = self.api_response(
            "computer_action",
            {
                "actions": [
                    {"action": "observe", "app": "Calculator"},
                    {"action": "click", "app": "Calculator", "element_index": 20},
                ]
            },
        )
        normalized = proxy._parse_api_plan(response)
        arguments = json.loads(normalized["arguments_json"])
        self.assertEqual(arguments["title"], "Inspect Calculator")
        self.assertNotIn("sky.click", arguments["code"])

    def test_final_message_is_parsed(self) -> None:
        normalized = proxy._parse_api_plan(
            self.api_response("final_message", {"content": "Task complete."})
        )
        self.assertEqual(normalized["kind"], "message")
        self.assertEqual(normalized["content"], "Task complete.")

    def test_worker_calls_api_directly_and_keeps_native_state(self) -> None:
        worker = proxy.OpenAIPlannerWorker("test-thread", proxy.SOL_FAST_MODEL)
        user_item = {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Click 12 in Calculator."}],
        }
        first = self.api_response(
            "computer_action",
            {
                "actions": [
                    {
                        "action": "click",
                        "app": "Calculator",
                        "element_index": 20,
                    }
                ]
            },
        )
        second = self.api_response(
            "final_message",
            {"content": "Calculator shows 12."},
        )
        sky_output = self.output_item("sky", "Calculator value: 12")
        with mock.patch.object(
            proxy,
            "_call_openai_api",
            side_effect=[first, second],
        ) as api:
            sky_call, usage = worker.call({"input": [user_item]})
            self.assertIn(
                "await sky.click(",
                json.loads(sky_call["arguments_json"])["code"],
            )
            self.assertEqual(usage["total_tokens"], 120)
            final, _ = worker.call({"input": [user_item, sky_output]})
        self.assertEqual(final["content"], "Calculator shows 12.")
        self.assertEqual(api.call_count, 2)
        second_prompt = api.call_args_list[1].args[0]["input"]
        self.assertIn("Click 12 in Calculator", second_prompt)
        self.assertIn("PRIOR ACTION PLAN", second_prompt)
        self.assertIn("Calculator value: 12", second_prompt)

    def test_responses_report_both_api_picker_slugs(self) -> None:
        for model in (proxy.SOL_NONE_MODEL, proxy.SOL_FAST_MODEL):
            response = proxy._base_response(
                "resp_test",
                "completed",
                [],
                {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                model,
            )
            self.assertEqual(response["model"], model)


if __name__ == "__main__":
    unittest.main()
