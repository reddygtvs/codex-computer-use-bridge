#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"

print "Refreshing the native subscription model integrations for this Codex version."
"$script_dir/install.sh"
