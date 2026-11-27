"""Drivers for the box's devices. Each is a Session sink (see comlang.session)."""


def serial_ports():
    """[(device, description)] of the serial ports, or [] without pyserial."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [(p.device, " ".join(x for x in (p.description, p.interface or "") if x))
            for p in list_ports.comports()]
