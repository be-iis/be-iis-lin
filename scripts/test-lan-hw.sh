#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

target="${LAN_TARGET:-${1:-}}"
remote_socket="${LAN_REMOTE_SOCKET:-/run/beiis/lin-hat.sock}"
local_socket="${LAN_LOCAL_SOCKET:-/tmp/beiis-lin-lan-${USER:-user}-$$.sock}"

if [[ -z "$target" ]]; then
  echo "Usage: LAN_TARGET=user@pi-host $0" >&2
  echo "   or: $0 user@pi-host" >&2
  exit 2
fi

[[ -x "$root/.venv/bin/python" ]] || {
  echo "Missing .venv. Run: make host" >&2
  exit 1
}

rm -f "$local_socket"
ssh_pid=""

cleanup() {
  if [[ -n "$ssh_pid" ]]; then
    kill "$ssh_pid" 2>/dev/null || true
    wait "$ssh_pid" 2>/dev/null || true
  fi
  rm -f "$local_socket"
}
trap cleanup EXIT INT TERM

echo "Opening SSH Unix-socket forward:"
echo "  local : $local_socket"
echo "  remote: $target:$remote_socket"

ssh \
  -o ExitOnForwardFailure=yes \
  -o StreamLocalBindUnlink=yes \
  -N \
  -L "$local_socket:$remote_socket" \
  "$target" &
ssh_pid=$!

for _ in $(seq 1 100); do
  [[ -S "$local_socket" ]] && break
  if ! kill -0 "$ssh_pid" 2>/dev/null; then
    wait "$ssh_pid"
    exit 1
  fi
  sleep 0.05
done

[[ -S "$local_socket" ]] || {
  echo "SSH forward did not create local socket: $local_socket" >&2
  exit 1
}

"$root/.venv/bin/python" scripts/test-socket-hw.py --socket "$local_socket"
