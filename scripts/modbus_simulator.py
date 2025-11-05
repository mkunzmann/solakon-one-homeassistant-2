#!/usr/bin/env python3
"""Simple Modbus TCP simulator for the Solakon ONE custom integration.

This script reads the `REGISTERS` mapping from the integration's
`custom_components.solakon_one.const` and exposes those addresses on a
Modbus TCP server. Read/Write registers (marked with "rw": True) are
writable; others are initialized with sensible defaults.

Run from the repository root so the integration package can be imported.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Dict

# Require pymodbus 3.x
from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusDeviceContext,
    ModbusServerContext,
)
# Binary payload builder not required; we pack registers manually


LOG = logging.getLogger("modbus_simulator")


def prepare_repo_imports():
    """Ensure repository root is on sys.path so we can import the integration module."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(this_dir)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def build_registers(registers_map: Dict[str, Dict]) -> list:
    """Construct a flat list of holding registers (0-based) and populate with defaults.

    The integration uses register addresses like 30000, 39123, etc. We map those
    to zero-based indices by subtracting 1 and allocate a block large enough to
    contain the highest addressed register + span.
    """
    # Load the integration's const.py directly to avoid importing package
    # entry points that require Home Assistant to be installed.
    import importlib.util

    repo_root = os.path.dirname(os.path.dirname(__file__))
    const_path = os.path.join(repo_root, "custom_components", "solakon_one", "const.py")
    spec = importlib.util.spec_from_file_location("solakon_one_const", const_path)
    const_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(const_mod)
    REGISTERS = getattr(const_mod, "REGISTERS")

    # compute maximum register index we need
    max_addr = 0
    for name, info in REGISTERS.items():
        addr = int(info["address"]) if "address" in info else 0
        count = int(info.get("count", 1))
        max_addr = max(max_addr, addr + count)

    size = max_addr + 10
    LOG.info("Allocating %d holding registers (0-based)", size)
    regs = [0] * size

    # helper to write register list into regs at zero-based index
    def write_regs(start_idx: int, registers: list):
        if start_idx + len(registers) > len(regs):
            raise IndexError("Register write exceeds allocated size")
        regs[start_idx : start_idx + len(registers)] = registers

    for name, info in REGISTERS.items():
        addr = int(info["address"])  # addresses are 1-based in mapping
        count = int(info.get("count", 1))
        rtype = info.get("type", "u16")
        scale = info.get("scale", 1)

        start = addr - 1

        # pick a reasonable default physical value by heuristics
        physical_value = 0
        if "voltage" in name:
            if "pv" in name:
                physical_value = 300.0
            elif "grid" in name:
                physical_value = 230.0
            elif "battery" in name:
                physical_value = 48.0
        elif "current" in name:
            physical_value = 10.0
        elif name.endswith("power") or "power" in name:
            physical_value = 500.0
        elif "soc" in name.lower():
            physical_value = 50
        elif "frequency" in name:
            physical_value = 50.0
        elif "temperature" in name or "temp" in name:
            physical_value = 30.0
        elif rtype == "string":
            physical_value = None
        else:
            physical_value = 0

        if rtype == "string":
            # store a readable string (pad/truncate to count*2 bytes)
            text = info.get("default", name)
            max_bytes = count * 2
            b = text.encode("ascii", errors="ignore")[:max_bytes]
            b = b.ljust(max_bytes, b"\x00")
            # pack into 16-bit big-endian words
            registers = [((b[i] << 8) | b[i + 1]) for i in range(0, len(b), 2)]
            write_regs(start, registers)
            continue

        # numeric types (pack manually to avoid dependency on BinaryPayloadBuilder)
        if rtype in ("u16", "bitfield16"):
            raw = int(physical_value * scale)
            registers = [raw & 0xFFFF]
            write_regs(start, registers)
        elif rtype == "i16":
            raw = int(physical_value * scale)
            registers = [raw & 0xFFFF]
            write_regs(start, registers)
        elif rtype == "u32":
            raw = int(physical_value * scale) & 0xFFFFFFFF
            high = (raw >> 16) & 0xFFFF
            low = raw & 0xFFFF
            registers = [high, low][:count]
            write_regs(start, registers)
        elif rtype == "i32":
            raw = int(physical_value * scale) & 0xFFFFFFFF
            high = (raw >> 16) & 0xFFFF
            low = raw & 0xFFFF
            registers = [high, low][:count]
            write_regs(start, registers)
        else:
            # Unknown type — write zeros
            write_regs(start, [0] * count)

    return regs


def run_server(host: str, port: int):
    # Build holding registers and put them into a datastore
    # `build_registers` loads the integration's `const.py` directly so we
    # avoid importing the integration package (which would require
    # Home Assistant to be installed).
    holding = build_registers({})

    block = ModbusSequentialDataBlock(0, holding)

    # For simplicity, mirror holding registers into input registers and
    # create empty blocks for coils/discrete inputs.
    device = ModbusDeviceContext(
        di=ModbusSequentialDataBlock(0, [0] * len(holding)),
        co=ModbusSequentialDataBlock(0, [0] * len(holding)),
        hr=block,
        ir=ModbusSequentialDataBlock(0, holding),
    )

    context = ModbusServerContext(devices=device, single=True)

    LOG.info("Starting Modbus TCP simulator on %s:%d", host, port)
    StartTcpServer(context, address=(host, port))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Modbus TCP simulator for Solakon ONE integration"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind the Modbus TCP server"
    )
    parser.add_argument(
        "--port", type=int, default=5020, help="Port to bind (default 5020)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
