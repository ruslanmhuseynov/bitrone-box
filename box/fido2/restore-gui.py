#!/usr/bin/env python3
"""Bitrone Box — тач-лаунчер восстановления на витрине.

Кнопка на сервер → подтверждение → запуск /opt/bitrone-box/restore.sh
(требует касания FIDO2-ключа) → прогресс-бар → ссылка для скачивания (3 часа).
Прогресс считается по размеру восстановленного (без обновления restic).
"""
import os
import subprocess
import threading
import tkinter as tk

REPO_ROOT = "/srv/restic"
RESTORE_ROOT = "/srv/restore"
RESTORE = "/opt/bitrone-box/restore.sh"

BG = "#0B1630"; CARD = "#111F3F"; TILE = "#22355F"; TRACK = "#1B2B4D"
TXT = "#FFFFFF"; MUTED = "#8CA0C6"; OK = "#3BA935"; ALERT = "#E5484D"; BUSY = "#3BA1E5"


def folder_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def servers():
    try:
        return sorted(d for d in os.listdir(REPO_ROOT)
                      if os.path.isfile(os.path.join(REPO_ROOT, d, "config")))
    except OSError:
        return []


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Bitrone — восстановление")
        self.root.configure(bg=BG)
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.menu()

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def menu(self):
        self.clear()
        tk.Label(self.root, text="Восстановление копии", font=("DejaVu Sans", 34, "bold"),
                 bg=BG, fg=TXT).pack(pady=(40, 6))
        tk.Label(self.root, text="Выберите сервер — восстановим последнюю копию",
                 font=("DejaVu Sans", 16), bg=BG, fg=MUTED).pack(pady=(0, 30))
        wrap = tk.Frame(self.root, bg=BG); wrap.pack(expand=True)
        srv = servers()
        if not srv:
            tk.Label(wrap, text="Копий пока нет", font=("DejaVu Sans", 20),
                     bg=BG, fg=MUTED).pack(pady=40)
        for s in srv:
            tk.Button(wrap, text=s, font=("DejaVu Sans", 22, "bold"), width=22, height=2,
                      bg=TILE, fg=TXT, activebackground=BUSY, activeforeground=TXT,
                      bd=0, highlightthickness=0,
                      command=lambda s=s: self.confirm(s)).pack(pady=8)
        tk.Button(self.root, text="Закрыть", font=("DejaVu Sans", 14), bg=CARD, fg=MUTED,
                  bd=0, highlightthickness=0, command=self.root.destroy).pack(side="bottom", pady=20)

    def confirm(self, server):
        self.clear()
        tk.Label(self.root, text=server, font=("DejaVu Sans", 30, "bold"),
                 bg=BG, fg=TXT).pack(pady=(80, 10))
        tk.Label(self.root, text="Восстановить ПОСЛЕДНЮЮ копию этого сервера?",
                 font=("DejaVu Sans", 18), bg=BG, fg=MUTED).pack(pady=10)
        row = tk.Frame(self.root, bg=BG); row.pack(pady=40)
        tk.Button(row, text="Да, восстановить", font=("DejaVu Sans", 20, "bold"), width=16, height=2,
                  bg=OK, fg=TXT, bd=0, highlightthickness=0,
                  command=lambda: self.keypad(server)).pack(side="left", padx=16)
        tk.Button(row, text="Отмена", font=("DejaVu Sans", 20), width=12, height=2,
                  bg=TILE, fg=TXT, bd=0, highlightthickness=0,
                  command=self.menu).pack(side="left", padx=16)

    def keypad(self, server):
        self.clear()
        self.pin = ""
        tk.Label(self.root, text="Введите PIN ключа Bitrone", font=("DejaVu Sans", 26, "bold"),
                 bg=BG, fg=TXT).pack(pady=(50, 6))
        self.pin_disp = tk.Label(self.root, text="", font=("DejaVu Sans", 34, "bold"),
                                 bg=BG, fg=BUSY)
        self.pin_disp.pack(pady=(0, 16))

        def redraw():
            self.pin_disp.config(text="●" * len(self.pin))

        def press(d):
            if len(self.pin) < 32:
                self.pin += d; redraw()

        def back():
            self.pin = self.pin[:-1]; redraw()

        grid = tk.Frame(self.root, bg=BG); grid.pack()
        keys = [("1", 0, 0), ("2", 0, 1), ("3", 0, 2), ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
                ("7", 2, 0), ("8", 2, 1), ("9", 2, 2), ("⌫", 3, 0), ("0", 3, 1), ("OK", 3, 2)]
        for (t, r, c) in keys:
            if t == "OK":
                cmd, bg = (lambda: self.run(server) if self.pin else None), OK
            elif t == "⌫":
                cmd, bg = back, TILE
            else:
                cmd, bg = (lambda d=t: press(d)), TILE
            tk.Button(grid, text=t, font=("DejaVu Sans", 24, "bold"), width=5, height=2,
                      bg=bg, fg=TXT, activebackground=BUSY, activeforeground=TXT,
                      bd=0, highlightthickness=0, command=cmd).grid(row=r, column=c, padx=8, pady=8)
        tk.Button(self.root, text="Отмена", font=("DejaVu Sans", 16), bg=CARD, fg=MUTED,
                  bd=0, highlightthickness=0, command=self.menu).pack(pady=18)

    def run(self, server):
        self.clear()
        self.server = server
        self.done = False; self.ok = False
        self.url = ""; self.lines = []

        tk.Label(self.root, text="Восстановление " + server, font=("DejaVu Sans", 28, "bold"),
                 bg=BG, fg=TXT).pack(pady=(90, 20))
        self.status = tk.Label(self.root, text="Приложите ключ Bitrone к коробке и коснитесь его",
                               font=("DejaVu Sans", 20), bg=BG, fg=BUSY)
        self.status.pack(pady=10)

        self.barw = int(self.root.winfo_screenwidth() * 0.6)
        self.bar = tk.Canvas(self.root, width=self.barw, height=28, bg=TRACK, highlightthickness=0)
        self.bar.pack(pady=24)
        self.fill = self.bar.create_rectangle(0, 0, 0, 28, fill=OK, width=0)
        self.pct_lbl = tk.Label(self.root, text="", font=("DejaVu Sans", 16), bg=BG, fg=MUTED)
        self.pct_lbl.pack()

        threading.Thread(target=self._worker, daemon=True).start()
        self._poll()

    def _worker(self):
        try:
            cmd = [RESTORE, self.server] if os.geteuid() == 0 else ["sudo", RESTORE, self.server]
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, bufsize=1)
            try:
                if getattr(self, "pin", ""):
                    p.stdin.write(self.pin + "\n"); p.stdin.flush()
                p.stdin.close()
            except Exception:
                pass
            self.pin = ""  # не держим PIN в памяти дольше нужного
            for line in p.stdout:
                line = line.strip()
                self.lines.append(line)
                if line.startswith("http://"):
                    self.url = line
            p.wait()
            self.ok = (p.returncode == 0)
        except Exception as e:
            self.lines.append(str(e)); self.ok = False
        self.done = True

    def _read_pct(self):
        try:
            with open("/run/bitrone-box/restore.pct") as f:
                return int(f.read().strip() or "-1")
        except (OSError, ValueError):
            return -1

    def _poll(self):
        if self.done:
            self._finish(); return
        pct = self._read_pct()
        if pct < 0:
            self.status.config(text="Приложите ключ Bitrone к коробке и коснитесь его")
        else:
            self.bar.coords(self.fill, 0, 0, int(self.barw * pct / 100), 28)
            self.status.config(text="Восстановление… (ключ принят)")
            self.pct_lbl.config(text="%d %%" % pct)
        self.root.after(700, self._poll)

    def _finish(self):
        self.bar.coords(self.fill, 0, 0, self.barw if self.ok else 0, 28)
        self.pct_lbl.config(text="100 %" if self.ok else "")
        self.status.config(text=("Готово" if self.ok else "Не удалось"),
                           fg=(OK if self.ok else ALERT))
        if self.ok and self.url:
            tk.Label(self.root, text="Скачать можно 3 часа по ссылке:", font=("DejaVu Sans", 16),
                     bg=BG, fg=MUTED).pack(pady=(26, 4))
            tk.Label(self.root, text=self.url, font=("DejaVu Sans Mono", 22, "bold"),
                     bg=BG, fg=TXT).pack()
        elif not self.ok:
            tk.Label(self.root, text="\n".join(self.lines[-5:]), font=("DejaVu Sans Mono", 12),
                     bg=BG, fg=MUTED, justify="left").pack(pady=12)
        tk.Button(self.root, text="В меню", font=("DejaVu Sans", 18, "bold"), width=14, height=2,
                  bg=TILE, fg=TXT, bd=0, highlightthickness=0, command=self.menu).pack(pady=30)

    def loop(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().loop()
