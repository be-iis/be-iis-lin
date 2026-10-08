import ctypes
import unittest

from beiis_lin import gpio_irq


class GpioIrqAbiTest(unittest.TestCase):
    def test_linux_gpio_v2_struct_sizes(self):
        self.assertEqual(ctypes.sizeof(gpio_irq._GpioChipInfo), 68)
        self.assertEqual(ctypes.sizeof(gpio_irq._GpioV2LineRequest), 592)
        self.assertEqual(ctypes.sizeof(gpio_irq._GpioV2LineEvent), 48)

    def test_linux_gpio_ioctl_numbers(self):
        self.assertEqual(gpio_irq.GPIO_GET_CHIPINFO_IOCTL, 0x8044B401)
        self.assertEqual(gpio_irq.GPIO_V2_GET_LINE_IOCTL, 0xC250B407)


if __name__ == "__main__":
    unittest.main()
