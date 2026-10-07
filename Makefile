SHELL := /bin/bash

PYTHON ?= python3
VENV ?= .venv
MICROPYTHON_DIR ?= build/micropython
MICROPYTHON_REF ?= v1.27.0
BOARD ?= BEIIS_LIN_HAT
BOARD_DIR ?= $(abspath stm32/boards/BEIIS_LIN_HAT)

HOST_ARCH := $(shell uname -m)

OPENOCD ?= openocd
OPENOCD_INTERFACE ?= interface/stlink.cfg
OPENOCD_TARGET ?= target/stm32g0x.cfg
OPENOCD_SPEED ?= 100

I2C_BUS ?= 1
I2C_ADDRESS ?= 0x42

FIRMWARE_DIR := $(MICROPYTHON_DIR)/ports/stm32/build-$(BOARD)
BOOTLOADER_DIR := $(MICROPYTHON_DIR)/ports/stm32/mboot/build-$(BOARD)
FIRMWARE_ELF ?= $(FIRMWARE_DIR)/firmware.elf
FIRMWARE_BIN ?= $(FIRMWARE_DIR)/firmware.bin
BOOTLOADER_ELF ?= $(BOOTLOADER_DIR)/firmware.elf

.PHONY: all help check-host-arch prepare prepare-x86 prepare-arm64 	host test test-runtime-hw test-socket-hw test-lan-hw micropython-fetch micropython-patch micropython-submodules 	micropython-build firmware bootloader firmware-all build 	flash flash-swd flash-all flash-bootloader flash-firmware flash-i2c 	restart install-daemon clean

all: host

help:
	@echo "BE-IIS LIN HAT"
	@echo
	@echo "Host architecture: $(HOST_ARCH)"
	@echo
	@echo "  make prepare          Install build/runtime dependencies"
	@echo "  make host             Create venv and install host tools editable"
	@echo "  make test             Run host unit tests"
	@echo "  make test-runtime-hw  Run runtime regression on connected hardware"
	@echo "  make test-socket-hw   Run Unix-socket hardware regression"
	@echo "  make test-lan-hw      Run socket regression over SSH/LAN (LAN_TARGET=user@host)"
	@echo "  make firmware-all     Build mboot + MicroPython application"
	@echo "  make flash-swd        Initial/full flash via ST-Link + OpenOCD"
	@echo "  make flash-i2c        Application update via I2C/mboot"
	@echo "  make install-daemon   Install beiis-lind systemd service"
	@echo "  make clean"

check-host-arch:
	@case "$(HOST_ARCH)" in 		x86_64|aarch64|arm64) ;; 		*) echo "Unsupported host architecture: $(HOST_ARCH)"; exit 1 ;; 	esac

prepare: check-host-arch
	bash scripts/prepare.sh

prepare-x86:
	BEIIS_EXPECT_ARCH=x86_64 bash scripts/prepare.sh

prepare-arm64:
	BEIIS_EXPECT_ARCH=aarch64 bash scripts/prepare.sh

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install -U pip

$(VENV)/.beiis-host-installed: host/pyproject.toml | $(VENV)/bin/python
	$(VENV)/bin/python -m pip install -e ./host
	@touch "$@"

host: check-host-arch $(VENV)/.beiis-host-installed

test: host
	$(VENV)/bin/python -m unittest discover -s host/tests -v

test-runtime-hw: host
	$(VENV)/bin/python scripts/test-runtime-hw.py --bus "$(I2C_BUS)" --address "$(I2C_ADDRESS)"

test-socket-hw: host
	$(VENV)/bin/python scripts/test-socket-hw.py

test-lan-hw: host
	@test -n "$(LAN_TARGET)" || { echo "Set LAN_TARGET=user@pi-host"; exit 2; }
	LAN_TARGET="$(LAN_TARGET)" bash scripts/test-lan-hw.sh

micropython-fetch:
	mkdir -p build
	test -d "$(MICROPYTHON_DIR)/.git" || git clone https://github.com/micropython/micropython.git "$(MICROPYTHON_DIR)"
	git -C "$(MICROPYTHON_DIR)" fetch --tags
	git -C "$(MICROPYTHON_DIR)" checkout --detach --force "$(MICROPYTHON_REF)"

