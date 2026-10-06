/* STM32G0B0KET6: 512 KiB flash, 144 KiB contiguous SRAM.
 *
 * Flash layout:
 *   0x08000000..0x08007fff  mboot (32 KiB, linked separately)
 *   0x08008000..0x08057fff  MicroPython application (320 KiB)
 *   0x08058000..0x0807ffff  internal filesystem (160 KiB)
 *
 * FLASH remains defined for the legacy non-mboot build. The normal product
 * build uses FLASH_APP via common_bl.ld.
 */
MEMORY
{
    RAM (xrw)       : ORIGIN = 0x20000000, LENGTH = 144K
    FLASH (rx)      : ORIGIN = 0x08000000, LENGTH = 352K
    FLASH_APP (rx)  : ORIGIN = 0x08008000, LENGTH = 320K
    FLASH_FS (rx)   : ORIGIN = 0x08058000, LENGTH = 160K
}

_minimum_heap_size = 0x200;
_minimum_stack_size = 0x400;

_ram_start = ORIGIN(RAM);
_ram_end = ORIGIN(RAM) + LENGTH(RAM);

_micropy_hw_internal_flash_storage_ram_cache_end = ORIGIN(RAM) + LENGTH(RAM);
_micropy_hw_internal_flash_storage_ram_cache_start = _micropy_hw_internal_flash_storage_ram_cache_end - 2K;

_estack = _micropy_hw_internal_flash_storage_ram_cache_start - _estack_reserve;
_sstack = _estack - 8K;

_heap_start = _ebss;
_heap_end = _sstack;

_micropy_hw_internal_flash_storage_start = ORIGIN(FLASH_FS);
_micropy_hw_internal_flash_storage_end = ORIGIN(FLASH_FS) + LENGTH(FLASH_FS);
