#!/usr/bin/env python3
"""Build a Codex catalog with local subscription models and OpenAI models."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile


def expand_custom_models(
    source_models: list[dict[str, object]],
    custom_models: list[dict[str, object]],
) -> list[dict[str, object]]:
    source_by_slug = {
        model.get("slug"): model
        for model in source_models
        if isinstance(model.get("slug"), str)
    }
    expanded: list[dict[str, object]] = []
    for custom in custom_models:
        clone_from = custom.get("clone_from")
        if clone_from is None:
            expanded.append(dict(custom))
            continue
        base = source_by_slug.get(clone_from)
        if base is None:
            raise RuntimeError(f"Base model was not found: {clone_from}")
        overrides = {
            key: value
            for key, value in custom.items()
            if key != "clone_from"
        }
        expanded.append({**base, **overrides})
    return expanded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path.home() / ".codex" / "models_cache.json",
    )
    parser.add_argument(
        "--gemini",
        type=Path,
        default=Path(__file__).with_name("model-catalog.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("merged-model-catalog.json"),
    )
    args = parser.parse_args()

    source = json.loads(args.source.read_text())
    custom_specs = json.loads(args.gemini.read_text()).get("models", [])
    if not custom_specs:
        raise RuntimeError("Custom model catalog did not contain any models")
    source_models = source.get("models", [])
    custom_models = expand_custom_models(source_models, custom_specs)
    custom_slugs = {model.get("slug") for model in custom_models}
    models = [
        *custom_models,
        *[
            model
            for model in source_models
            if model.get("slug") not in custom_slugs
        ],
    ]
    merged = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "etag": "local-subscription-models-plus-openai-v2",
        "client_version": source.get("client_version", "0.150.0"),
        "models": models,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=args.output.parent,
        prefix=args.output.name + ".",
        delete=False,
    ) as handle:
        json.dump(merged, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), "models": len(models)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
