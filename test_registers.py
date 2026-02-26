#!/usr/bin/env python3
"""
Quick Modbus register reader — connect to running simulator and dump all registers.
Usage:  python test_registers.py [--host 127.0.0.1] [--port 502]
"""
import argparse
import socket
import struct
import sys

def read_holding_registers(host, port, start, count, unit_id=1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    sock.connect((host, port))

    # MBAP + PDU
    trans_id, proto_id, length = 1, 0, 6
    pdu = struct.pack(">HHHBBHH", trans_id, proto_id, length,
                      unit_id, 0x03, start, count)
    sock.sendall(pdu)

    # Read response header (6 bytes MBAP)
    resp_header = b""
    while len(resp_header) < 6:
        resp_header += sock.recv(6 - len(resp_header))

    resp_length = struct.unpack(">H", resp_header[4:6])[0]
    resp_body = b""
    while len(resp_body) < resp_length:
        resp_body += sock.recv(resp_length - len(resp_body))

    sock.close()
    byte_count = resp_body[2]
    values = struct.unpack(f">{byte_count // 2}H", resp_body[3:3 + byte_count])
    return values


def unpack_float32(h, l):
    return struct.unpack(">f", struct.pack(">HH", h, l))[0]


def unpack_uint32(h, l):
    return (h << 16) | l


LINE_STATE_NAMES = {0:"IDLE",1:"RUNNING",2:"MICROSTOP",3:"STOPPED",4:"FAULT",5:"CHANGEOVER",6:"CIP"}
STOP_CODES = {0:"none",1:"MS01",2:"MS02",3:"MS03",4:"MS04",5:"MS05",
              6:"MS06",7:"MS07",8:"MS08",9:"MS09",10:"MS10",
              11:"ST01",12:"ST02",13:"ST03",14:"ST04",
              21:"BD-M1",22:"BD-M2",23:"BD-M3"}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=502)
    args = p.parse_args()

    try:
        regs = read_holding_registers(args.host, args.port, 0, 60)
    except Exception as e:
        print(f"Could not connect to {args.host}:{args.port} — {e}")
        print("Try --port 5020 if simulator is not running as root.")
        sys.exit(1)

    def r(i): return regs[i] if i < len(regs) else 0

    print("\n╔═══ Bottling Line — Register Snapshot ══════════════════════╗")
    print(f"  Line State       : {LINE_STATE_NAMES.get(r(0), r(0))}")
    print(f"  Line Speed       : {unpack_float32(r(1),r(2)):.1f} bpm")
    print(f"  Good Count       : {unpack_uint32(r(3),r(4))}")
    print(f"  Reject Count     : {unpack_uint32(r(5),r(6))}")
    print(f"  Order Index      : {'IDLE' if r(7)==0xFFFF else r(7)}")
    print(f"  SKU Index        : {'IDLE' if r(8)==0xFFFF else r(8)}")
    print(f"  Stop Code        : {STOP_CODES.get(r(9), r(9))}")
    print(f"  Fault Code       : {r(10)}")
    print(f"  Order Seq        : {r(11)}")
    print(f"  Speed Factor×10  : {r(12)} ({r(12)/10:.1f}×)")
    print(f"")
    print(f"  [Infeed01]")
    print(f"    Bottle Presence: {bool(r(14))}")
    print(f"    Infeed Rate    : {unpack_float32(r(15),r(16)):.1f} bpm")
    print(f"    Starved        : {bool(r(17))}")
    print(f"    Jam Detected   : {bool(r(18))}")
    print(f"")
    print(f"  [Filler01]")
    print(f"    Target Weight  : {unpack_float32(r(20),r(21)):.1f} g")
    print(f"    Actual Weight  : {unpack_float32(r(22),r(23)):.1f} g")
    print(f"    Fill Time      : {unpack_uint32(r(24),r(25))} ms")
    print(f"    Scale Stable   : {bool(r(26))}")
    print(f"    Drip Sensor    : {bool(r(27))}")
    print(f"")
    print(f"  [Capper01]")
    print(f"    Torque Target  : {unpack_float32(r(29),r(30)):.1f} Ncm")
    print(f"    Torque Actual  : {unpack_float32(r(31),r(32)):.1f} Ncm")
    print(f"    Torque In Spec : {bool(r(33))}")
    print(f"    Cap Feed OK    : {bool(r(34))}")
    print(f"")
    print(f"  [Checkweigher01]")
    print(f"    Gross Weight   : {unpack_float32(r(36),r(37)):.1f} g")
    print(f"    Weight In Spec : {bool(r(38))}")
    print(f"    Rezero Active  : {bool(r(39))}")
    print(f"")
    print(f"  [Labeller01]")
    print(f"    Label Applied  : {bool(r(41))}")
    print(f"    Label Sensor   : {bool(r(42))}")
    print(f"    Label Stock    : {r(43)}%")
    print(f"")
    print(f"  [Scanner01]")
    print(f"    Barcode OK     : {bool(r(45))}")
    print(f"    Rescan Count   : {r(46)}")
    print(f"")
    print(f"  [Labeller02]")
    print(f"    Hazard Required: {bool(r(48))}")
    print(f"    Hazard Applied : {bool(r(49))}")
    print(f"    Hazard Stock   : {r(50)}%")
    print(f"")
    print(f"  [RejectPusher01]")
    print(f"    Reject Triggered: {bool(r(52))}")
    print(f"    Reject Reason  : {r(53)}")
    print(f"    Pusher Cycle   : {unpack_uint32(r(54),r(55))} ms")
    print("╚══════════════════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    main()
