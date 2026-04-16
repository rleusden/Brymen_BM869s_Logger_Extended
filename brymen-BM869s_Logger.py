import sys
import os
import hid
import time
from pathlib import Path
import msvcrt
from datetime import datetime
from collections import deque
import threading
import re
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.animation as animation

if not hasattr(hid, 'Device'):
    class _HidDevice(hid.device):
        def __init__(self, vendor_id=0, product_id=0, path=None):
            super().__init__()
            if path:
                self.open_path(path)
            else:
                self.open(vendor_id, product_id)
        @property
        def manufacturer(self):
            return self.get_manufacturer_string()
        @property
        def product(self):
            return self.get_product_string()
        @property
        def serial(self):
            return self.get_serial_number_string()
        def read(self, size, timeout_ms=0):
            return bytes(super().read(size, timeout_ms))  # list -> bytes
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()
    hid.Device = _HidDevice

def key():
   x = msvcrt.kbhit()
   if x:
      ret = ord(msvcrt.getch())
   else:
      ret = 0
   return ret


def rename_log(fname, depth):
    fbak = fname + ".bak"
    if Path(fbak).exists():
        depth -= 1
        if depth == 0:
            os.remove(fbak)
        else:
            rename_log(fbak, depth)
    if Path(fname).exists():
        os.rename(fname, fbak)


def init_decode():
    digits = []
    for i in range(0, 256):
        digits.append(0)
    digits[0b10111110] = "0"
    digits[0b10100000] = "1"
    digits[0b11011010] = "2"
    digits[0b11111000] = "3"
    digits[0b11100100] = "4"
    digits[0b01111100] = "5"
    digits[0b01111110] = "6"
    digits[0b10101000] = "7"
    digits[0b11111110] = "8"
    digits[0b11111100] = "9"
    digits[0b00000000] = " "
    digits[0b01000000] = "-"
    digits[0b01001110] = "F"
    digits[0b00011110] = "C"
    digits[0b00010110] = "L"
    digits[0b11110010] = "d"
    digits[0b00100000] = "i"
    digits[0b01110010] = "o"
    digits[0b01011110] = "E"
    digits[0b01000010] = "r"
    digits[0b01100010] = "n"
    return digits
digits = init_decode()


# ---------------------------------------------------------------------------
# Live plot databuffer  (5 minuten schuivend venster)
# ---------------------------------------------------------------------------
PLOT_WINDOW_SEC = 300
plot_times  = deque()   # datetime objecten
plot_values = deque()   # float meetwaarden
plot_unit   = "V"
plot_lock   = threading.Lock()

def parse_value(measurement_str):
    """Haal numerieke waarde en eenheid op uit meetstring."""
    global plot_unit
    m = re.search(r'([-\s\d.]+)\s*([munpkMG]?[VAHz%RF][\w%]*)', measurement_str)
    if m:
        try:
            val = float(m.group(1).replace(' ', ''))
            plot_unit = m.group(2)
            return val
        except ValueError:
            pass
    return None

def add_plot_point(measurement_str):
    """Voeg meting toe aan plotbuffer, verwijder punten ouder dan 5 minuten."""
    val = parse_value(measurement_str)
    if val is None:
        return
    now = datetime.now()
    cutoff = now.timestamp() - PLOT_WINDOW_SEC
    with plot_lock:
        plot_times.append(now)
        plot_values.append(val)
        while plot_times and plot_times[0].timestamp() < cutoff:
            plot_times.popleft()
            plot_values.popleft()


# ---------------------------------------------------------------------------
# Brymen protocol decoder
# ---------------------------------------------------------------------------
label = [10000, 10000]

