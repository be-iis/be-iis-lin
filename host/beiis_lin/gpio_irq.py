from __future__ import annotations

import ctypes
import fcntl
import glob
import os
import select
from dataclasses import dataclass


GPIO_V2_LINES_MAX = 64
GPIO_V2_LINE_NUM_ATTRS_MAX = 10

GPIO_V2_LINE_FLAG_INPUT = 1 << 2
GPIO_V2_LINE_FLAG_EDGE_RISING = 1 << 4
GPIO_V2_LINE_FLAG_EDGE_FALLING = 1 << 5


def _ioc(direction: int, type_: int, nr: int, size: int) -> int:
    return (
        (direction << 30)
        | (size << 16)
        | (type_ << 8)
        | nr
    )


class _GpioChipInfo(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 32),
        ("label", ctypes.c_char * 32),
        ("lines", ctypes.c_uint32),
    ]


class _GpioV2LineAttributeValue(ctypes.Union):
    _fields_ = [
        ("flags", ctypes.c_uint64),
        ("values", ctypes.c_uint64),
        ("debounce_period_us", ctypes.c_uint32),
    ]


class _GpioV2LineAttribute(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint32),
        ("padding", ctypes.c_uint32),
        ("value", _GpioV2LineAttributeValue),
    ]


class _GpioV2LineConfigAttribute(ctypes.Structure):
    _fields_ = [
        ("attr", _GpioV2LineAttribute),
        ("mask", ctypes.c_uint64),
    ]


class _GpioV2LineConfig(ctypes.Structure):
    _fields_ = [
        ("flags", ctypes.c_uint64),
        ("num_attrs", ctypes.c_uint32),
        ("padding", ctypes.c_uint32 * 5),
        ("attrs", _GpioV2LineConfigAttribute * GPIO_V2_LINE_NUM_ATTRS_MAX),
    ]


class _GpioV2LineRequest(ctypes.Structure):
    _fields_ = [
        ("offsets", ctypes.c_uint32 * GPIO_V2_LINES_MAX),
        ("consumer", ctypes.c_char * 32),
        ("config", _GpioV2LineConfig),
        ("num_lines", ctypes.c_uint32),
        ("event_buffer_size", ctypes.c_uint32),
        ("padding", ctypes.c_uint32 * 5),
        ("fd", ctypes.c_int32),
    ]


class _GpioV2LineEvent(ctypes.Structure):
    _fields_ = [
        ("timestamp_ns", ctypes.c_uint64),
        ("id", ctypes.c_uint32),
        ("offset", ctypes.c_uint32),
        ("seqno", ctypes.c_uint32),
        ("line_seqno", ctypes.c_uint32),
        ("padding", ctypes.c_uint32 * 6),
    ]


class _GpioV2LineValues(ctypes.Structure):
    _fields_ = [
        ("bits", ctypes.c_uint64),
        ("mask", ctypes.c_uint64),
    ]


GPIO_GET_CHIPINFO_IOCTL = _ioc(
    2, 0xB4, 0x01, ctypes.sizeof(_GpioChipInfo)
)
GPIO_V2_GET_LINE_IOCTL = _ioc(
    3, 0xB4, 0x07, ctypes.sizeof(_GpioV2LineRequest)
)
GPIO_V2_LINE_GET_VALUES_IOCTL = _ioc(
    3, 0xB4, 0x0E, ctypes.sizeof(_GpioV2LineValues)
)


def _ioctl_struct(fd: int, request: int, value: ctypes.Structure) -> None:
    size = ctypes.sizeof(value)
    data = bytearray(ctypes.string_at(ctypes.addressof(value), size))
    fcntl.ioctl(fd, request, data, True)
    ctypes.memmove(ctypes.addressof(value), bytes(data), size)


def _decode_cstr(value) -> str:
    return bytes(value).split(b"\0", 1)[0].decode("utf-8", "replace")


@dataclass(frozen=True)
class GpioChip:
    path: str
    name: str
    label: str
    lines: int


def gpio_chips() -> list[GpioChip]:
    chips: list[GpioChip] = []

    for path in sorted(glob.glob("/dev/gpiochip*")):
        fd = None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
            info = _GpioChipInfo()
            _ioctl_struct(fd, GPIO_GET_CHIPINFO_IOCTL, info)
            chips.append(
                GpioChip(
                    path=path,
                    name=_decode_cstr(info.name),
                    label=_decode_cstr(info.label),
                    lines=int(info.lines),
                )
            )
        except OSError:
            continue
        finally:
            if fd is not None:
                os.close(fd)

    return chips


