import gc
import esp
from machine import UART

esp.osdebug(None)

# WROOM-1 dev board has a single USB-UART bridge wired to GPIO43/44 (UART0).
# Our GPS is also on those pins, so release UART0 from the REPL here.
# The REPL still works fine over the native USB-CDC interface used by mpremote.
try:
    UART(0).deinit()
except Exception:
    pass

gc.collect()