def brymen869_decode(device, reply):
    global label
    display1 = " "
    display2 = " "
    unit1 = ""
    unit2 = ""

    if len(reply.strip()) < 16:
        return ""

    for i in range(3, 9):
        if reply[i] & 1:
            if i != 3 and i != 8:
                display1 += "."
                display1 += digits[reply[i] - 1]
            else:
                display1 += digits[reply[i] - 1]
        else:
            display1 += digits[reply[i]]
    display1 = display1.rstrip()

    # remove glitches
    if len(display1) <= 3 or display1[3] == ' ' or display1[1] == ' ' or (display1[3] == '-' and display1[3] == '-'):
        if display1 != "  0.L":
            return None

    if (reply[2] >> 7) & 1:
        display1 = '-' + display1[1:]
    if (reply[9] >> 4) & 1:
        display1 = '-' + display1[1:]

    kind1 = ""
    if ((reply[2]) & 1) and ((reply[1] >> 4) & 1):
        kind1 = "DC+AC" + kind1
    elif (reply[1] >> 4) & 1:
        kind1 = "DC" + kind1
    elif (reply[2]) & 1:
        kind1 = "AC" + kind1
    elif ((reply[2] >> 1) & 1) and ((reply[2] >> 3) & 1):
        kind1 = "T1-T2" + kind1
    elif (reply[2] >> 1) & 1:
        kind1 = "T1" + kind1
    elif (reply[2] >> 3) & 1:
        kind1 = "T2" + kind1

    if (reply[15] >> 4) & 1:
        unit1 = "R"
    elif reply[15] & 1:
        unit1 = "Hz"
    elif (reply[15] >> 1) & 1:
        unit1 = "dBm"
    elif reply[8] & 1:
        unit1 = "V"
    elif (reply[14] >> 7) & 1:
        unit1 = "A"
    elif (reply[14] >> 5) & 1:
        unit1 = "F"
    elif (reply[14] >> 4) & 1:
        unit1 = "S"
    elif (reply[15] >> 7) & 1:
        unit1 = "D%"

    if (reply[15] >> 6) & 1:
        unit1 = "k" + unit1
    elif (reply[15] >> 5) & 1:
        unit1 = "M" + unit1
    elif (reply[15] >> 2) & 1 and not ((reply[15] >> 1) & 1):
        unit1 = "m" + unit1
    elif (reply[15] >> 3) & 1:
        unit1 = "u" + unit1
    elif (reply[14] >> 6) & 1:
        unit1 = "n" + unit1

    for i in range(10, 14):
        if i != 10 and (reply[i]) & 1:
            display2 += "."
            display2 += digits[reply[i] - 1]
        elif i == 10 and (reply[i] & 1):
            display2 += digits[reply[i] - 1]
        else:
            display2 += digits[reply[i]]
    display2 = display2.rstrip()
    if display2 == "diod":
        display2 = "diode"

    kind2 = ""
    if (reply[9] >> 5) & 1:
        kind2 = "AC" + kind2
    elif (reply[9] >> 6) & 1:
        kind2 = "T2" + kind2

    if (reply[14] >> 2) & 1:
        unit2 = "Hz"
    elif (reply[9] >> 2) & 1:
        unit2 = "A"
    elif (reply[14] >> 3) & 1:
        unit2 = "V"
    elif (reply[9] >> 3) & 1:
        unit2 = "%4-20mA"

    if reply[14] & 1:
        unit2 = "M" + unit2
    elif (reply[14] >> 1) & 1:
        unit2 = "k" + unit2
    elif reply[9] & 1:
        unit2 = "u" + unit2
    elif reply[9] >> 1 & 1:
        unit2 = "m" + unit2

    label[device] += 1
    if len(display2.strip()) < 2:
        return f"{label[device]-1}: {display1}{unit1}-{kind1}"
    return f"{device}:{label[device]-1}: {display1}{unit1} {kind1}, {display2}{unit2} {kind2}"


# ---------------------------------------------------------------------------
# HID
# ---------------------------------------------------------------------------
TIMER_INTERVAL_MS = 100
VID = 0x0820
PID = 0x0001
device_list = hid.enumerate(VID, PID)

dmm = [None, None]
response = ["", ""]

def hid_open(device):
    global dmm, response
    if len(device_list) > device:
        dmm[device] = hid.Device(VID, PID, path=device_list[device]["path"])
        print(f'[{device}]: {dmm[device].manufacturer} {dmm[device].product}')
    else:
        print(f"[{device}]: not found")


