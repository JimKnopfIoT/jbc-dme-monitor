#!/usr/bin/env python3
"""Read a JBC DME-2A over USB-B - read-only.

Protocol determined for interoperability from JBC's freely downloadable
"JBC Stations Updater" and verified on the station (DME_TCH_04, SW 8886937).
See PROTOCOL.md.

Physical: STM32 Virtual ComPort, USB 0483:5740, /dev/ttyACM*.
Frame (protocol 02):
    DLE STX | src dst FID cmd len data.. BCC | DLE ETX
    0x10 inside the frame is doubled. BCC = XOR over STX..ETX without
    stuffing. Station replies carry src | 0x80.
Connection:
    The station sends a handshake periodically (cmd 0, FID 253, dst = PC address).
    The PC acknowledges every handshake with data [0x06], src = pc | 0x80.
    Requests then use FID 1..239.

By default this library only sends the commands in READ_ONLY_COMMANDS and
refuses everything else, so the station is never changed. With
DME(allow_write=True) it additionally sends M_W_LEVELSTEMPS (52), and only for
the temperature levels (set_level_temp, select_level). The DME-2A answers
52 with NACK in monitor mode, so with control=True every write is wrapped like
JBC's own software does it: 225 ":C", 52, 225 ":M", followed by a reconnect
(only from the ":N" state of a fresh connection does the station accept ":C").
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
CMD_R_MAXTEMP = 162
CMD_R_MINTEMP = 164
CMD_R_USB_CONNECTSTATUS = 224
CMD_W_LEVELSTEMPS = 52
CMD_W_USB_CONNECTSTATUS = 225
CMD_ACK = 6
CMD_NACK = 21

READ_ONLY_COMMANDS = {
    CMD_HS, CMD_FIRMWARE, CMD_INF_PORT, CMD_R_LEVELSTEMPS,
    CMD_R_SELECTTEMP, CMD_R_TIPTEMP, CMD_R_MAXTEMP, CMD_R_MINTEMP,
    CMD_R_USB_CONNECTSTATUS,
}
WRITE_COMMANDS = {CMD_W_LEVELSTEMPS}

# absolute limits of JBC's software (CTemperature.IsValid: 810..4500 = 90..500 °C)
TEMP_ABS_MIN = 90
TEMP_ABS_MAX = 500

TOOLS = {
    0: "", 1: "T210", 2: "T245", 3: "PA", 4: "HT", 5: "DS", 6: "DR",
    7: "NT105", 8: "NP105", 9: "T470",
    10: "DT530",   # not in JBC's tool table, identified on the station
}

# status bits in M_INF_PORT byte 10
ST_STAND = 0x01
ST_SLEEP = 0x02
ST_HIBER = 0x04
ST_EXTR = 0x08
ST_DESOLD = 0x10

USB_VID_PID = "0483:5740"


def find_port():
    """Find the station: by-id link of the STM32 VCP first, else the first ttyACM."""
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
    """Connection to a DME-2A. Not thread-safe: use it from one thread."""

    def __init__(self, path=None, allow_write=False, control=False):
        self.path = path or find_port()
        self.allow_write = allow_write
        self.control = control and allow_write
        self.limits = (TEMP_ABS_MIN, TEMP_ABS_MAX)
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
            raise StationError("no station found")
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
        ok = cmd in READ_ONLY_COMMANDS or (self.allow_write and (
            cmd in WRITE_COMMANDS or (self.control and cmd == CMD_W_USB_CONNECTSTATUS)))
        if not ok:
            raise StationError(f"command {cmd} is not allowed (read-only)")
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
        r = self.transact(cmd, data, timeout)
        return r[1] if r and r[0] == cmd else None

    def transact(self, cmd, data=b"", timeout=0.25):
        """Send a request; return (reply cmd, data) or None. Reply cmd is
        cmd itself, CMD_ACK or CMD_NACK."""
        self.fid = self.fid % 239 + 1
        fid = self.fid
        self._send(self.pc, cmd, fid, data)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for f in self._read(end - time.monotonic()):
                if f["fid"] == fid and f["cmd"] in (cmd, CMD_ACK, CMD_NACK):
                    data = bytes(f["data"])
                    # the DME-2A acknowledges writes with the same cmd and data
                    # [0x06] (ACK) or [0x15] (NACK) instead of a cmd 6/21 frame
                    if cmd not in READ_ONLY_COMMANDS and f["cmd"] == cmd and len(data) == 1:
                        if data[0] == CMD_ACK:
                            return CMD_ACK, b""
                        if data[0] == CMD_NACK:
                            return CMD_NACK, b""
                    return f["cmd"], data
        return None

    # -- Connection ------------------------------------------------------
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
            raise StationError("no handshake from the station")
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
        if self.allow_write:
            lo = self.request(CMD_R_MINTEMP)
            hi = self.request(CMD_R_MAXTEMP)
            lo = round(_le(lo[0:2]) / 9) if lo and len(lo) >= 2 else TEMP_ABS_MIN
            hi = round(_le(hi[0:2]) / 9) if hi and len(hi) >= 2 else TEMP_ABS_MAX
            self.limits = (max(lo, TEMP_ABS_MIN), min(hi, TEMP_ABS_MAX))
        self.info["min_temp"], self.info["max_temp"] = self.limits
        if self.allow_write:
            mode = self.request(CMD_R_USB_CONNECTSTATUS)
            self.info["usb_mode"] = bytes(mode).decode("ascii", "replace") if mode else ""
        return self.info

    # -- Data ------------------------------------------------------------
    def read_port(self, p, levels_every=5.0):
        """One port (0..3) as a dict. Values are None if there was no reply."""
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
            r["levels_on"] = bool(lv[0])
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

    # -- Writing (only with allow_write=True) -----------------------------
    def _levels_now(self, p):
        """Fresh M_R_LEVELSTEMPS reply of port p (0..3) and its tool id."""
        inf = self.request(CMD_INF_PORT, bytes([p]))
        if not inf or not inf[0]:
            raise StationError(f"no tool on port {p + 1}")
        lv = self.request(CMD_R_LEVELSTEMPS, bytes([p, inf[0]]))
        if not lv or len(lv) < 11:
            raise StationError(f"port {p + 1}: levels not readable")
        return bytearray(lv[:11]), inf[0]

    def _set_mode(self, mode):
        """225 M_W_USB_CONNECTSTATUS: b":C" = control, b":M" = monitor. True on ACK."""
        r = self.transact(CMD_W_USB_CONNECTSTATUS, mode, timeout=0.6)
        return bool(r and r[0] == CMD_ACK)

    def _reconnect(self):
        """Close and handshake again. Right after closing the station needs a
        moment before it offers a new handshake."""
        limits = self.limits
        self.close()
        for i in range(3):
            time.sleep(0.5)
            try:
                self.connect(timeout=3.0)
                break
            except StationError:
                if i == 2:
                    raise
        self.limits = limits

    def _write_levels(self, p, tool, lv):
        """Write like JBC's own software: control mode, write, back to monitor mode
        right away, so the station is in control mode only for this one command."""
        payload = bytes(lv[:11]) + bytes([p, tool])
        if self.control and not self._set_mode(b":C"):
            raise StationError(f"port {p + 1}: control mode refused")
        try:
            r = self.transact(CMD_W_LEVELSTEMPS, payload, timeout=0.6)
        finally:
            if self.control:
                # Leave control mode. The station only accepts ":C" again from the
                # state ":N" it reports after a fresh handshake (":M" -> ":C" is
                # refused with error 5), so reconnect to get back to ":N".
                self._set_mode(b":M")
                self._reconnect()
        back = self.request(CMD_R_LEVELSTEMPS, bytes([p, tool]))
        if back and bytes(back[:11]) == bytes(lv[:11]):
            self._levels[p], self._levels_t[p] = back, time.monotonic()
            return True
        what = "no reply" if r is None else ("NACK" if r[0] == CMD_NACK else "not applied")
        raise StationError(f"port {p + 1}: write refused ({what})")

    def set_level_temp(self, p, level, celsius):
        """Set temperature of level 0..2 on port 0..3. Returns the value set."""
        if not self.allow_write:
            raise StationError("read-only connection")
        if level not in (0, 1, 2):
            raise ValueError("level must be 0..2")
        c = int(round(celsius))
        lo, hi = self.limits
        if not lo <= c <= hi:
            raise StationError(f"{c} °C outside {lo}…{hi} °C")
        lv, tool = self._levels_now(p)
        if not lv[2 + 3 * level]:
            raise StationError(f"level {level + 1} is disabled")
        lv[3 + 3 * level:5 + 3 * level] = (c * 9).to_bytes(2, "little")
        self._write_levels(p, tool, lv)
        return c

    def select_level(self, p, level):
        """Make level 0..2 the active level of port 0..3 (levels get switched on)."""
        if not self.allow_write:
            raise StationError("read-only connection")
        if level not in (0, 1, 2):
            raise ValueError("level must be 0..2")
        lv, tool = self._levels_now(p)
        if not lv[2 + 3 * level]:
            raise StationError(f"level {level + 1} is disabled")
        lv[0], lv[1] = 1, level
        self._write_levels(p, tool, lv)

    def read_all(self):
        ports = [self.read_port(p) for p in range(4)]
        if all(p["temp"] is None and p["tool_id"] == 0 for p in ports):
            raise StationError("station does not respond")
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
