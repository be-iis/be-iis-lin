#!/usr/bin/env bash
set -euo pipefail

echo "IP-over-LIN does not install beiis-lind as a systemd service." >&2
echo "Start beiis-lind manually when a Unix-socket backend is needed." >&2
exit 1