# ---------------------------------------------------------------------------
# Meetlus — draait in een aparte thread
# ---------------------------------------------------------------------------
stop_event = threading.Event()

def measure_loop(flog):
    global response
    rename_log(flog, 4)
    log = open(flog, 'a')

    hid_open(0)
    hid_open(1)
    time.sleep(0.500)

    rd0 = b""
    rd1 = b""
    while not stop_event.is_set():
        if key() != 0:
            stop_event.set()
            break

        if rd0 == b"" and dmm[0]:
            dmm[0].write(b"\x00\x00\x86\x66")
            measurement0 = brymen869_decode(0, response[0])
            if measurement0:
                log.write(measurement0 + "\n")
                log.flush()
                print(measurement0)
                add_plot_point(measurement0)    # <-- naar grafiek
            response[0] = b""

        if rd1 == b"" and dmm[1]:
            dmm[1].write(b"\x00\x00\x86\x66")
            measurement1 = brymen869_decode(1, response[1])
            if measurement1:
                log.write(measurement1 + "\n")
                log.flush()
                print(measurement1)
            response[1] = b""

        if dmm[0]:
            rd0 = dmm[0].read(64, 100)
            response[0] += rd0
        if dmm[1]:
            rd1 = dmm[1].read(64, 100)
            response[1] += rd1

        time.sleep(0.05)

    log.close()


# ---------------------------------------------------------------------------
# Matplotlib live grafiek — draait in de main thread (vereiste op Windows)
# ---------------------------------------------------------------------------
def run_plot():
    fig, ax = plt.subplots(figsize=(11, 4))
    fig.canvas.manager.set_window_title("Brymen BM869s Logger")
    fig.patch.set_facecolor('#1e1e2e')
    ax.set_facecolor('#1e1e2e')
    ax.tick_params(colors='#cdd6f4', which='both')
    for spine in ax.spines.values():
        spine.set_color('#45475a')
    ax.set_title("Brymen BM869s  —  laatste 5 minuten", color='#cdd6f4', pad=10)
    ax.set_xlabel("Tijd", color='#cdd6f4')
    ax.set_ylabel(plot_unit, color='#cdd6f4')
    ax.grid(True, color='#313244', linewidth=0.5)

    line, = ax.plot([], [], color='#89b4fa', linewidth=1.5)
    latest_text = ax.text(
        0.01, 0.95, "", transform=ax.transAxes,
        color='#a6e3a1', fontsize=12, verticalalignment='top',
        fontfamily='monospace'
    )
    plt.tight_layout()

    def update(frame):
        with plot_lock:
            if len(plot_times) < 2:
                return line, latest_text
            xs = [mdates.date2num(t) for t in plot_times]
            ys = list(plot_values)
            unit = plot_unit
            latest = ys[-1]

        line.set_data(xs, ys)
        now_num = mdates.date2num(datetime.now())
        cutoff_num = now_num - PLOT_WINDOW_SEC / 86400
        ax.set_xlim(cutoff_num, now_num + 5 / 86400)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        fig.autofmt_xdate(rotation=30)
        ax.relim()
        ax.autoscale_view(scalex=False)
        ax.set_ylabel(unit, color='#cdd6f4')
        latest_text.set_text(f"Nu: {latest:.4f} {unit}")
        return line, latest_text

    ani = animation.FuncAnimation(
        fig, update, interval=500, blit=False, cache_frame_data=False
    )

    def on_close(event):
        stop_event.set()

    fig.canvas.mpl_connect('close_event', on_close)
    plt.show()


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
print("Brymen BM869s logger  —  druk een toets of sluit grafiekvenster om te stoppen")
logfile = datetime.now().strftime("brymen_%Y%m%d_%H%M%S.log")
print(f"Logbestand: {logfile}")

measure_thread = threading.Thread(target=measure_loop, args=(logfile,), daemon=True)
measure_thread.start()

run_plot()          # blokkeert totdat het venster gesloten wordt

stop_event.set()
measure_thread.join(timeout=2)

if dmm[0]:
    dmm[0].close()
if dmm[1]:
    dmm[1].close()
