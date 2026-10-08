# Helper scripts

These scripts are kept as plain shell files and can be invoked with `bash`;
an executable file mode is not required.

- `prepare.sh` - install Debian/Ubuntu/Raspberry Pi OS dependencies
- `build.sh` - build mboot and application firmware
- `test.sh` - run host unit tests
- `flash-swd.sh` - initial/full programming through OpenOCD + ST-Link/SWD
- `flash-i2c.sh` - application firmware update through I2C/mboot
- `install-daemon.sh` - install and start `beiis-lind`
- `uninstall-daemon.sh` - remove the installed service and host venv
