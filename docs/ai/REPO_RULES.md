# AI context: repository rules

When changing this project:

1. Keep portable LIN logic under stm32/lib/lin.
2. Keep board-specific STM32G0B0 details in the board definition/patch layer.
3. Do not make Linux responsible for LIN timing.
4. Do not expose Raw REPL as the primary public application API.
5. Keep beiis-lind as the normal exclusive owner of the I2C endpoint.
6. Preserve the mboot one-shot first-vector MARKVALID scheme.
7. Do not add bootloader write protection unless explicitly requested.
8. Host tests must continue to run with:
   python -m unittest discover -s host/tests -v
9. Human documentation belongs in docs/human.
10. Machine/agent context belongs in docs/ai.