micropython-patch: micropython-fetch
	$(PYTHON) stm32/patches/patch_micropython_g0b0.py "$(MICROPYTHON_DIR)/ports/stm32/stm32_it.c"

micropython-submodules: micropython-patch
	$(MAKE) -C "$(MICROPYTHON_DIR)/ports/stm32" 		BOARD="$(BOARD)" BOARD_DIR="$(BOARD_DIR)" submodules

micropython-build: micropython-submodules
	$(MAKE) -C "$(MICROPYTHON_DIR)/ports/stm32" 		BOARD="$(BOARD)" 		BOARD_DIR="$(BOARD_DIR)" 		USE_MBOOT=1 		LTO=0 		USER_C_MODULES="$(abspath stm32/micropython/modules)" 		CFLAGS_EXTRA="-DBEIIS_LIN_MODULE_ENABLED=1 -DBEIIS_I2C_REPL_ENABLED=1 -DBEIIS_APP_IO_ENABLED=1"

firmware: micropython-build
	@test -f "$(FIRMWARE_BIN)"
	@echo "Application: $(FIRMWARE_BIN)"

bootloader: micropython-submodules
	$(MAKE) -C "$(MICROPYTHON_DIR)/ports/stm32/mboot" 		BOARD="$(BOARD)" BOARD_DIR="$(BOARD_DIR)"
	@test -f "$(BOOTLOADER_ELF)"
	@echo "Bootloader: $(BOOTLOADER_ELF)"

firmware-all: bootloader firmware
build: firmware-all

flash: flash-swd
flash-all: flash-swd

flash-swd: firmware-all
	OPENOCD="$(OPENOCD)" 	OPENOCD_INTERFACE="$(OPENOCD_INTERFACE)" 	OPENOCD_TARGET="$(OPENOCD_TARGET)" 	OPENOCD_SPEED="$(OPENOCD_SPEED)" 	BOARD="$(BOARD)" 	MICROPYTHON_DIR="$(MICROPYTHON_DIR)" 	bash scripts/flash-swd.sh

flash-bootloader: bootloader
	@test -f "$(BOOTLOADER_ELF)" || { echo "Missing $(BOOTLOADER_ELF)"; exit 1; }
	$(OPENOCD) 		-f "$(OPENOCD_INTERFACE)" 		-f "$(OPENOCD_TARGET)" 		-c "reset_config none" 		-c "adapter speed $(OPENOCD_SPEED)" 		-c "init" 		-c "halt" 		-c "program $(abspath $(BOOTLOADER_ELF)) verify" 		-c "cortex_m reset_config sysresetreq" 		-c "reset run" 		-c "shutdown"

flash-firmware: firmware
	@test -f "$(FIRMWARE_ELF)" || { echo "Missing $(FIRMWARE_ELF)"; exit 1; }
	$(OPENOCD) 		-f "$(OPENOCD_INTERFACE)" 		-f "$(OPENOCD_TARGET)" 		-c "reset_config none" 		-c "adapter speed $(OPENOCD_SPEED)" 		-c "init" 		-c "halt" 		-c "program $(abspath $(FIRMWARE_ELF)) verify" 		-c "cortex_m reset_config sysresetreq" 		-c "reset run" 		-c "shutdown"

flash-i2c: firmware host
	I2C_BUS="$(I2C_BUS)" 	I2C_ADDRESS="$(I2C_ADDRESS)" 	FIRMWARE_BIN="$(abspath $(FIRMWARE_BIN))" 	bash scripts/flash-i2c.sh

restart:
	$(OPENOCD) 		-f "$(OPENOCD_INTERFACE)" 		-f "$(OPENOCD_TARGET)" 		-c "reset_config none" 		-c "adapter speed $(OPENOCD_SPEED)" 		-c "init" 		-c "cortex_m reset_config sysresetreq" 		-c "reset run" 		-c "shutdown"

install-daemon: host
	sudo bash scripts/install-daemon.sh

clean:
	rm -rf "$(VENV)" build
