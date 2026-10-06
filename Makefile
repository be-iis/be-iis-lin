PYTHON ?= python3
VENV ?= .venv
MICROPYTHON_DIR ?= build/micropython
MICROPYTHON_REF ?= v1.27.0
BOARD ?= BEIIS_LIN_HAT
BOARD_DIR ?= $(abspath stm32/boards/BEIIS_LIN_HAT)

OPENOCD ?= openocd
OPENOCD_INTERFACE ?= interface/stlink.cfg
OPENOCD_TARGET ?= target/stm32g0x.cfg
OPENOCD_SPEED ?= 100

FIRMWARE_ELF ?= $(MICROPYTHON_DIR)/ports/stm32/build-$(BOARD)/firmware.elf
BOOTLOADER_ELF ?= $(MICROPYTHON_DIR)/ports/stm32/mboot/build-$(BOARD)/firmware.elf

.PHONY: all host test micropython-fetch micropython-patch micropython-submodules \
	micropython-build firmware bootloader flash flash-all flash-bootloader \
	flash-firmware restart clean

all: host

host:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -e ./host

test: host
	$(VENV)/bin/python -m unittest discover -s host/tests -v

micropython-fetch:
	mkdir -p build
	test -d "$(MICROPYTHON_DIR)/.git" || git clone https://github.com/micropython/micropython.git "$(MICROPYTHON_DIR)"
	git -C "$(MICROPYTHON_DIR)" fetch --tags
	git -C "$(MICROPYTHON_DIR)" checkout --detach --force "$(MICROPYTHON_REF)"

micropython-patch: micropython-fetch
	$(PYTHON) stm32/patches/patch_micropython_g0b0.py "$(MICROPYTHON_DIR)/ports/stm32/stm32_it.c"

micropython-submodules: micropython-patch
	$(MAKE) -C "$(MICROPYTHON_DIR)/ports/stm32" \
		BOARD="$(BOARD)" \
		BOARD_DIR="$(BOARD_DIR)" \
		submodules

micropython-build: micropython-submodules
	$(MAKE) -C "$(MICROPYTHON_DIR)/ports/stm32" \
		BOARD="$(BOARD)" \
		BOARD_DIR="$(BOARD_DIR)" \
		USE_MBOOT=1 \
		USER_C_MODULES="$(abspath stm32/micropython/modules)" \
		CFLAGS_EXTRA="-DBEIIS_LIN_MODULE_ENABLED=1 -DBEIIS_I2C_REPL_ENABLED=1"

firmware: micropython-build
	@echo
	@echo "BE-IIS LIN HAT application built at 0x08008000."
	@find "$(MICROPYTHON_DIR)/ports/stm32/build-$(BOARD)" -maxdepth 1 \
		\( -name 'firmware.bin' -o -name 'firmware.hex' -o -name 'firmware.elf' -o -name 'firmware.dfu' \) \
		-print 2>/dev/null || true

bootloader: micropython-submodules
	$(MAKE) -C "$(MICROPYTHON_DIR)/ports/stm32/mboot" \
		BOARD="$(BOARD)" \
		BOARD_DIR="$(BOARD_DIR)"
	@echo
	@echo "BE-IIS LIN HAT mboot built at 0x08000000."
	@find "$(MICROPYTHON_DIR)/ports/stm32/mboot/build-$(BOARD)" -maxdepth 1 \
		\( -name 'firmware.bin' -o -name 'firmware.hex' -o -name 'firmware.elf' -o -name 'firmware.dfu' \) \
		-print 2>/dev/null || true

flash: flash-all

flash-all: bootloader firmware
	@test -f "$(BOOTLOADER_ELF)" || { echo "Missing $(BOOTLOADER_ELF)"; exit 1; }
	@test -f "$(FIRMWARE_ELF)" || { echo "Missing $(FIRMWARE_ELF)"; exit 1; }
	$(OPENOCD) \
		-f "$(OPENOCD_INTERFACE)" \
		-f "$(OPENOCD_TARGET)" \
		-c "reset_config none" \
		-c "adapter speed $(OPENOCD_SPEED)" \
		-c "init" \
		-c "halt" \
		-c "program $(abspath $(BOOTLOADER_ELF)) verify" \
		-c "program $(abspath $(FIRMWARE_ELF)) verify" \
		-c "cortex_m reset_config sysresetreq" \
		-c "reset run" \
		-c "shutdown"

flash-bootloader: bootloader
	@test -f "$(BOOTLOADER_ELF)" || { echo "Missing $(BOOTLOADER_ELF)"; exit 1; }
	$(OPENOCD) \
		-f "$(OPENOCD_INTERFACE)" \
		-f "$(OPENOCD_TARGET)" \
		-c "reset_config none" \
		-c "adapter speed $(OPENOCD_SPEED)" \
		-c "init" \
		-c "halt" \
		-c "program $(abspath $(BOOTLOADER_ELF)) verify" \
		-c "cortex_m reset_config sysresetreq" \
		-c "reset run" \
		-c "shutdown"

flash-firmware: firmware
	@test -f "$(FIRMWARE_ELF)" || { echo "Missing $(FIRMWARE_ELF)"; exit 1; }
	$(OPENOCD) \
		-f "$(OPENOCD_INTERFACE)" \
		-f "$(OPENOCD_TARGET)" \
		-c "reset_config none" \
		-c "adapter speed $(OPENOCD_SPEED)" \
		-c "init" \
		-c "halt" \
		-c "program $(abspath $(FIRMWARE_ELF)) verify" \
		-c "cortex_m reset_config sysresetreq" \
		-c "reset run" \
		-c "shutdown"

restart:
	$(OPENOCD) \
		-f "$(OPENOCD_INTERFACE)" \
		-f "$(OPENOCD_TARGET)" \
		-c "reset_config none" \
		-c "adapter speed $(OPENOCD_SPEED)" \
		-c "init" \
		-c "cortex_m reset_config sysresetreq" \
		-c "reset run" \
		-c "shutdown"

clean:
	rm -rf $(VENV) build
