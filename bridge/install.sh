#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
codex_home="${CODEX_HOME:-$HOME/.codex}"
router_dir="$codex_home/antigravity-router"
config_file="$codex_home/config.toml"
obsolete_instant_skill_dir="$codex_home/skills/computer-use-chatgpt-instant"
launch_agents_dir="$HOME/Library/LaunchAgents"
router_plist="$launch_agents_dir/com.tushar.codex-antigravity-router.plist"
compat_plist="$launch_agents_dir/com.tushar.codex-sky-executor-compat.plist"
codex_bin="/Applications/ChatGPT.app/Contents/Resources/codex"
user_domain="gui/$(id -u)"

if [[ ! -x "$codex_bin" ]]; then
  print -u2 "Codex executable was not found: $codex_bin"
  exit 1
fi
if [[ ! -x "$HOME/.local/bin/agy" ]]; then
  print -u2 "Antigravity CLI was not found: $HOME/.local/bin/agy"
  exit 1
fi
if [[ ! -f "$codex_home/models_cache.json" ]]; then
  print -u2 "Codex model cache was not found: $codex_home/models_cache.json"
  print -u2 "Open Codex once, then run this installer again."
  exit 1
fi

install -d -m 700 "$router_dir"
install -d -m 700 "$codex_home"
install -d -m 755 "$launch_agents_dir"

router_files=(
  AGENTS.md
  antigravity_responses_proxy.py
  build_model_catalog.py
  model-catalog.json
  planner-output.schema.json
  test_antigravity_responses_proxy.py
)
for file_name in "${router_files[@]}"; do
  install -m 600 "$script_dir/$file_name" "$router_dir/$file_name"
done
install -m 755 "$script_dir/antigravity_responses_proxy.py" "$router_dir/antigravity_responses_proxy.py"
install -m 755 "$script_dir/build_model_catalog.py" "$router_dir/build_model_catalog.py"

if [[ -d "$obsolete_instant_skill_dir" ]]; then
  /bin/rm -R "$obsolete_instant_skill_dir"
fi

/usr/bin/env python3 "$router_dir/build_model_catalog.py" \
  --source "$codex_home/models_cache.json" \
  --gemini "$router_dir/model-catalog.json" \
  --output "$router_dir/merged-model-catalog.json"

install -m 600 "$script_dir/com.tushar.codex-antigravity-router.plist" "$router_plist"
install -m 644 "$script_dir/com.tushar.codex-sky-executor-compat.plist" "$compat_plist"
plutil -lint "$router_plist" "$compat_plist"

launchctl bootout "$user_domain/com.tushar.codex-antigravity-router" 2>/dev/null || true
launchctl bootout "$user_domain/com.tushar.codex-sky-executor-compat" 2>/dev/null || true
launchctl setenv SWIFT_IS_CURRENT_EXECUTOR_LEGACY_MODE_OVERRIDE legacy
launchctl bootstrap "$user_domain" "$compat_plist"
launchctl bootstrap "$user_domain" "$router_plist"
launchctl kickstart -k "$user_domain/com.tushar.codex-antigravity-router"

if [[ -f "$config_file" ]]; then
  backup_file="$config_file.backup-codex-bridge-$(date +%Y%m%d-%H%M%S)-$$"
  cp -p "$config_file" "$backup_file"
  print "Saved config backup: $backup_file"
fi

/usr/bin/env python3 "$script_dir/configure_codex.py" \
  --codex "$codex_bin" \
  --config "$config_file" \
  --catalog "$router_dir/merged-model-catalog.json" \
  --set-default

for attempt in {1..40}; do
  if curl -fsS "http://127.0.0.1:55437/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done
curl -fsS "http://127.0.0.1:55437/health" >/dev/null

"$script_dir/verify.sh"
print "Installation passed. New Gemini tasks use the updated router immediately."
