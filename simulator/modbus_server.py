"""
Pure-Python Modbus TCP Server (FC03 — Read Holding Registers)
─────────────────────────────────────────────────────────────
Implements just enough of the Modbus TCP spec for Node-RED / any
Modbus TCP client to poll holding registers.

Supported function codes:
  FC03  Read Holding Registers
  FC06  Write Single Register      (useful for test clients)
  FC16  Write Multiple Registers   (useful for test clients)

Modbus TCP frame:
  [Transaction ID 2B] [Protocol ID 2B = 0x0000] [Length 2B]
  [Unit ID 1B] [Function Code 1B] [Data NB]
"""
import socket
import struct
import threading
import logging

log = logging.getLogger("modbus_server")


class ModbusTCPServer:
    """Thread-safe Modbus TCP server backed by a flat register array."""

    def __init__(self, registers, host="0.0.0.0", port=502, unit_id=1):
        self._regs = registers          # shared list[int], length = TOTAL_REGISTERS
        self._lock = threading.Lock()
        self._host = host
        self._port = port
        self._unit_id = unit_id
        self._server_sock = None
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────────
    def set_register(self, index: int, value: int):
        with self._lock:
            self._regs[index] = int(value) & 0xFFFF

    def get_register(self, index: int) -> int:
        with self._lock:
            return self._regs[index]

    def set_registers(self, start: int, values):
        with self._lock:
            for i, v in enumerate(values):
                self._regs[start + i] = int(v) & 0xFFFF

    def get_registers_snapshot(self):
        with self._lock:
            return list(self._regs)

    def start(self):
        """Start server in a background daemon thread."""
        self._running = True
        t = threading.Thread(target=self._serve, daemon=True, name="modbus-tcp")
        t.start()
        log.info("Modbus TCP server listening on %s:%d", self._host, self._port)

    def stop(self):
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

    # ── Internal ──────────────────────────────────────────────────────────────
    def _serve(self):
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server_sock.bind((self._host, self._port))
        except PermissionError:
            # Port 502 requires root; fall back to 5020
            self._port = 5020
            self._server_sock.bind((self._host, self._port))
            log.warning("Port 502 requires root — bound to port 5020 instead")
        self._server_sock.listen(5)
        self._server_sock.settimeout(1.0)

        while self._running:
            try:
                conn, addr = self._server_sock.accept()
                log.debug("Modbus client connected: %s", addr)
                t = threading.Thread(
                    target=self._handle_client,
                    args=(conn, addr),
                    daemon=True,
                    name=f"modbus-client-{addr[0]}",
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, conn, addr):
        conn.settimeout(30.0)
        try:
            while self._running:
                try:
                    header = self._recv_exact(conn, 6)
                except (ConnectionResetError, TimeoutError, OSError):
                    break
                if not header:
                    break

                trans_id = struct.unpack(">H", header[0:2])[0]
                # proto_id = header[2:4]  # always 0x0000
                length = struct.unpack(">H", header[4:6])[0]

                payload = self._recv_exact(conn, length)
                if not payload:
                    break

                unit_id = payload[0]
                fc = payload[1]
                data = payload[2:]

                response_pdu = self._process(fc, data)
                if response_pdu is None:
                    continue

                # Build response MBAP header
                resp_len = len(response_pdu) + 1  # +1 for unit_id byte per Modbus TCP spec
                mbap = struct.pack(">HHHB", trans_id, 0, resp_len, unit_id)
                conn.sendall(mbap + response_pdu)
        finally:
            conn.close()
            log.debug("Modbus client disconnected: %s", addr)

    def _recv_exact(self, conn, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return b""
            buf += chunk
        return buf

    def _process(self, fc: int, data: bytes) -> bytes:
        if fc == 0x03:  # Read Holding Registers
            return self._fc03(data)
        elif fc == 0x06:  # Write Single Register
            return self._fc06(data)
        elif fc == 0x10:  # Write Multiple Registers
            return self._fc16(data)
        else:
            # Exception response: illegal function
            return bytes([fc | 0x80, 0x01])

    def _fc03(self, data: bytes) -> bytes:
        start_addr, qty = struct.unpack(">HH", data[:4])
        regs = self.get_registers_snapshot()
        count = min(qty, len(regs) - start_addr)
        byte_count = count * 2
        values = regs[start_addr: start_addr + count]
        packed = struct.pack(f">{count}H", *values)
        return bytes([0x03, byte_count]) + packed

    def _fc06(self, data: bytes) -> bytes:
        addr, value = struct.unpack(">HH", data[:4])
        self.set_register(addr, value)
        return bytes([0x06]) + data[:4]

    def _fc16(self, data: bytes) -> bytes:
        start_addr, qty = struct.unpack(">HH", data[:4])
        byte_count = data[4]
        values = struct.unpack(f">{qty}H", data[5: 5 + byte_count])
        self.set_registers(start_addr, values)
        return bytes([0x10]) + data[:4]

    @property
    def port(self) -> int:
        return self._port
