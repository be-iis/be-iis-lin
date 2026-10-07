#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
prefix="/opt/beiis-lin"
venv="$prefix/venv"

python3 -m venv "$venv"
"$venv/bin/python" -m pip install -U pip
"$venv/bin/python" -m pip install "$root/host"

ln -sfn "$venv/bin/beiis-lind" /usr/local/bin/beiis-lind
ln -sfn "$venv/bin/beiis-lin" /usr/local/bin/beiis-lin

install -D -m 0644 "$root/host/systemd/beiis-lind.service" /etc/systemd/system/beiis-lind.service

systemctl daemon-reload
systemctl enable beiis-lind.service
systemctl restart beiis-lind.service
systemctl --no-pager --full status beiis-lind.service || true

echo
echo "Socket: /run/beiis/lin-hat.sock"
