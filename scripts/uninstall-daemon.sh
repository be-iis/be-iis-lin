#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

systemctl disable --now beiis-lind.service 2>/dev/null || true
rm -f /etc/systemd/system/beiis-lind.service
rm -f /usr/local/bin/beiis-lind /usr/local/bin/beiis-lin
rm -rf /opt/beiis-lin
systemctl daemon-reload
