# JBC DME-2A — USB protocol (read part)

The USB interface of the JBC DME-2A, as far as needed to **read** the station.
Verified on `DME_TCH_04`, software `8886937`, hardware `0012408C`.

Command numbers and field formats were determined for interoperability from JBC's
freely downloadable "JBC Stations Updater" and checked against the station.
This repository contains no code or files from JBC.

## Physical layer

- **USB-B** socket at the back of the station.
- The station enumerates as **STM32 Virtual ComPort**, USB `0483:5740`, CDC-ACM.
  On Linux that is `/dev/ttyACM*`, no driver needed.
- The baud rate does not matter for CDC. JBC's PC software sets 500000 8N1.
- `0483:5740` is the generic ID of STM32 CDC devices; other devices may use it too.
  Only the reply to `M_FIRMWARE` identifies the station.
- The RJ12 socket next to it is the **robot port** (RS232, ASCII protocol documented
  by JBC). Robot mode locks the station's front panel completely, so it is not
  suitable for monitoring.

## Frame (protocol 02)

```
DLE STX | SRC DST FID CMD LEN DATA[LEN] BCC | DLE ETX
0x10 0x02                                    0x10 0x03
```

| Field | Meaning |
|---|---|
| `SRC` | Sender address. Replies have bit 7 set (`SRC | 0x80`). |
| `DST` | Destination address |
| `FID` | Frame ID. Requests count 1…239; handshake 253, firmware query 237. The reply carries the same FID. |
| `CMD` | Command |
| `LEN` | Number of data bytes |
| `BCC` | XOR over all bytes from `STX` to `ETX` (unstuffed), computed with `BCC = 0`. A valid frame XORs to 0. |

**Stuffing:** a `0x10` inside `SRC…BCC` is sent as `0x10 0x10`. `DLE STX` and
`DLE ETX` themselves are not doubled.

## Connection

1. The station sends a **handshake** about 15 times per second on its own:
   `CMD 0`, `FID 253`, `SRC` = station address (here `0x10`), `DST` = the address it
   assigns to the PC (here `0x1d`), one data byte.
   On the wire: `10 02 10 10 1d fd 00 01 1d ed 10 03`.
2. The PC acknowledges with `CMD 0`, `FID 253`, data `06` (ACK) and `SRC = PC | 0x80`.
3. The PC asks for the identification: `CMD 33` (`M_FIRMWARE`), `FID 237`, no data.
   ASCII reply: `"02:DME_TCH_04:8886937:0012408C"` = protocol, model, SW, HW.
4. Further requests use FID 1…239. **Every later handshake from the station is
   acknowledged as in step 2**, otherwise it drops the connection.

Switching to a control or monitor mode (`CMD 225` with `":M"`/`":C"`) is **not
needed** for reading. Without it, `CMD 224` reports `":N"`; the station still answers
the read commands and stays usable at its front panel.

## Read commands

Ports are addressed 0…3 (port 1…4 on the station). Temperatures use an internal
unit: **value ÷ 9 = °C**.

| CMD | Name | Request | Reply |
|---|---|---|---|
| 33 | `M_FIRMWARE` | – | ASCII `protocol:model:SW:HW` |
| 48 | `M_INF_PORT` | `[port]` | 12 or 14 bytes, see below |
| 51 | `M_R_LEVELSTEMPS` | `[port, tool]` | 13 bytes, see below |
| 80 | `M_R_SELECTTEMP` | `[port]` | `[T lo, T hi, port]`, uint16 **LE** ÷ 9 = base set temperature |
| 82 | `M_R_TIPTEMP` | `[port]` | 5 bytes: `[0..1]` uint16 **LE** ÷ 9 = **tip temperature**, `[4]` port |
| 224 | `M_R_USB_CONNECTSTATUS` | – | ASCII, e.g. `":N"` |

### `M_INF_PORT` (48)

| Byte | Content |
|---|---|
| 0 | Tool number (see below), 0 = no tool |
| 1 | Error, 0 = ok |
| 2–3 | On the DME-2A this is **not** the tip temperature (always the base set point, byte order swapped). Read the tip temperature with `82`. |
| 6–7 | Power in ‰, uint16 **big-endian** |
| 10 | State bits: `0x01` stand, `0x02` sleep, `0x04` hibernation, `0x08` extractor/stand, `0x10` desoldering |
| 11 | Only with 14 bytes: change flags |
| last | Port |

When a tool is put back: `0x00` (working) → `0x01` (stand, delay) → `0x02` (sleep)
→ `0x04` (hibernation).

### `M_R_LEVELSTEMPS` (51)

| Byte | Content |
|---|---|
| 0 | Levels on (1) / off (0) |
| 1 | Active level 0…2, `255` = none |
| 2, 5, 8 | Level 1/2/3 enabled |
| 3–4, 6–7, 9–10 | Temperature of level 1/2/3, uint16 LE ÷ 9 |

**Effective set point:** if levels are active, the temperature of the active level
applies, otherwise the value from `80`. With preset levels, `80` only ever reports
the base value.

### Tool numbers

| No. | Tool |
|---|---|
| 1 | T210 |
| 2 | T245 |
| 3 | PA (tweezers) |
| 4 | HT |
| 5 | DS |
| 6 | DR |
| 7 | NT105 |
| 8 | NP105 |
| 9 | T470 |
| 10 | DT530 (identified on the station) |

## Write commands

They exist (set temperature, levels, sleep times, locks, firmware update …).
This project deliberately uses **none** of them. `jbc_dme.py` only allows the commands
listed above plus the handshake and refuses everything else.
