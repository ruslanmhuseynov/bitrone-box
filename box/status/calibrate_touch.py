#!/usr/bin/env python3
"""One-shot touchscreen calibration for a libinput-handled resistive panel.

Shows four targets near the corners, you tap each one, then it:
  1. computes the libinput "Calibration Matrix" (scale + offset per axis),
  2. applies it live so you can immediately check the aim,
  3. prints an /etc/X11/xorg.conf.d snippet to make it permanent.

Run on the monoblock INSIDE X (from an xterm):  python3 calibrate_touch.py
Tap the four green crosses with a fingernail/stylus (more precise on resistive).
Press Esc to cancel.

No extra packages: only python3-tk and the `xinput` CLI (already installed).
"""
import re
import subprocess
import sys
import tkinter as tk

# Targets as (x,y) fractions of the screen. Near corners, inset 10%.
TARGETS = [(0.10, 0.10), (0.90, 0.10), (0.90, 0.90), (0.10, 0.90)]

DEV_MATCH = "touchscreen"        # substring to find the device id in `xinput list`
PRODUCT_MATCH = "IDC 6681 Touchscreen"  # MatchProduct for the permanent snippet


def sh(*args):
    return subprocess.run(list(args), capture_output=True, text=True).stdout


def find_device():
    out = sh("xinput", "list")
    for line in out.splitlines():
        if DEV_MATCH in line.lower():
            m = re.search(r"id=(\d+)", line)
            if m:
                return m.group(1)
    sys.exit("Touchscreen not found in `xinput list` (is X running and the panel bound?).")


def set_matrix(dev_id, m):
    subprocess.run(["xinput", "set-prop", dev_id,
                    "libinput Calibration Matrix"] + ["%.6f" % v for v in m])


def fit(ins, outs):
    """Least-squares line out = a*in + c."""
    n = len(ins)
    si, so = sum(ins), sum(outs)
    sii = sum(i * i for i in ins)
    sio = sum(i * o for i, o in zip(ins, outs))
    den = n * sii - si * si
    a = (n * sio - si * so) / den
    c = (so - a * si) / n
    return a, c


def main():
    dev_id = find_device()
    # Reset to identity so each tap reports the raw (normalised) device position.
    set_matrix(dev_id, [1, 0, 0, 0, 1, 0, 0, 0, 1])

    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.config(cursor="none")
    W = root.winfo_screenwidth()
    H = root.winfo_screenheight()
    cv = tk.Canvas(root, bg="black", highlightthickness=0)
    cv.pack(fill="both", expand=True)

    taps = []
    idx = [0]

    def draw():
        cv.delete("all")
        rx, ry = TARGETS[idx[0]]
        x, y = rx * W, ry * H
        r = 22
        cv.create_line(x - r, y, x + r, y, fill="#39FF14", width=2)
        cv.create_line(x, y - r, x, y + r, fill="#39FF14", width=2)
        cv.create_oval(x - r, y - r, x + r, y + r, outline="#39FF14", width=2)
        cv.create_text(W / 2, H / 2, fill="#888888",
                       font=("DejaVu Sans", 22),
                       text="Tap the green cross  (%d/4)" % (idx[0] + 1))

    def on_tap(e):
        taps.append((e.x / W, e.y / H))
        idx[0] += 1
        if idx[0] >= len(TARGETS):
            root.quit()
        else:
            draw()

    cv.bind("<Button-1>", on_tap)
    root.bind("<Escape>", lambda e: sys.exit("Cancelled."))
    draw()
    root.mainloop()
    root.destroy()

    ax, cx = fit([p[0] for p in taps], [t[0] for t in TARGETS])
    ay, cy = fit([p[1] for p in taps], [t[1] for t in TARGETS])
    M = [ax, 0, cx, 0, ay, cy, 0, 0, 1]
    set_matrix(dev_id, M)
    mstr = " ".join("%.6f" % v for v in M)

    print("\nCalibration applied live. Touch around and check the aim.")
    print("Matrix: %s\n" % mstr)
    print("To make it permanent, create")
    print("  /etc/X11/xorg.conf.d/99-touch-calibration.conf")
    print("with:\n")
    print('Section "InputClass"')
    print('    Identifier   "IDEACO touch calibration"')
    print('    MatchProduct "%s"' % PRODUCT_MATCH)
    print('    Option "CalibrationMatrix" "%s"' % mstr)
    print('EndSection')


if __name__ == "__main__":
    main()
