#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

OPENOCD="${OPENOCD:-openocd}"
OPENOCD_INTERFACE="${OPENOCD_INTERFACE:-interface/stlink.cfg}"
OPENOCD_TARGET="${OPENOCD_TARGET:-target/stm32g0x.cfg}"
OPENOCD_SPEED="${OPENOCD_SPEED:-100}"
BOARD="${BOARD:-BEIIS_LIN_HAT}"
MICROPYTHON_DIR="${MICROPYTHON_DIR:-build/micropython}"

bootloader="${BOOTLOADER_ELF:-$MICROPYTHON_DIR/ports/stm32/mboot/build-$BOARD/firmware.elf}"
firmware="${FIRMWARE_ELF:-$MICROPYTHON_DIR/ports/stm32/build-$BOARD/firmware.elf}"

[[ -f "$bootloader" ]] || { echo "Missing $bootloader" >&2; exit 1; }
[[ -f "$firmware" ]] || { echo "Missing $firmware" >&2; exit 1; }

"$OPENOCD" \
  -f "$OPENOCD_INTERFACE" \
  -f "$OPENOCD_TARGET" \
  -c "reset_config none" \
  -c "adapter speed $OPENOCD_SPEED" \
  -c "init" \
  -c "halt" \
  -c "program $(realpath "$bootloader") verify" \
  -c "program $(realpath "$firmware") verify" \
  -c "cortex_m reset_config sysresetreq" \
  -c "reset run" \
  -c "shutdown"
