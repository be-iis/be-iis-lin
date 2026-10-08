#!/usr/bin/env bash
set -euo pipefail

arch="$(uname -m)"
expected="${BEIIS_EXPECT_ARCH:-}"

case "$arch" in
  x86_64) canonical="x86_64" ;;
  aarch64|arm64) canonical="aarch64" ;;
  *)
    echo "Unsupported host architecture: $arch" >&2
    exit 1
    ;;
esac

if [[ -n "$expected" ]]; then
  [[ "$expected" == "arm64" ]] && expected="aarch64"
  if [[ "$canonical" != "$expected" ]]; then
    echo "Expected $expected, running on $canonical" >&2
    exit 1
  fi
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "prepare.sh currently supports Debian/Ubuntu/Raspberry Pi OS (apt)." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y \
  git make rsync \
  python3 python3-venv python3-pip \
  gcc-arm-none-eabi libnewlib-arm-none-eabi \
  openocd \
  i2c-tools

echo
echo "Prepared BE-IIS LIN build host: $canonical"
echo "Next: make host && make test && make firmware-all"
