#!/usr/bin/env python3
"""Install the local Antigravity model provider through Codex app-server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tomllib
from typing import Any


DEFAULT_CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
MODEL = "gemini-3.7-flash-low"
SOL_NONE_MODEL = "gpt-5.6-sol-none"
CUSTOM_MODELS = {MODEL, SOL_NONE_MODEL, "gpt-5.6-sol-fast"}
PROVIDER = "antigravity-router"


def send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def receive(process: subprocess.Popen[str], request_id: int) -> dict[str, Any]:
    assert process.stdout is not None
    while True:
        line = process.stdout.readline()
        if not line:
            raise RuntimeError("Codex app-server closed before it returned a response")
        message = json.loads(line)
        if message.get("id") == request_id:
            return message


def require_result(message: dict[str, Any]) -> dict[str, Any]:
    if "error" in message:
        raise RuntimeError(json.dumps(message["error"], ensure_ascii=False))
    result = message.get("result")
    return result if isinstance(result, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex", type=Path, default=DEFAULT_CODEX)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--set-default", action="store_true")
    args = parser.parse_args()

    default_model = MODEL
    if args.config.is_file():
        try:
            configured = tomllib.loads(
                args.config.read_text(encoding="utf-8")
            ).get("model")
            if configured in CUSTOM_MODELS:
                default_model = configured
        except (OSError, tomllib.TOMLDecodeError):
            pass

    edits: list[dict[str, Any]] = [
        {
            "keyPath": "model_provider",
            "value": PROVIDER,
            "mergeStrategy": "upsert",
        },
        {
            "keyPath": "model_catalog_json",
            "value": str(args.catalog.resolve()),
            "mergeStrategy": "upsert",
        },
        {
            "keyPath": f"model_providers.{PROVIDER}",
            "value": {
                "name": "Codex + Antigravity",
                "base_url": "http://127.0.0.1:55437/v1",
                "wire_api": "responses",
                "requires_openai_auth": True,
                "request_max_retries": 2,
                "stream_max_retries": 2,
            },
            "mergeStrategy": "upsert",
        },
    ]
    if args.set_default:
        default_effort = "none" if default_model == SOL_NONE_MODEL else "low"
        edits[0:0] = [
            {
                "keyPath": "model",
                "value": default_model,
                "mergeStrategy": "upsert",
            },
            {
                "keyPath": "model_reasoning_effort",
                "value": default_effort,
                "mergeStrategy": "upsert",
            },
        ]

    process = subprocess.Popen(
        [str(args.codex), "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        send(
            process,
            {
                "method": "initialize",
                "id": 1,
                "params": {
                    "clientInfo": {
                        "name": "codex-computer-use-bridge",
                        "title": "Native Gemini Installer",
                        "version": "1",
                    },
                    "capabilities": {
                        "experimentalApi": True,
                        "requestAttestation": False,
                    },
                },
            },
        )
        require_result(receive(process, 1))
        send(process, {"method": "initialized"})
        send(
            process,
            {
                "method": "config/batchWrite",
                "id": 2,
                "params": {
                    "filePath": str(args.config.resolve()),
                    "edits": edits,
                    "reloadUserConfig": True,
                },
            },
        )
        require_result(receive(process, 2))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    print(json.dumps({
        "config": str(args.config),
        "provider": PROVIDER,
        "model": default_model,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
