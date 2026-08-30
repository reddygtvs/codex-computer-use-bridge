#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
snapshot_dir="$script_dir/snapshots/pre-general-tools"
router_dir="${CODEX_HOME:-$HOME/.codex}/antigravity-router"
user_domain="gui/$(id -u)"

[[ -f "$snapshot_dir/antigravity_responses_proxy.py" ]]
[[ -f "$snapshot_dir/AGENTS.md" ]]
[[ -d "$router_dir" ]]

backup_dir="$router_dir/rollback-backup-$(date +%Y%m%d-%H%M%S)-$$"
install -d -m 700 "$backup_dir"
cp -p "$router_dir/antigravity_responses_proxy.py" "$backup_dir/"
cp -p "$router_dir/AGENTS.md" "$backup_dir/"

install -m 755 "$snapshot_dir/antigravity_responses_proxy.py" \
  "$router_dir/antigravity_responses_proxy.py"
install -m 600 "$snapshot_dir/AGENTS.md" "$router_dir/AGENTS.md"

launchctl kickstart -k \
  "$user_domain/com.tushar.codex-antigravity-router"

for attempt in {1..40}; do
  if curl -fsS "http://127.0.0.1:55437/health" >/dev/null 2>&1; then
    print "Restored the exact pre-bridge Computer Use adapter."
    print "Saved the replaced files in: $backup_dir"
    exit 0
  fi
  sleep 0.25
done

print -u2 "The rollback files were installed, but the router health check failed."
exit 1
