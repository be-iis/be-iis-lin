#!/usr/bin/env bash
set -euo pipefail

example="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$example/../.." && pwd)"
venv="$root/.venv"
socket="/tmp/beiis-lin-ip.sock"
lock="/tmp/beiis-lin-ip.lock"
bridge_log="/tmp/beiis-lin-ip-bridge.log"
daemon_log="/tmp/beiis-lin-ip-daemon.log"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo examples/ip-over-lin/test-hardware.sh" >&2
  exit 1
fi

[[ -x "$venv/bin/beiis-lind" ]] || {
  echo "Missing host environment. Run: make host" >&2
  exit 1
}

# The IP test deliberately uses a temporary socket backend, never a service.
systemctl disable --now beiis-lind.service 2>/dev/null || true

# Remove the superseded direct-I2C lin0 prototype if it is still loaded from
# an earlier test. The new lin0 is a TUN interface owned by beiis-lin-ip.
ip link set lin0 down 2>/dev/null || true
rmmod beiis_lin_net 2>/dev/null || true

rm -f "$socket" "$lock" "$bridge_log" "$daemon_log"

daemon_pid=""
bridge_pid=""

cleanup() {
  if [[ -n "$bridge_pid" ]]; then
    kill "$bridge_pid" 2>/dev/null || true
    wait "$bridge_pid" 2>/dev/null || true
  fi

  if [[ -n "$daemon_pid" ]]; then
    kill "$daemon_pid" 2>/dev/null || true
    wait "$daemon_pid" 2>/dev/null || true
  fi

  rm -f "$socket" "$lock"
}
trap cleanup EXIT INT TERM

"$venv/bin/beiis-lind"   --bus "${I2C_BUS:-1}"   --address "${I2C_ADDRESS:-0x42}"   --socket "$socket"   --mode 0666   --lock-file "$lock"   >"$daemon_log" 2>&1 &
daemon_pid=$!

for _ in $(seq 1 100); do
  [[ -S "$socket" ]] && break
  if ! kill -0 "$daemon_pid" 2>/dev/null; then
    echo "beiis-lind exited:" >&2
    cat "$daemon_log" >&2
    exit 1
  fi
  sleep 0.05
done

[[ -S "$socket" ]] || {
  echo "Socket backend did not start: $socket" >&2
  cat "$daemon_log" >&2
  exit 1
}

"$venv/bin/python" "$example/bridge.py"   --socket "$socket"   --ifname lin0   --address "${LIN_LOCAL_IP:-10.42.1.1/24}"   --nodes 2   --wire-loopback   >"$bridge_log" 2>&1 &
bridge_pid=$!

for _ in $(seq 1 100); do
  if ip link show lin0 >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$bridge_pid" 2>/dev/null; then
    echo "IP bridge exited:" >&2
    cat "$bridge_log" >&2
    exit 1
  fi
  sleep 0.05
done

if ! ip link show lin0 >/dev/null 2>&1; then
  echo "lin0 was not created." >&2
  cat "$bridge_log" >&2
  exit 1
fi

echo
ip -details addr show dev lin0
echo
echo "Path:"
echo "  Linux IP -> lin0(TUN) -> beiis-lin-ip -> Unix socket -> beiis-lind -> STM32 -> LIN"
echo
echo "Pinging 10.42.1.2 ..."

if ! ping -I lin0 -c 3 -W 3 "${LIN_TEST_PEER:-10.42.1.2}"; then
  echo
  echo "Bridge log:"
  cat "$bridge_log"
  echo
  echo "Daemon log:"
  cat "$daemon_log"
  exit 1
fi

echo
echo "PASS: IPv4 ICMP crossed the TUN/socket/LIN path."
