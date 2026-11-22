# JBC DME-2A — USB-Protokoll (lesender Teil)

Beschreibung der USB-Schnittstelle der JBC DME-2A, soweit sie zum **Auslesen** der
Station nötig ist. Am Gerät verifiziert mit `DME_TCH_04`, Software `8886937`,
Hardware `0012408C`.

Die Kommandonummern und Feldformate wurden für die Interoperabilität aus JBCs frei
herunterladbarem „JBC Stations Updater“ ermittelt und an der Station nachgemessen.
Dieses Repository enthält keinen Code und keine Dateien von JBC.

## Physikalische Schicht

- Buchse **USB-B** hinten an der Station.
- Die Station meldet sich als **STM32 Virtual ComPort**, USB `0483:5740`, CDC-ACM.
  Unter Linux ist das `/dev/ttyACM*`, es braucht keinen Treiber.
- Baudrate ist bei CDC egal. JBCs PC-Software setzt 500000 8N1.
- Achtung: `0483:5740` ist die Standardkennung für STM32-CDC-Geräte. Andere Geräte
  können sich genauso melden. Eindeutig ist erst die Antwort auf `M_FIRMWARE`.
- Hinweis: Die RJ12-Buchse daneben ist der **Roboter-Anschluss** (RS232, ASCII-Protokoll,
  von JBC dokumentiert). Im Robotermodus ist die Station an der Front komplett
  gesperrt, für reines Mitlesen ist er also ungeeignet.

## Rahmen (Protokoll 02)

```
DLE STX | SRC DST FID CMD LEN DATA[LEN] BCC | DLE ETX
0x10 0x02                                    0x10 0x03
```

| Feld | Bedeutung |
|---|---|
| `SRC` | Absenderadresse. Bei Antworten ist Bit 7 gesetzt (`SRC | 0x80`). |
| `DST` | Zieladresse |
| `FID` | Frame-ID. Anfragen fortlaufend 1…239; Handshake 253, Firmware-Abfrage 237. Die Antwort trägt dieselbe FID. |
| `CMD` | Kommando |
| `LEN` | Anzahl Datenbytes |
| `BCC` | XOR über alle Bytes von `STX` bis `ETX` (ohne Stuffing), mit `BCC = 0` gerechnet. Ein gültiger Rahmen ergibt XOR 0. |

**Stuffing:** Ein `0x10` innerhalb von `SRC…BCC` wird als `0x10 0x10` gesendet.
`DLE STX` und `DLE ETX` selbst werden nicht verdoppelt.

## Verbindungsaufbau

1. Die Station sendet von sich aus etwa 15× pro Sekunde einen **Handshake**:
   `CMD 0`, `FID 253`, `SRC` = Stationsadresse (hier `0x10`), `DST` = die Adresse,
   die sie dem PC zuteilt (hier `0x1d`), ein Datenbyte.
   Beispiel auf der Leitung: `10 02 10 10 1d fd 00 01 1d ed 10 03`.
2. Der PC quittiert mit `CMD 0`, `FID 253`, Daten `06` (ACK) und `SRC = PC | 0x80`.
3. Der PC fragt die Kennung ab: `CMD 33` (`M_FIRMWARE`), `FID 237`, ohne Daten.
   Antwort als ASCII: `"02:DME_TCH_04:8886937:0012408C"` = Protokoll, Modell, SW, HW.
4. Danach weiter Anfragen mit FID 1…239. **Jeden weiteren Handshake der Station
   quittiert der PC wie in Schritt 2**, sonst baut sie die Verbindung ab.

Ein Wechsel in einen Steuer- oder Monitormodus (`CMD 225` mit `":M"`/`":C"`) ist
zum Lesen **nicht nötig**. Ohne ihn meldet `CMD 224` den Status `":N"`, die Station
beantwortet die Lesekommandos trotzdem und bleibt an der Front bedienbar.

## Lesekommandos

Ports werden 0…3 adressiert (Port 1…4 an der Station). Temperaturen kommen in einer
internen Einheit: **Wert ÷ 9 = °C**.

| CMD | Name | Anfrage | Antwort |
|---|---|---|---|
| 33 | `M_FIRMWARE` | – | ASCII `Protokoll:Modell:SW:HW` |
| 48 | `M_INF_PORT` | `[port]` | 12 oder 14 Byte, siehe unten |
| 51 | `M_R_LEVELSTEMPS` | `[port, tool]` | 13 Byte, siehe unten |
| 80 | `M_R_SELECTTEMP` | `[port]` | `[T lo, T hi, port]`, uint16 **LE** ÷ 9 = Grund-Solltemperatur |
| 82 | `M_R_TIPTEMP` | `[port]` | 5 Byte: `[0..1]` uint16 **LE** ÷ 9 = **Ist-Temperatur der Spitze**, `[4]` Port |
| 224 | `M_R_USB_CONNECTSTATUS` | – | ASCII, z. B. `":N"` |

### `M_INF_PORT` (48)

| Byte | Inhalt |
|---|---|
| 0 | Tool-Nummer (siehe unten), 0 = kein Tool |
| 1 | Fehler, 0 = ok |
| 2–3 | enthält auf der DME-2A **nicht** die Ist-Temperatur (stets gleich dem Grund-Sollwert, Byte-Reihenfolge vertauscht). Ist-Temperatur über `82` lesen. |
| 6–7 | Leistung in ‰, uint16 **Big-Endian** |
| 10 | Zustandsbits: `0x01` Ablage, `0x02` Sleep, `0x04` Hibernation, `0x08` Extractor/Ablage, `0x10` Entlöten |
| 11 | nur bei 14 Byte: Änderungsflags |
| letztes | Port |

Ablauf beim Zurücklegen eines Tools: `0x00` (arbeiten) → `0x01` (Ablage, Verzögerung)
→ `0x02` (Sleep) → `0x04` (Hibernation).

### `M_R_LEVELSTEMPS` (51)

| Byte | Inhalt |
|---|---|
| 0 | Stufen ein (1) / aus (0) |
| 1 | aktive Stufe 0…2, `255` = keine |
| 2, 5, 8 | Stufe 1/2/3 ein/aus |
| 3–4, 6–7, 9–10 | Temperatur der Stufe 1/2/3, uint16 LE ÷ 9 |

**Effektiver Sollwert:** Sind Stufen aktiv, gilt die Temperatur der aktiven Stufe,
sonst der Wert aus `80`. Stationen mit vorgewählten Stufen melden in `80` sonst immer
nur den Grundwert.

### Tool-Nummern

| Nr. | Tool |
|---|---|
| 1 | T210 |
| 2 | T245 |
| 3 | PA (Pinzette) |
| 4 | HT |
| 5 | DS |
| 6 | DR |
| 7 | NT105 |
| 8 | NP105 |
| 9 | T470 |
| 10 | DT530 (am Gerät bestimmt) |

## Schreibende Kommandos

Es gibt sie (Solltemperatur, Stufen, Sleep-Zeiten, Sperren, Firmware-Update …).
Dieses Projekt verwendet bewusst **keine** davon. `jbc_dme.py` lässt nur die oben
gelisteten Kommandos und den Handshake zu und verweigert alles andere.
