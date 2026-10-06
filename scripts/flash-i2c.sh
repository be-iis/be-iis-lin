#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

bus="${I2C_BUS:-1}"
address="${I2C_ADDRESS:-0x42}"
image="${FIRMWARE_BIN:-build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin}"

[[ -f "$image" ]] || { echo "Missing firmware image: $image" >&2; exit 1; }

if [[ -x "$root/.venv/bin/beiis-lin" ]]; then
  cli="$root/.venv/bin/beiis-lin"
elif command -v beiis-lin >/dev/null 2>&1; then
  cli="$(command -v beiis-lin)"
else
  echo "beiis-lin not installed. Run: make host" >&2
  exit 1
fi

"$cli" --bus "$bus" --address "$address" flash "$image"
