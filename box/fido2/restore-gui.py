#!/usr/bin/env python3
"""Bitrone Box — тач-лаунчер восстановления на витрине (AZ / RU / EN).

Кнопка на сервер → подтверждение → PIN → запуск /opt/bitrone-box/restore.sh
(FIDO2: PIN + касание) → прогресс-бар → ссылка для скачивания (3 часа).
Язык берётся из LANG в /etc/bitrone-box/box.conf.
"""
import os
import subprocess
import threading
import tkinter as tk

REPO_ROOT = "/srv/restic"
RESTORE_ROOT = "/srv/restore"
RESTORE = "/opt/bitrone-box/restore.sh"
CONFIG = "/etc/bitrone-box/box.conf"

BG = "#0B1630"; CARD = "#111F3F"; TILE = "#22355F"; TRACK = "#1B2B4D"
TXT = "#FFFFFF"; MUTED = "#8CA0C6"; OK = "#3BA935"; ALERT = "#E5484D"; BUSY = "#3BA1E5"

STRINGS = {
    "az": {
        "title": "Nüsxənin bərpası", "pick": "Serveri seçin — son nüsxəni bərpa edək",
        "none": "Hələ nüsxə yoxdur", "close": "Bağla",
        "confirm_q": "Bu serverin SON nüsxəsini bərpa edək?",
        "yes": "Bəli, bərpa et", "cancel": "Ləğv et",
        "pin_title": "Bitrone açarının PIN-ini daxil edin",
        "touch": "Bitrone açarını qutuya yaxınlaşdırın və toxunun",
        "restoring": "Bərpa olunur… (açar qəbul edildi)",
        "done": "Hazırdır", "fail": "Alınmadı",
        "dl": "3 saat ərzində linklə yükləmək olar:", "menu": "Menyuya",
        "restore_of": "Bərpa: %s",
    },
    "ru": {
        "title": "Восстановление копии", "pick": "Выберите сервер — восстановим последнюю копию",
        "none": "Копий пока нет", "close": "Закрыть",
        "confirm_q": "Восстановить ПОСЛЕДНЮЮ копию этого сервера?",
        "yes": "Да, восстановить", "cancel": "Отмена",
        "pin_title": "Введите PIN ключа Bitrone",
        "touch": "Приложите ключ Bitrone к коробке и коснитесь его",
        "restoring": "Восстановление… (ключ принят)",
        "done": "Готово", "fail": "Не удалось",
        "dl": "Скачать можно 3 часа по ссылке:", "menu": "В меню",
        "restore_of": "Восстановление %s",
    },
    "en": {
        "title": "Restore a backup", "pick": "Pick a server — we'll restore the latest copy",
        "none": "No backups yet", "close": "Close",
        "confirm_q": "Restore this server's LATEST copy?",
        "yes": "Yes, restore", "cancel": "Cancel",
        "pin_title": "Enter the Bitrone key PIN",
        "touch": "Insert the Bitrone key and touch it",
        "restoring": "Restoring… (key accepted)",
        "done": "Done", "fail": "Failed",
        "dl": "Download link (valid 3 hours):", "menu": "Menu",
        "restore_of": "Restoring %s",
    },
}


