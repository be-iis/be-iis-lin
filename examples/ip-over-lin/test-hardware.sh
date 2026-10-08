#!/usr/bin/env bash
set -euo pipefail

example="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$example/../.." && pwd)"
venv="$root/.venv"
socket="/tmp/beiis-lin-ip.sock"
lock="/tmp/beiis-lin-ip.lock"
bridge_log="/tmp/beiis-lin-ip-bridge.log"
daemon_log="/tmp/beiis-lin-ip-daemon.log"
iperf_server_log="/tmp/beiis-lin-ip-iperf-server.log"
namespace="${LIN_NODE_NAMESPACE:-beiis-lin-node2}"
peer="${LIN_TEST_PEER:-10.42.1.2}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash examples/ip-over-lin/test-hardware.sh" >&2
  exit 1
fi

[[ -x "$venv/bin/beiis-lind" ]] || {
  echo "Missing host environment. Run: make host" >&2
  exit 1
}

command -v ip >/dev/null || {
  echo "Missing iproute2/ip command" >&2
  exit 1
}

systemctl disable --now beiis-lind.service 2>/dev/null || true
ip link set lin0 down 2>/dev/null || true
rmmod beiis_lin_net 2>/dev/null || true
ip netns del "$namespace" 2>/dev/null || true

rm -f "$socket" "$lock" "$bridge_log" "$daemon_log" "$iperf_server_log"

daemon_pid=""
bridge_pid=""
iperf_pid=""

cleanup() {
  if [[ -n "$iperf_pid" ]]; then
    kill "$iperf_pid" 2>/dev/null || true
    wait "$iperf_pid" 2>/dev/null || true
  fi

  if [[ -n "$bridge_pid" ]]; then
    kill "$bridge_pid" 2>/dev/null || true
    wait "$bridge_pid" 2>/dev/null || true
  fi

  if [[ -n "$daemon_pid" ]]; then
    kill "$daemon_pid" 2>/dev/null || true
    wait "$daemon_pid" 2>/dev/null || true
  fi

  ip netns del "$namespace" 2>/dev/null || true
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

"$venv/bin/python" "$example/bridge.py"   --socket "$socket"   --ifname lin0   --address "${LIN_LOCAL_IP:-10.42.1.1/24}"   --nodes 2   --wire-loopback   --node-namespace "$namespace"   --node-address "${LIN_NODE_IP:-10.42.1.2/24}"   >"$bridge_log" 2>&1 &
bridge_pid=$!

for _ in $(seq 1 200); do
  if ip link show lin0 >/dev/null 2>&1 &&
     ip netns exec "$namespace" ip link show lin-node2 >/dev/null 2>&1; then
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

if ! ip netns exec "$namespace" ip link show lin-node2 >/dev/null 2>&1; then
  echo "node2 network namespace endpoint was not created." >&2
  cat "$bridge_log" >&2
  exit 1
fi

echo
echo "Master endpoint:"
ip -details addr show dev lin0
echo
echo "Node endpoint:"
ip -n "$namespace" -details addr show dev lin-node2
echo
echo "Path:"
echo "  Linux 10.42.1.1 -> master runtime -> LIN1 -> LIN2 -> slave runtime -> Linux 10.42.1.2"
echo
echo "Pinging $peer ..."

if ! ping -I lin0 -c 3 -W 5 "$peer"; then
  echo
  echo "Bridge log:"
  cat "$bridge_log"
  echo
  echo "Daemon log:"
  cat "$daemon_log"
  exit 1
fi

echo
echo "PASS: real IPv4 ICMP crossed both Linux stacks and physical LIN."

if [[ "${RUN_IPERF:-1}" == "0" ]]; then
  echo "SKIP: iperf disabled with RUN_IPERF=0"
  exit 0
fi

if ! command -v iperf3 >/dev/null 2>&1; then
  echo
  echo "iperf3 is not installed on this Pi."
  echo "Install/copy iperf3, then rerun this test (or use RUN_IPERF=0 for ping only)."
  exit 2
fi

echo
echo "Starting iperf3 server inside $namespace ..."
ip netns exec "$namespace" iperf3 -s -1 -B "$peer" >"$iperf_server_log" 2>&1 &
iperf_pid=$!

sleep 0.5

echo "Running short TCP iperf3 test over LIN ..."
if ! timeout "${IPERF_TIMEOUT:-90}"   iperf3 -c "$peer" -t "${IPERF_SECONDS:-3}" -P 1 -M "${IPERF_MSS:-256}"; then
  echo
  echo "iperf3 client/server did not complete."
  echo "Server log:"
  cat "$iperf_server_log" 2>/dev/null || true
  echo
  echo "Bridge log:"
  tail -n 80 "$bridge_log" 2>/dev/null || true
  exit 1
fi

wait "$iperf_pid" || true
iperf_pid=""

echo
echo "iperf3 server:"
cat "$iperf_server_log"
echo
echo "PASS: ping + TCP iperf3 crossed the universal runtime instances and physical LIN."