def _chip_priority(chip: GpioChip, offset: int) -> tuple[int, str]:
    text = f"{chip.name} {chip.label}".lower()

    if offset >= chip.lines:
        return (100, chip.path)
    if "rp1" in text:
        return (0, chip.path)
    if "pinctrl-bcm" in text:
        return (1, chip.path)
    if "pinctrl" in text:
        return (2, chip.path)
    return (20, chip.path)


class HostGpioIrq:
    """Wait for both edges on one Linux GPIO line using GPIO character ABI v2."""

    def __init__(
        self,
        offset: int = 6,
        chip: str | None = None,
        consumer: str = "beiis-lind",
    ):
        self.offset = int(offset)
        self.chip_path = ""
        self.chip_name = ""
        self.chip_label = ""
        self._chip_fd = -1
        self._line_fd = -1
        self._idle_value = None

        candidates = gpio_chips()
        if chip is not None:
            candidates = [
                item
                for item in candidates
                if item.path == chip or item.name == chip or item.label == chip
            ]
            if not candidates:
                raise OSError(f"GPIO chip not found: {chip}")
        else:
            candidates.sort(key=lambda item: _chip_priority(item, self.offset))

        last_error: Exception | None = None
        for item in candidates:
            if self.offset >= item.lines:
                continue
            try:
                self._request(item, consumer)
                return
            except OSError as exc:
                last_error = exc
                self.close()

        if last_error is not None:
            raise OSError(
                f"could not request GPIO{self.offset} event line: {last_error}"
            )
        raise OSError(f"no GPIO chip exposes offset {self.offset}")

    @property
    def available(self) -> bool:
        return self._line_fd >= 0

    @property
    def description(self) -> str:
        if not self.available:
            return "unavailable"
        label = self.chip_label or self.chip_name or self.chip_path
        return f"{label}:GPIO{self.offset}"

    def _request(self, chip: GpioChip, consumer: str) -> None:
        chip_fd = os.open(chip.path, os.O_RDONLY | os.O_CLOEXEC)
        req = _GpioV2LineRequest()
        req.offsets[0] = self.offset
        req.consumer = consumer.encode("utf-8")[:31]
        req.config.flags = (
            GPIO_V2_LINE_FLAG_INPUT
            | GPIO_V2_LINE_FLAG_EDGE_RISING
            | GPIO_V2_LINE_FLAG_EDGE_FALLING
        )
        req.num_lines = 1
        req.event_buffer_size = 16

        try:
            _ioctl_struct(chip_fd, GPIO_V2_GET_LINE_IOCTL, req)
        except Exception:
            os.close(chip_fd)
            raise

        if req.fd < 0:
            os.close(chip_fd)
            raise OSError("GPIO line request returned no event fd")

        self._chip_fd = chip_fd
        self._line_fd = int(req.fd)
        os.set_blocking(self._line_fd, False)
        self.chip_path = chip.path
        self.chip_name = chip.name
        self.chip_label = chip.label
        self.drain()
        self._idle_value = self.value()

    def value(self) -> int:
        if not self.available:
            raise OSError("GPIO IRQ line is not available")
        values = _GpioV2LineValues()
        values.mask = 1
        _ioctl_struct(
            self._line_fd,
            GPIO_V2_LINE_GET_VALUES_IOCTL,
            values,
        )
        return 1 if (values.bits & 1) else 0

    def active(self) -> bool:
        if not self.available or self._idle_value is None:
            return False
        return self.value() != self._idle_value

    def wait(self, timeout: float | None = None) -> bool:
        if not self.available:
            return False

        # PC6 is level-based. If another IRQ source already holds the shared
        # line active, there may be no fresh edge for a newly-ready source.
        # Always inspect the current level before sleeping for an edge.
        if self.active():
            return True

        poller = select.poll()
        poller.register(
            self._line_fd,
            select.POLLIN | select.POLLPRI | select.POLLERR,
        )
        timeout_ms = -1 if timeout is None else max(0, int(timeout * 1000))
        events = poller.poll(timeout_ms)
        if not events:
            return False

        self.drain()
        return self.active() or True

    def drain(self) -> None:
        if not self.available:
            return

        event_size = ctypes.sizeof(_GpioV2LineEvent)
        while True:
            try:
                data = os.read(self._line_fd, event_size * 16)
                if not data:
                    return
            except BlockingIOError:
                return

    def close(self) -> None:
        if self._line_fd >= 0:
            os.close(self._line_fd)
            self._line_fd = -1
        if self._chip_fd >= 0:
            os.close(self._chip_fd)
            self._chip_fd = -1
        self._idle_value = None
