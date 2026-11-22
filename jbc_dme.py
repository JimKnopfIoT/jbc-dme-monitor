#!/usr/bin/env python3
"""JBC DME-2A ueber USB-B auslesen - nur lesend.

Protokoll abgeleitet aus JBC_Connect.dll (JBC Stations Updater, frei
herunterladbar) und am Geraet verifiziert (DME_TCH_04, SW 8886937).

Physisch: STM32 Virtual ComPort, USB 0483:5740, /dev/ttyACM*.
Rahmen (Protocol_02):
    DLE STX | src dst FID cmd len data.. BCC | DLE ETX
    0x10 in den Daten wird verdoppelt. BCC = XOR ueber STX..ETX ohne
    Stuffing. Antworten der Station: src | 0x80.
Verbindung:
    Station sendet zyklisch HS (cmd 0, FID 253, dst = PC-Adresse).
    PC quittiert jeden HS mit Daten [0x06], src = pc | 0x80.
    Danach Anfragen mit FID 1..239.

Diese Bibliothek sendet ausschliesslich die Kommandos in READ_ONLY_COMMANDS.
Alles andere wird verweigert, damit die Station nicht veraendert wird.
"""
import glob
import os
import termios
import time

DLE, STX, ETX = 0x10, 0x02, 0x03

CMD_HS = 0
CMD_FIRMWARE = 33
CMD_INF_PORT = 48
CMD_R_LEVELSTEMPS = 51
CMD_R_SELECTTEMP = 80
CMD_R_TIPTEMP = 82
CMD_R_USB_CONNECTSTATUS = 224

READ_ONLY_COMMANDS = {
    CMD_HS, CMD_FIRMWARE, CMD_INF_PORT, CMD_R_LEVELSTEMPS,
    CMD_R_SELECTTEMP, CMD_R_TIPTEMP, CMD_R_USB_CONNECTSTATUS,
}

TOOLS = {
    0: "", 1: "T210", 2: "T245", 3: "PA", 4: "HT", 5: "DS", 6: "DR",
    7: "NT105", 8: "NP105", 9: "T470",
    10: "DT530",   # nicht in JBC_Connect.dll, am Geraet bestimmt (2026-11-22)
}

# Statusbits aus M_INF_PORT [10]
ST_STAND = 0x01
ST_SLEEP = 0x02
ST_HIBER = 0x04
ST_EXTR = 0x08
ST_DESOLD = 0x10

USB_VID_PID = "0483:5740"


def find_port():
    """Station suchen: zuerst by-id (STM32 VCP), sonst erstes ttyACM."""
    for p in sorted(glob.glob("/dev/serial/by-id/*STMicroelectronics*Virtual*")):
        return os.path.realpath(p)
    acm = sorted(glob.glob("/dev/ttyACM*"))
    return acm[0] if acm else None


def _bcc(data):
    x = 0
    for b in data:
        x ^= b
    return x


def encode(src, dst, fid, cmd, data=b""):
    raw = bytearray([STX, src, dst, fid, cmd, len(data)]) + bytearray(data) + b"\x00\x03"
    raw[-2] = _bcc(raw)
    out = bytearray([DLE, raw[0]])
    for b in raw[1:-1]:
        if b == DLE:
            out.append(DLE)
        out.append(b)
    out += bytes([DLE, raw[-1]])
    return bytes(out)


class Decoder:
    def __init__(self):
        self.state = 0
        self.buf = bytearray()

    def feed(self, chunk):
        frames = []
        for b in chunk:
            if self.state == 0:
                if b == DLE:
                    self.state = 1
            elif self.state == 1:
                if b == STX:
                    self.buf = bytearray([b])
                    self.state = 2
                elif b != DLE:
                    self.state = 0
            elif self.state == 2:
                if b == DLE:
                    self.state = 3
                else:
                    self.buf.append(b)
            elif self.state == 3:
                if b == DLE:
                    self.buf.append(b)
                    self.state = 2
                elif b == ETX:
                    self.buf.append(b)
                    raw = bytes(self.buf)
                    if len(raw) >= 8 and len(raw) == 8 + raw[5] and _bcc(raw) == 0:
                        frames.append({
                            "src": raw[1] & 0x7F, "resp": bool(raw[1] & 0x80),
                            "dst": raw[2] & 0x7F, "fid": raw[3], "cmd": raw[4],
                            "data": raw[6:6 + raw[5]],
                        })
                    self.state = 0
                elif b == STX:
                    self.buf = bytearray([b])
                    self.state = 2
                else:
                    self.state = 0
        return frames


def _le(b):
    return int.from_bytes(b, "little")


def _be(b):
    return int.from_bytes(b, "big")


class StationError(Exception):
    pass


