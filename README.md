# Bowling Controller — Experimental Sensor-Board Emulator for Mac Center Starbowl Bowling

<img width="643" height="485" alt="image" src="https://github.com/user-attachments/assets/4131b503-bb4d-4a33-89c1-ddc437e4b14b" />

> **Summary:** BOL.EXE is an old DOS program for a bowling center. With My Brother, we disassembled the program to find how it talks to the pinsetter sensor board. Then we wrote a Python program that answers in the same way as the sensor board. This lets a person test and play BOL.EXE inside a virtual machine, without the real pinsetter hardware. 

## Background

This project is not a new, isolated activity. It is part of a community effort to preserve old bowling-center software.

- **The disk image** with the folder `BOLICHE` (and the file `BOL.EXE` inside it) was shared on Archive.org by **[@Tipitochen](https://www.youtube.com/@tipitochen)**. He obtained the terminals from the Mac Center bowling center. Mac Center is a Paysandú Shopping mall, in Uruguay. This means the software in this project ran on real hardware, at a real location.
- **The software on the Disk image** appears to be provided by a Brazilian company called KOPP. Today, according to their **[company website](https://kopp.com.br)** they do not provide bowling services nor maintenance for it

We extracted the files from a virtual machine that was built from this disk image. Then examined the configuration files (`BOLICHE.INI` and `GLINK.CFG`). After this, with a disassembled `BOL.EXE`, we found the real communication protocol (packet format, checksum, commands, and port speeds), and wrote the Python controller that emulates the sensor board.

## Purpose of this Project

`BOL.EXE` was the software for a bowling center computer. This computer was connected by a serial cable (COM1 and COM2) to the machine that sets the pins and reads which pins fall. Today, a person can run `BOL.EXE` in a virtual machine (VirtualBox). But without the physical sensor board, the program waits for a signal that does not arrive.

This project is a substitute for the sensor board. The Python controller listens to the virtual serial ports. It sends the correct byte sequences back to `BOL.EXE`, as if pins had fallen. This lets a person continue to test the old program, without the original hardware.

**This project is not related to gambling or money games.** It concerns ten-pin bowling equipment only.

## Project Status

The original documentation from the team is direct and clear about the current limits of the project. This README keeps the same approach.

- We reconstructed the communication protocol from the disassembled executable file. We did not guess the protocol.
- The project includes 12 automated tests. These tests check the protocol, the checksum, TCP data fragmentation, and the state machine for one throw. The tests do not need the virtual machine.
- The controller is a **partial** emulator of the protocol. It covers the parts that we could confirm from the code. we marked the remaining parts as open questions, and did not add invented behavior.

## Technical Description

### 1. Reverse Engineering of the Executable File

We analyzed `BOLICHE\BOL.EXE` (a 32-bit DOS/Watcom executable) with a disassembler. The analysis produced the following results:

- The packet format for the serial cable: each packet starts with byte `1B` and ends with byte `04`. Each packet includes a simple checksum, calculated from the sum of the bytes.
- The port settings for each serial port: COM1 uses 9600 baud, and COM2 uses 19200 baud. We took these values from the program instructions, not from the configuration files, because the configuration files did not match the real values.
- A table of known commands. For example, one command requests the current status, and another command loads the name of player 1.
- The method to encode, in the COM2 data, which pin (numbered 1 to 10) has fallen.

We recorded this analysis with exact file offsets. This allows any reader to verify each conclusion.

### 2. The Controller Application (Python and Tkinter)
<img width="640" height="480" alt="image" src="https://github.com/user-attachments/assets/1aebe459-c40f-4a89-8e70-358e8b087d58" />

The application uses Tkinter, which is part of the standard Python installation. The application does not need extra software packages. The application has these functions:

- It works as a **local TCP server**. It listens on `127.0.0.1:5000` for COM1, and on `127.0.0.1:5001` for COM2. VirtualBox connects to these two addresses, in place of the real serial cables.
- It shows a visual layout of 10 pins. The user can select which pins have fallen. The application also has quick-selection buttons: "5 pins", "all remaining pins", and "no pins".
- It sends a complete four-phase sequence for one throw: rest, start, read, and return. The application uses the same minimum timing values that the team observed in the original program.
- It saves a detailed log of all data sent and received. A user can send this log as evidence if a problem occurs.
- It includes an earlier, simpler version of the application (see `GUI_ANTERIOR.md`). This file documents the development history of the project.

### 3. Test Suite

The project includes 12 unit tests. A user can run the tests with one click (`PROBAR.cmd`). The tests do not need the virtual machine or the real game (It is available on Archive.org [Starbowl Paysandu](https://archive.org/details/starbowlpdu) . The tests check: packet construction and validation, all 1024 possible combinations of fallen pins, network reconnection, and one complete simulated throw cycle.

## File List

| File | Description |
|---|---|
| `ABRIR_CONTROLADOR.cmd` | Starts the application. Requires Python 3 with Tkinter. |
| `controlador.py` | The main window. Contains the pin and throw controls. |
| `bolos_gui.py` | The base graphical interface. Comes from the earlier version. |
| `servidor.py` | The TCP server. Acts as the virtual serial ports. |
| `protocolo.py` | Builds, checks, and calculates the checksum for each packet. |
| `tiradas.py` | Contains the logic for the pin state and the throw phase. |
| `placa_com2.py` | An automatic board responder. Runs from the command line, without the graphical interface. |
| `pruebas.py`, `pruebas_tiradas.py` | The 12 automated tests. |
| `PROBAR.cmd` | Runs the automated tests. |
| `NOTAS_TECNICAS_PREVIAS.md`, `EVIDENCIA_TIRADAS.md`, `evidencia_ensamblador.txt`, `evidencia_tiradas.txt` | The record of the reverse-engineering work, with file offsets and findings. |
| `VALIDACION.txt` | Lists the checks made before the team built the package. |
| `SHA256SUMS.txt` | Lists the checksum of each file. A user can use this to confirm that no file changed. |
| `GUI_ANTERIOR.md` | Documents the earlier version of the project. |

## Operation Instructions

1. Close any other server program that uses port 5000 or port 5001.
2. Turn off the virtual machine. Set COM1 and COM2 in VirtualBox as TCP clients. Point them to `127.0.0.1:5000` and `127.0.0.1:5001`.
3. Open `ABRIR_CONTROLADOR.cmd`. Press "Escuchar" (Listen) for each port.
4. Turn on the virtual machine. Start `BOL.EXE`.
5. From Central / COM1 tab, Start a game (Press `Iniciar DEMO Experimental`).
6. Once the display updates, change to `Tiradas / COM2 tab`
7. Select the pins that fall. Press "Enviar tirada" (Send Throw).
8. Wait about 4-10 seconds, then send another group or Press "Todos Restantes" (All Remaining)
9. for a new Round, click on "Nuevo Rack" (This steps is **Crucial**, we are telling the counter that the pins are now inline again)
<img width="640" height="360" alt="image" src="https://github.com/user-attachments/assets/0d028de6-4fa0-4e85-8ee1-cf520fc86f80" />
<img width="640" height="480" alt="image" src="https://github.com/user-attachments/assets/0185ed6d-e170-4b95-8e02-332fa4221589" />
<img width="640" height="480" alt="image" src="https://github.com/user-attachments/assets/89e35d92-7625-4bac-8dff-b8819e12cbab" />

For complete instructions and problem diagnosis, see `LEEME.md`.

## Project Limits

This section states clearly what the project does not do.

- The project is not a crack or a patch for the original executable file. It does not change game scores. It does not enable cheating.
- The project does not connect to the internet. All connections stay on the local computer, at address `127.0.0.1`.
- The project does not replace a physical sensor board in a working bowling center. It is a laboratory tool for the study of legacy software.

## Credits

- **[@Tipitochen](https://www.youtube.com/@tipitochen)** — obtained and published, on Archive.org, the original disk image from the Mac Center terminals (Paysandú Shopping, Uruguay).

---