def load_lang():
    try:
        with open(CONFIG, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("LANG="):
                    v = line.split("=", 1)[1].strip()
                    if v in STRINGS:
                        return v
    except OSError:
        pass
    return "az"


def save_lang(code):
    try:
        with open(CONFIG, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        found = False
        for i, ln in enumerate(lines):
            if ln.strip().startswith("LANG="):
                lines[i] = "LANG=%s\n" % code; found = True
        if not found:
            lines.append("LANG=%s\n" % code)
        with open(CONFIG, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        pass  # нет прав (kiosk) — только на эту сессию


def servers():
    try:
        return sorted(d for d in os.listdir(REPO_ROOT)
                      if os.path.isfile(os.path.join(REPO_ROOT, d, "config")))
    except OSError:
        return []


class App:
    def __init__(self):
        self.L = STRINGS[load_lang()]
        self.root = tk.Tk()
        self.root.title("Bitrone")
        self.root.configure(bg=BG)
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.menu()

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def lang_bar(self):
        bar = tk.Frame(self.root, bg=BG)
        for code in ("az", "ru", "en"):
            active = (self.L is STRINGS[code])
            tk.Button(bar, text=code.upper(), font=("DejaVu Sans", 18, "bold"),
                      width=5, pady=6, bd=0, highlightthickness=0,
                      bg=(OK if active else TILE), fg=TXT,
                      activebackground=BUSY, activeforeground=TXT,
                      command=lambda c=code: self.set_lang(c)).pack(side="left", padx=5)
        bar.place(relx=0.985, rely=0.02, anchor="ne")

    def set_lang(self, code):
        if code in STRINGS:
            self.L = STRINGS[code]
            save_lang(code)
            self.menu()

    def menu(self):
        self.clear()
        L = self.L
        self.lang_bar()
        tk.Label(self.root, text=L["title"], font=("DejaVu Sans", 34, "bold"),
                 bg=BG, fg=TXT).pack(pady=(40, 6))
        tk.Label(self.root, text=L["pick"], font=("DejaVu Sans", 16),
                 bg=BG, fg=MUTED).pack(pady=(0, 30))
        wrap = tk.Frame(self.root, bg=BG); wrap.pack(expand=True)
        srv = servers()
        if not srv:
            tk.Label(wrap, text=L["none"], font=("DejaVu Sans", 20),
                     bg=BG, fg=MUTED).pack(pady=40)
        for s in srv:
            tk.Button(wrap, text=s, font=("DejaVu Sans", 22, "bold"), width=22, height=2,
                      bg=TILE, fg=TXT, activebackground=BUSY, activeforeground=TXT,
                      bd=0, highlightthickness=0,
                      command=lambda s=s: self.confirm(s)).pack(pady=8)
        tk.Button(self.root, text=L["close"], font=("DejaVu Sans", 22, "bold"),
                  width=18, height=2, bg=TILE, fg=TXT, activebackground=ALERT, activeforeground=TXT,
                  bd=0, highlightthickness=0, command=self.root.destroy).pack(side="bottom", pady=30)

    def confirm(self, server):
        self.clear()
        L = self.L
        tk.Label(self.root, text=server, font=("DejaVu Sans", 30, "bold"),
                 bg=BG, fg=TXT).pack(pady=(80, 10))
        tk.Label(self.root, text=L["confirm_q"], font=("DejaVu Sans", 18),
                 bg=BG, fg=MUTED).pack(pady=10)
        row = tk.Frame(self.root, bg=BG); row.pack(pady=40)
        tk.Button(row, text=L["yes"], font=("DejaVu Sans", 20, "bold"), width=16, height=2,
                  bg=OK, fg=TXT, bd=0, highlightthickness=0,
                  command=lambda: self.keypad(server)).pack(side="left", padx=16)
        tk.Button(row, text=L["cancel"], font=("DejaVu Sans", 20), width=12, height=2,
                  bg=TILE, fg=TXT, bd=0, highlightthickness=0,
                  command=self.menu).pack(side="left", padx=16)

    def keypad(self, server):
        self.clear()
        L = self.L
        self.pin = ""
        tk.Label(self.root, text=L["pin_title"], font=("DejaVu Sans", 26, "bold"),
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
        tk.Button(self.root, text=L["cancel"], font=("DejaVu Sans", 16), bg=CARD, fg=MUTED,
                  bd=0, highlightthickness=0, command=self.menu).pack(pady=18)

    def run(self, server):
        self.clear()
        L = self.L
        self.server = server
        self.done = False; self.ok = False
        self.url = ""; self.lines = []

        tk.Label(self.root, text=L["restore_of"] % server, font=("DejaVu Sans", 28, "bold"),
                 bg=BG, fg=TXT).pack(pady=(90, 20))
        self.status = tk.Label(self.root, text=L["touch"], font=("DejaVu Sans", 20),
                               bg=BG, fg=BUSY)
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
            self.status.config(text=self.L["touch"])
        else:
            self.bar.coords(self.fill, 0, 0, int(self.barw * pct / 100), 28)
            self.status.config(text=self.L["restoring"])
            self.pct_lbl.config(text="%d %%" % pct)
        self.root.after(700, self._poll)

    def _finish(self):
        L = self.L
        self.bar.coords(self.fill, 0, 0, self.barw if self.ok else 0, 28)
        self.pct_lbl.config(text="100 %" if self.ok else "")
        self.status.config(text=(L["done"] if self.ok else L["fail"]),
                           fg=(OK if self.ok else ALERT))
        if self.ok and self.url:
            tk.Label(self.root, text=L["dl"], font=("DejaVu Sans", 16),
                     bg=BG, fg=MUTED).pack(pady=(26, 4))
            tk.Label(self.root, text=self.url, font=("DejaVu Sans Mono", 22, "bold"),
                     bg=BG, fg=TXT).pack()
        elif not self.ok:
            tk.Label(self.root, text="\n".join(self.lines[-5:]), font=("DejaVu Sans Mono", 12),
                     bg=BG, fg=MUTED, justify="left").pack(pady=12)
        tk.Button(self.root, text=L["menu"], font=("DejaVu Sans", 18, "bold"), width=14, height=2,
                  bg=TILE, fg=TXT, bd=0, highlightthickness=0, command=self.menu).pack(pady=30)

    def loop(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().loop()
