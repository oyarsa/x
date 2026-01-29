#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <remote-host>" >&2
    echo "Example: $0 123.45.67.89" >&2
    exit 1
fi

REMOTE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Running bootstrap as root..."
ssh "root@$REMOTE" "bash -s" < "$SCRIPT_DIR/bootstrap-root.sh"

echo "==> Running setup as dev..."
TOKEN="$(gh auth token)"
ssh "dev@$REMOTE" "git clone https://$TOKEN@github.com/oyarsa/x.git ~/x && GITHUB_TOKEN='$TOKEN' ~/x/sandbox/setup.sh"

echo "==> Done! Connect with: ssh dev@$REMOTE"
