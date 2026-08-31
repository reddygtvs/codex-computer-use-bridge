#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
codex_home="${CODEX_HOME:-$HOME/.codex}"
router_dir="$codex_home/antigravity-router"
config_file="$codex_home/config.toml"
launch_agents_dir="$HOME/Library/LaunchAgents"
router_plist="$launch_agents_dir/com.tushar.codex-antigravity-router.plist"
compat_plist="$launch_agents_dir/com.tushar.codex-sky-executor-compat.plist"
codex_bin="/Applications/ChatGPT.app/Contents/Resources/codex"

[[ -x "$codex_bin" ]]
[[ -x "$HOME/.local/bin/agy" ]]
[[ -f "$config_file" ]]
[[ -f "$router_dir/antigravity_responses_proxy.py" ]]
[[ -f "$router_dir/merged-model-catalog.json" ]]
[[ -f "$router_plist" ]]
[[ -f "$compat_plist" ]]

plutil -lint "$router_plist" "$compat_plist" >/dev/null
[[ "$(launchctl getenv SWIFT_IS_CURRENT_EXECUTOR_LEGACY_MODE_OVERRIDE)" == "legacy" ]]
curl -fsS "http://127.0.0.1:55437/health" >/dev/null
/usr/bin/security find-generic-password \
  -s "computer-use-agnostic-openai-api-key" \
  -a "openai-platform" -w >/dev/null

/usr/bin/env python3 - "$config_file" "$router_dir/merged-model-catalog.json" <<'PY'
from pathlib import Path
import json
import sys
import tomllib

config_path = Path(sys.argv[1])
catalog_path = Path(sys.argv[2])
config = tomllib.loads(config_path.read_text(encoding="utf-8"))
assert config["model_provider"] == "antigravity-router"
assert Path(config["model_catalog_json"]) == catalog_path
provider = config["model_providers"]["antigravity-router"]
assert provider["base_url"] == "http://127.0.0.1:55437/v1"
assert provider["wire_api"] == "responses"
assert provider["requires_openai_auth"] is True
catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
assert any(model.get("slug") == "gemini-3.7-flash-low" for model in catalog["models"])
assert any(model.get("slug") == "gpt-5.6-sol-none" for model in catalog["models"])
assert any(model.get("slug") == "gpt-5.6-sol-fast" for model in catalog["models"])
assert not any(model.get("slug") == "gpt-5.6-sol-instant" for model in catalog["models"])
print(json.dumps({"models": len(catalog["models"]), "provider": "antigravity-router"}))
PY

cmp -s "$script_dir/antigravity_responses_proxy.py" "$router_dir/antigravity_responses_proxy.py"
cmp -s "$script_dir/AGENTS.md" "$router_dir/AGENTS.md"
if ps -axo command= | grep -E 'SkyComputerUseClient mcp$' | grep -v 'event-stream mcp$' >/dev/null; then
  print -u2 "An obsolete plain Sky prewarmer is running."
  exit 1
fi

/usr/bin/env python3 -m py_compile "$router_dir/antigravity_responses_proxy.py" "$router_dir/build_model_catalog.py" "$script_dir/configure_codex.py"
(cd "$router_dir" && /usr/bin/env python3 -m unittest -q test_antigravity_responses_proxy.py)
codesign --verify --deep --strict "/Applications/ChatGPT.app"

print "Codex: $($codex_bin -V)"
print "Antigravity: $($HOME/.local/bin/agy --version 2>/dev/null | head -n 1)"
print "Native Gemini, Sol None API, and Sol Fast API persistence checks passed."
