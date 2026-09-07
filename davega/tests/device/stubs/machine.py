"""`machine` - only the parts the dashboard touches."""
from fakes import UART, Pin                        # noqa: F401

_uart = UART()


def _the_uart(*a, **kw):
    return _uart


UART = _the_uart
