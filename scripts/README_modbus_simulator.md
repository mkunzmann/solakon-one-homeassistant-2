Modbus TCP Simulator for Solakon ONE
=================================

This simulator exposes the registers used by the `solakon_one` custom
integration over Modbus TCP. It reads the `REGISTERS` mapping from
`custom_components/solakon_one/const.py` and serves holding/input registers
initialized with sensible defaults. Read/write registers marked `rw: True`
are writable by clients.

Quick start
-----------

1. From the repository root, install dependencies (preferably inside a venv):

```bash
python -m pip install -r requirements.txt
```

2. Run the simulator (default port 5020):

```bash
python scripts/modbus_simulator.py --host 0.0.0.0 --port 5020
```

3. Configure your Home Assistant integration to connect to the simulator's
   host/port (use Slave ID 1 by default).

Notes
-----
- The script attempts to be compatible with pymodbus 2.x and 3.x imports.
- Default register values are heuristic and intended for development/testing
  only. You can modify `scripts/modbus_simulator.py` to set custom values.

Troubleshooting
---------------
- If imports fail, ensure `pymodbus` is installed. You may need to adjust the
  server import paths if a future pymodbus releases break compatibility.
