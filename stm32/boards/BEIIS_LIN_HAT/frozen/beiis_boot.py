try:
    import beiis_runtime
    beiis_runtime.boot_if_needed()
except Exception as exc:
    import sys
    sys.print_exception(exc)
