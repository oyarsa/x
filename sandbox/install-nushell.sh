#!/bin/bash
set -euo pipefail

mkdir -p /etc/apt/keyrings
curl -fsSL https://apt.fury.io/nushell/gpg.key | gpg --dearmor -o /etc/apt/keyrings/fury-nushell.gpg

echo "deb [signed-by=/etc/apt/keyrings/fury-nushell.gpg] https://apt.fury.io/nushell/ /" |
	tee /etc/apt/sources.list.d/fury-nushell.list >/dev/null

apt-get update
apt-get install -y nushell