class DME:
    """Verbindung zu einer DME-2A. Nicht thread-safe: aus einem Thread benutzen."""

    def __init__(self, path=None):
        self.path = path or find_port()
        self.fd = None
        self.dec = Decoder()
        self.st = self.pc = None
        self.fid = 0
        self.info = {}
        self._tool = [0, 0, 0, 0]
        self._levels = [None] * 4
        self._levels_t = [0.0] * 4

    # -- Low level -------------------------------------------------------
    def open(self):
        if not self.path:
            raise StationError("keine Station gefunden")
        fd = os.open(self.path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        a = termios.tcgetattr(fd)
        a[0] = a[1] = a[3] = 0
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        a[4] = a[5] = termios.B500000
        termios.tcsetattr(fd, termios.TCSANOW, a)
        termios.tcflush(fd, termios.TCIFLUSH)
        self.fd = fd

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        self.fd = None
        self.st = self.pc = None

    def _send(self, src, cmd, fid, data=b""):
        if cmd not in READ_ONLY_COMMANDS:
            raise StationError(f"Kommando {cmd} ist nicht freigegeben (nur lesen)")
        os.write(self.fd, encode(src, self.st, fid, cmd, data))

    def _read(self, timeout):
        end = time.monotonic() + timeout
        out = []
        while True:
            try:
                chunk = os.read(self.fd, 4096)
            except BlockingIOError:
                chunk = b""
            if chunk:
                for f in self.dec.feed(chunk):
                    if f["cmd"] == CMD_HS and f["fid"] == 253 and not f["resp"]:
                        if self.st is not None:
                            self._send(self.pc | 0x80, CMD_HS, 253, b"\x06")
                        else:
                            out.append(f)
                    else:
                        out.append(f)
                if out:
                    return out
            if time.monotonic() >= end:
                return out
            time.sleep(0.003)

    def request(self, cmd, data=b"", timeout=0.25):
        self.fid = self.fid % 239 + 1
        fid = self.fid
        self._send(self.pc, cmd, fid, data)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for f in self._read(end - time.monotonic()):
                if f["cmd"] == cmd and f["fid"] == fid:
                    return f["data"]
        return None

    # -- Verbindung ------------------------------------------------------
    def connect(self, timeout=2.0):
        self.open()
        end = time.monotonic() + timeout
        while time.monotonic() < end and self.st is None:
            for f in self._read(0.2):
                if f["cmd"] == CMD_HS and f["fid"] == 253 and f["src"] in (0x00, 0x10):
                    self.st, self.pc = f["src"], f["dst"]
                    self._send(self.pc | 0x80, CMD_HS, 253, b"\x06")
                    break
        if self.st is None:
            self.close()
            raise StationError("kein Handshake von der Station")
        fw = None
        end = time.monotonic() + 1.0
        self._send(self.pc, CMD_FIRMWARE, 237)
        while fw is None and time.monotonic() < end:
            for f in self._read(0.2):
                if f["cmd"] == CMD_FIRMWARE:
                    fw = f["data"].decode("utf-8", "replace")
        parts = (fw or "").split(":")
        self.info = {
            "protocol": parts[0] if parts else "",
            "model": parts[1] if len(parts) > 1 else "",
            "sw": parts[2] if len(parts) > 2 else "",
            "hw": parts[3] if len(parts) > 3 else "",
            "port": self.path,
        }
        return self.info

    # -- Daten -----------------------------------------------------------
    def read_port(self, p, levels_every=5.0):
        """Ein Port (0..3) als dict. None-Werte, wenn keine Antwort."""
        r = {"port": p + 1, "tool_id": 0, "tool": "", "error": 0, "status": 0,
             "state": "none", "temp": None, "set": None, "power": None,
             "levels": None, "level": None}
        inf = self.request(CMD_INF_PORT, bytes([p]))
        if inf and len(inf) >= 12:
            r["tool_id"] = inf[0]
            r["tool"] = TOOLS.get(inf[0], f"Tool {inf[0]}")
            r["error"] = inf[1]
            r["power"] = _be(inf[6:8]) / 10.0
            r["status"] = inf[10]
        tip = self.request(CMD_R_TIPTEMP, bytes([p]))
        if tip and len(tip) >= 2:
            r["temp"] = _le(tip[0:2]) / 9.0
        sel = self.request(CMD_R_SELECTTEMP, bytes([p]))
        if sel and len(sel) >= 2:
            r["set"] = _le(sel[0:2]) / 9.0

        now = time.monotonic()
        if r["tool_id"] and (r["tool_id"] != self._tool[p]
                             or now - self._levels_t[p] > levels_every):
            lv = self.request(CMD_R_LEVELSTEMPS, bytes([p, r["tool_id"]]))
            if lv and len(lv) >= 11:
                self._levels[p] = lv
                self._levels_t[p] = now
        self._tool[p] = r["tool_id"]
        lv = self._levels[p] if r["tool_id"] else None
        if lv:
            temps = [_le(lv[3 + 3 * i:5 + 3 * i]) / 9.0 for i in range(3)]
            on = [bool(lv[2 + 3 * i]) for i in range(3)]
            r["levels"] = [t if o else None for t, o in zip(temps, on)]
            if lv[0] and lv[1] < 3:
                r["level"] = lv[1]
                r["set"] = temps[lv[1]]

        st = r["status"]
        if not r["tool_id"]:
            r["state"] = "none"
        elif r["error"]:
            r["state"] = "error"
        elif st & ST_HIBER:
            r["state"] = "hiber"
        elif st & ST_SLEEP:
            r["state"] = "sleep"
        elif st & (ST_STAND | ST_EXTR):
            r["state"] = "stand"
        else:
            r["state"] = "work"
        return r

    def read_all(self):
        ports = [self.read_port(p) for p in range(4)]
        if all(p["temp"] is None and p["tool_id"] == 0 for p in ports):
            raise StationError("Station antwortet nicht")
        return ports


if __name__ == "__main__":
    import json
    import sys
    d = DME(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(d.connect()))
    try:
        for _ in range(int(sys.argv[2]) if len(sys.argv) > 2 else 3):
            print(json.dumps(d.read_all()))
            time.sleep(0.5)
    finally:
        d.close()
