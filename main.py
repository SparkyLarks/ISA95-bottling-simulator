#!/usr/bin/env python3
"""
Bottling Line Simulator — Entry Point
Amárach StackWorks  |  v1.0

Usage:
    python main.py                     # uses config.yaml in current dir
    python main.py --config my.yaml    # custom config file
    python main.py --speed 120         # override speed factor
    python main.py --port 5020         # override Modbus TCP port
"""
import argparse
import logging
import os
import sys
import time

def setup_logging(level: str = "INFO"):
    fmt = "%(asctime)s  %(levelname)-8s  %(name)-20s  %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

def main():
    parser = argparse.ArgumentParser(description="Bottling Line Modbus Simulator")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--speed",  type=float, help="Override speed_factor")
    parser.add_argument("--port",   type=int,   help="Override Modbus TCP port")
    parser.add_argument("--loglevel", default=None, help="DEBUG/INFO/WARNING")
    args = parser.parse_args()

    # Change to simulator root so relative paths resolve correctly
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    from simulator.config import load_config
    cfg = load_config(args.config)

    if args.speed:
        cfg["simulator"]["speed_factor"] = args.speed
    if args.port:
        cfg["modbus"]["port"] = args.port
    if args.loglevel:
        cfg["logging"]["level"] = args.loglevel

    setup_logging(cfg["logging"]["level"])
    log = logging.getLogger("main")

    # Ensure logs dir exists
    os.makedirs("logs", exist_ok=True)

    log.info("=" * 60)
    log.info("  Bottling Line Simulator  |  Amárach StackWorks  |  v1.0")
    log.info("=" * 60)
    log.info("  Speed factor : %.1fx", cfg["simulator"]["speed_factor"])
    log.info("  Modbus port  : %d", cfg["modbus"]["port"])
    log.info("  Transactions : %s", cfg["logging"]["transactions_file"])
    log.info("=" * 60)

    from simulator.register_map import TOTAL_REGISTERS
    from simulator.modbus_server import ModbusTCPServer
    from simulator.line import LineSimulator

    # Shared register array
    registers = [0] * TOTAL_REGISTERS

    # Start Modbus TCP server
    mb = ModbusTCPServer(
        registers=registers,
        host=cfg["modbus"]["host"],
        port=cfg["modbus"]["port"],
        unit_id=cfg["modbus"]["unit_id"],
    )
    mb.start()

    # Give the server a moment to bind
    time.sleep(0.3)
    log.info("Modbus TCP ready on port %d", mb.port)

    # Start simulation (runs in this thread — blocking)
    sim = LineSimulator(cfg, mb)
    try:
        sim.run()
    except KeyboardInterrupt:
        log.info("Interrupted by user — shutting down")
    finally:
        mb.stop()
        log.info("Simulator stopped.")


if __name__ == "__main__":
    main()
