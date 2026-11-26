#!/usr/bin/env python3
"""Bitrone Box — полноэкранный дашборд статуса защиты на моноблоке.

Дизайн повторяет фирменный стиль soc.bitrone.az (блок «Təhlükəsizlik icmalı»):
тёмно-синий фон, скруглённые плитки, зелёный/янтарный/красный акценты, крупные
числа-метрики. Переиспользует всю логику bitrone_box_status.py (скан restic в
REPO_ROOT, status.json) — отличается только вывод:
не на плату RP2040, а на весь экран через tkinter Canvas. Для слабого железа
(Atom, 2 ГБ): без браузера и тяжёлых библиотек.

Данные: bitrone_box_status.scan() читает папки-репозитории restic в REPO_ROOT
(копии зашифрованы на стороне клиента — видны только даты/размеры) и выдаёт
состояние: свежесть копий, полная копия, диск, SMART.

Управление: Ctrl+Q — выход.

Запуск:   python3 bitrone_box_screen.py -c /etc/bitrone-box/box.conf
Зависимость: python3-tk.
"""
import argparse
import os
import subprocess
import sys
import time
import tkinter as tk
import tkinter.font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bitrone_box_status as box   # noqa: E402

# --- фирменная палитра Bitrone (snapshot с soc.bitrone.az) ---
BG     = "#0B1630"   # глубокий тёмно-синий (фон)
CARD   = "#111F3F"   # секции
TILE   = "#22355F"   # плитки
STROKE = "#2A3B63"   # контуры
TXT    = "#FFFFFF"
MUTED  = "#8CA0C6"   # приглушённый светло-синий
FOOT   = "#4A5B82"

ACCENT = {
    "ok":    "#3BA935",   # фирменный зелёный
    "busy":  "#3BA1E5",   # синий — копия идёт
    "warn":  "#F5A623",   # янтарный
    "alert": "#E5484D",   # красный
    None:    "#5B6B8C",
}
# фон баннера состояния (тёмный тон под цвет акцента)
BANNER_BG = {
    "ok":    "#13261B",
    "busy":  "#102636",
    "warn":  "#2A2412",
    "alert": "#2C1620",
    None:    CARD,
}
GLYPH = {"ok": "✓", "busy": "⟳", "warn": "!", "alert": "⚠", None: "•"}

HEADLINE = {
    "az": {"ok": "HAMISI QORUNUR", "busy": "NÜSXƏ GƏLİR",
           "warn": "DİQQƏT TƏLƏB OLUNUR", "alert": "KRİTİK VƏZİYYƏT"},
    "en": {"ok": "ALL PROTECTED", "busy": "BACKUP INCOMING",
           "warn": "ATTENTION NEEDED", "alert": "CRITICAL CONDITION"},
    "ru": {"ok": "ВСЁ ПОД ЗАЩИТОЙ", "busy": "ПРИЁМ КОПИИ",
           "warn": "ТРЕБУЕТ ВНИМАНИЯ", "alert": "КРИТИЧЕСКОЕ СОСТОЯНИЕ"},
}
SUB_OK   = {"az": "Məlumatlarınız qorunur", "en": "Your data is protected",
            "ru": "Ваши данные под защитой"}
CARD_TTL = {"az": "Təhlükəsizlik icması", "en": "Security summary",
            "ru": "Сводка безопасности"}

# порядок тяжести состояний (для «худшее из»)
WORST = {None: 0, "ok": 0, "busy": 1, "warn": 2, "alert": 3}

# подписи панелей «жизнедеятельности»
PANEL = {
    "az": {
        "backup": "NÜSXƏ", "stab": "SABİTLİK", "disks": "DİSKLƏR", "mem": "YADDAŞ",
        "sys": "SİSTEM", "upd": "YENİLƏMƏ", "act": "AKTİVASİYA", "rdp": "RDP · TERMİNAL",
        "smart_ok": "SMART OK", "smart_bad": "SMART XƏTA",
        "crashes": "çökmə", "stable": "Sabit",
        "last24": "Son 24 saat · BSOD", "stable24": "Son 24 saat təmiz",
        "whea_no": "WHEA: yoxdur", "whea_yes": "WHEA: var",
        "uptime": "İşləmə vaxtı", "modules": "modul",
        "autoupd_off": "Avto: söndürülüb", "autoupd_on": "Avto: aktiv",
        "reboot_no": "Reboot: tələb olunmur", "reboot_yes": "Reboot tələb olunur",
        "kb": "KB", "current": "Güncəl", "active": "Aktiv", "inactive": "Aktiv deyil",
        "win": "Windows", "sessions": "Aktiv sessiya",
        "termok": "TermService OK", "termbad": "TermService dayanıb",
        "d_short": "g", "h_short": "s",
        "b_ok": "HAMISI QORUNUR", "b_ok_sub": "Server sağlamdır, nüsxələr qorunur",
        "b_busy": "NÜSXƏ GƏLİR", "b_warn": "DİQQƏT TƏLƏB OLUNUR",
        "b_warn_sub": "Bəzi göstəricilər yoxlama tələb edir",
        "b_unstable": "SERVER QEYRİ-SABİTDİR",
        "b_unstable_sub": "Son 24 saatda %d çökmə (BSOD) · nüsxələr qorunur",
        "b_critical": "KRİTİK VƏZİYYƏT",
        "b_critical_sub": "Avadanlıq xətası · Bitrone xəbərdar edildi · nüsxələr qorunur",
    },
    "en": {
        "backup": "BACKUP", "stab": "STABILITY", "disks": "DISKS", "mem": "MEMORY",
        "sys": "SYSTEM", "upd": "UPDATES", "act": "ACTIVATION", "rdp": "RDP · TERMINAL",
        "smart_ok": "SMART OK", "smart_bad": "SMART FAIL",
        "crashes": "crashes", "stable": "Stable",
        "last24": "Last 24h · BSOD", "stable24": "Last 24h clean",
        "whea_no": "WHEA: none", "whea_yes": "WHEA: yes",
        "uptime": "Uptime", "modules": "modules",
        "autoupd_off": "Auto: off", "autoupd_on": "Auto: on",
        "reboot_no": "Reboot: not needed", "reboot_yes": "Reboot required",
        "kb": "KB", "current": "Up to date", "active": "Active", "inactive": "Not active",
        "win": "Windows", "sessions": "Active sessions",
        "termok": "TermService OK", "termbad": "TermService down",
        "d_short": "d", "h_short": "h",
        "b_ok": "ALL PROTECTED", "b_ok_sub": "Server healthy, backups protected",
        "b_busy": "BACKUP INCOMING", "b_warn": "ATTENTION NEEDED",
        "b_warn_sub": "Some metrics need a check",
        "b_unstable": "SERVER UNSTABLE",
        "b_unstable_sub": "%d crashes in last 24h (BSOD) · backups protected",
        "b_critical": "CRITICAL CONDITION",
        "b_critical_sub": "Hardware fault · Bitrone notified · backups protected",
    },
    "ru": {
        "backup": "КОПИЯ", "stab": "СТАБИЛЬНОСТЬ", "disks": "ДИСКИ", "mem": "ПАМЯТЬ",
        "sys": "СИСТЕМА", "upd": "ОБНОВЛЕНИЯ", "act": "АКТИВАЦИЯ", "rdp": "RDP · ТЕРМИНАЛ",
        "smart_ok": "SMART OK", "smart_bad": "SMART СБОЙ",
        "crashes": "BSOD", "stable": "Стабилен",
        "last24": "За 24 ч · BSOD", "stable24": "За 24 ч чисто",
        "whea_no": "WHEA: нет", "whea_yes": "WHEA: есть",
        "uptime": "Аптайм", "modules": "мод.",
        "autoupd_off": "Авто: выкл", "autoupd_on": "Авто: вкл",
        "reboot_no": "Перезагрузка: не нужна", "reboot_yes": "Нужна перезагрузка",
        "kb": "KB", "current": "Актуально", "active": "Активна", "inactive": "Не активна",
        "win": "Windows", "sessions": "Активных сессий",
        "termok": "TermService OK", "termbad": "TermService стоит",
        "d_short": "д", "h_short": "ч",
        "b_ok": "ВСЁ ПОД ЗАЩИТОЙ", "b_ok_sub": "Сервер здоров, копии защищены",
        "b_busy": "ПРИЁМ КОПИИ", "b_warn": "ТРЕБУЕТ ВНИМАНИЯ",
        "b_warn_sub": "Некоторые показатели нужно проверить",
        "b_unstable": "СЕРВЕР НЕСТАБИЛЕН",
        "b_unstable_sub": "За 24 ч BSOD: %d · копии защищены",
        "b_critical": "КРИТИЧЕСКОЕ СОСТОЯНИЕ",
        "b_critical_sub": "Сбой оборудования · Bitrone уведомлён · копии защищены",
    },
}


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    r = max(1, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


def short_os(s):
    return ((s or "").replace("Windows Server", "Win Server").replace(" Evaluation", "")
            .replace(" Standard", "").replace(" Datacenter", " DC").strip())


class Screen:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lang = cfg["LANG"] if cfg["LANG"] in HEADLINE else "az"
        self.interval = max(2, int(cfg["INTERVAL"]))
        self.smart = None
        self.smart_at = 0.0
        self.msg = {"state": "ok", "title": "BITRONE", "pages": []}
        self.health = []
        self.status = {}

        self.root = tk.Tk()
        self.root.title("Bitrone Box")
        self.root.configure(bg=BG)
        self.root.attributes("-fullscreen", True)
        self.root.config(cursor="none")
        self.root.bind("<Control-q>", lambda e: self.root.destroy())

        self.W = self.root.winfo_screenwidth() or 1366
        self.H = self.root.winfo_screenheight() or 768
        s = self.W

        def F(px, bold=False):
            return tkfont.Font(family="DejaVu Sans", size=max(10, px),
                               weight="bold" if bold else "normal")
        self.f_brand = F(s // 32, True)
        self.f_card  = F(s // 66)
        self.f_sn    = F(s // 66)
        self.f_clock = F(s // 30, True)
        self.f_client = F(s // 60)
        self.f_head  = F(s // 26, True)
        self.f_sub   = F(s // 58)
        self.f_glyph = F(s // 30, True)
        self.f_big   = F(s // 16, True)
        self.f_label = F(s // 70)
        self.f_hint  = F(s // 34, True)
        self.f_foot  = F(s // 82)
        # шрифты панелей «жизнедеятельности» (8 плиток)
        self.f_plabel  = F(s // 80)
        self.f_pbig    = F(s // 22, True)
        self.f_pbig_sm = F(s // 34, True)
        self.f_pline   = F(s // 84)
        self._fcache = {}

        # фирменный логотип (белая плашка в шапке); фолбэк — текст BITRONE
        self.logo = None
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "assets", "bitrone_logo.png")
            img = tk.PhotoImage(file=path)
            target = max(1, int(self.H * 0.072))
            factor = max(1, round(img.height() / target))
            self.logo = img.subsample(factor, factor) if factor > 1 else img
        except Exception as e:
            print("logo: %s" % e, file=sys.stderr, flush=True)

        self.cv = tk.Canvas(self.root, bg=BG, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)

        # скрытый запуск восстановления: ДОЛГОЕ касание (>=1.5с) в правом верхнем углу
        self._press_t = 0.0
        self._press_xy = (0, 0)
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<ButtonRelease-1>", self._release)

        # кнопка восстановления — поверх canvas (перерисовка её не стирает)
        self.restore_btn = tk.Button(self.root, text=self._restore_label(), command=self._launch_restore,
                                     font=self.f_sub, bg=TILE, fg=TXT,
                                     activebackground=ACCENT["busy"], activeforeground=TXT,
                                     bd=0, highlightthickness=0, padx=16, pady=7, cursor="hand2")
        self.restore_btn.place(relx=0.985, rely=0.965, anchor="se")

        # кнопки языка (AZ/RU/EN) — поверх canvas, левый нижний угол
        self.lang_btns = {}
        lb = tk.Frame(self.root, bg=BG)
        for code in ("az", "ru", "en"):
            b = tk.Button(lb, text=code.upper(), font=self.f_sub, width=4, pady=6,
                          fg=TXT, activebackground=ACCENT["busy"], activeforeground=TXT,
                          bd=0, highlightthickness=0, cursor="hand2",
                          command=lambda c=code: self.set_lang(c))
            b.pack(side="left", padx=5)
            self.lang_btns[code] = b
        lb.place(relx=0.015, rely=0.965, anchor="sw")
        self._lang_btn_colors()

        self.refresh_data()
        self.tick()

    def _press(self, e):
        self._press_t = time.time()
        self._press_xy = (e.x, e.y)

    def _release(self, e):
        held = time.time() - self._press_t
        x0, y0 = self._press_xy
        corner = (x0 > self.W * 0.85 and y0 < self.H * 0.15 and
                  e.x > self.W * 0.85 and e.y < self.H * 0.15)
        if held >= 1.5 and corner:
            self._launch_restore()

    def _launch_restore(self):
        gui = "/opt/bitrone-box/restore-gui.py"
        if not os.path.exists(gui):
            return
        try:
            subprocess.Popen(["python3", gui])
        except OSError as ex:
            print("restore-gui: %s" % ex, file=sys.stderr, flush=True)

    def _restore_label(self):
        return {"az": "⟲ Bərpa", "ru": "⟲ Восстановить",
                "en": "⟲ Restore"}.get(self.lang, "⟲ Restore")

    def _lang_btn_colors(self):
        for code, b in self.lang_btns.items():
            b.config(bg=(ACCENT["ok"] if code == self.lang else TILE))

    def set_lang(self, code):
        if code not in HEADLINE:
            return
        self.lang = code
        self.cfg["LANG"] = code
        self.restore_btn.config(text=self._restore_label())
        self._lang_btn_colors()
        self._persist_lang(code)
        try:                       # пересобрать сообщение (панель копий) на новом языке
            self.msg, self.status = box.snapshot(self.cfg, self.smart, time.time())
        except Exception as e:
            print("lang snapshot: %s" % e, file=sys.stderr, flush=True)
        self.render()

    def _persist_lang(self, code):
        path = "/etc/bitrone-box/box.conf"
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            found = False
            for i, ln in enumerate(lines):
                if ln.strip().startswith("LANG="):
                    lines[i] = "LANG=%s\n" % code; found = True
            if not found:
                lines.append("LANG=%s\n" % code)
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except OSError:
            pass  # нет прав на запись (kiosk) — переключаем только для этой сессии

    def refresh_data(self):
        now = time.time()
        if now - self.smart_at > 600:
            self.smart = box.smart_ok(self.cfg["SMART_DEVICE"], self.cfg["STATE_DIR"])
            self.smart_at = now
        try:
            self.msg, status = box.snapshot(self.cfg, self.smart, now)
            self.status = status
            box.write_status(self.cfg["STATUS_JSON"], status)
        except Exception as e:
            print("refresh: %s" % e, file=sys.stderr, flush=True)
        try:
            self.health = box.load_health(self.cfg.get("HEALTH_ROOT", ""))
        except Exception as e:
            print("health: %s" % e, file=sys.stderr, flush=True)
            self.health = []
        self.render()
        self.root.after(self.interval * 1000, self.refresh_data)

    def tick(self):
        self.render()
        self.root.after(1000, self.tick)

    # ---------------- отрисовка ----------------
    def render(self):
        if self.health:
            self.render_rich()
        else:
            self.render_dashboard(self.msg.get("state", "ok"))

    def render_dashboard(self, state):
        cv, W, H = self.cv, self.W, self.H
        cv.delete("all")
        cv.configure(bg=BG)
        pad = int(W * 0.028)
        accent = ACCENT.get(state, ACCENT[None])

        # ---- шапка: логотип Bitrone (белая плашка) + заголовок | часы + клиент ----
        hy = int(H * 0.115)
        cy = hy // 2
        dx = pad
        if self.logo is not None:
            lw, lh = self.logo.width(), self.logo.height()
            px_pad = int(W * 0.011)
            py_pad = int(H * 0.016)
            round_rect(cv, dx, cy - lh // 2 - py_pad,
                       dx + lw + 2 * px_pad, cy + lh // 2 + py_pad,
                       int(H * 0.016), fill="#FFFFFF", outline="")
            cv.create_image(dx + px_pad, cy, anchor="w", image=self.logo)
            dx += lw + 2 * px_pad + int(W * 0.018)
        else:
            dr = int(H * 0.009)
            for col in ("#E5484D", "#F5A623", "#3BA935"):
                cv.create_oval(dx, cy - dr, dx + 2 * dr, cy + dr, fill=col, outline="")
                dx += int(dr * 3.2)
            dx += int(W * 0.012)
            cv.create_text(dx, cy, anchor="w", text="BITRONE", fill=TXT, font=self.f_brand)
            dx += self.f_brand.measure("BITRONE") + int(W * 0.012)
        cv.create_text(dx, cy, anchor="w",
                       text=CARD_TTL[self.lang] + "  ·  " + self.cfg["SN"],
                       fill=MUTED, font=self.f_card)
        cv.create_text(W - pad, cy - int(H * 0.016), anchor="e",
                       text=time.strftime("%H:%M"), fill=TXT, font=self.f_clock)
        if self.cfg.get("CLIENT"):
            cv.create_text(W - pad, cy + int(H * 0.030), anchor="e",
                           text=self.cfg["CLIENT"], fill=MUTED, font=self.f_client)

        # ---- баннер состояния (как предупреждающая карточка на сайте) ----
        by0 = hy + int(pad * 0.6)
        by1 = by0 + int(H * 0.19)
        round_rect(cv, pad, by0, W - pad, by1, int(H * 0.022),
                   fill=BANNER_BG.get(state, CARD), outline=accent, width=2)
        # квадратный значок-чип
        chip = int(H * 0.11)
        chx0 = pad + int(W * 0.022)
        chy0 = (by0 + by1) // 2 - chip // 2
        round_rect(cv, chx0, chy0, chx0 + chip, chy0 + chip, int(H * 0.016),
                   fill=accent, outline="")
        cv.create_text(chx0 + chip // 2, chy0 + chip // 2,
                       text=GLYPH.get(state, "•"), fill="#0B1630", font=self.f_glyph)
        tx = chx0 + chip + int(W * 0.028)
        cv.create_text(tx, (by0 + by1) // 2 - int(H * 0.028), anchor="w",
                       text=HEADLINE[self.lang].get(state, ""), fill=TXT, font=self.f_head)
        sub = SUB_OK[self.lang] if state == "ok" else \
            (self.msg.get("pages") or [{}])[0].get("lines", [""])[0]
        cv.create_text(tx, (by0 + by1) // 2 + int(H * 0.035), anchor="w",
                       text=sub, fill=MUTED, font=self.f_sub)

        # ---- стат-плитки (крупные числа, как «3/3 qorunan server») ----
        metrics = [p for p in self.msg.get("pages", []) if p.get("big")]
        info = [p for p in self.msg.get("pages", []) if not p.get("big")]
        gy0 = by1 + int(pad * 0.7)
        gy1 = H - int(H * 0.055)
        if info:
            gy1 -= int(H * 0.085)
        n = max(1, len(metrics))
        cols = n if n <= 3 else 2
        rows = (n + cols - 1) // cols
        gap = int(pad * 0.7)
        tw = (W - 2 * pad - (cols - 1) * gap) / cols
        th = (gy1 - gy0 - (rows - 1) * gap) / rows
        for i, p in enumerate(metrics):
            c, r = i % cols, i // cols
            x0 = pad + c * (tw + gap)
            y0 = gy0 + r * (th + gap)
            self.tile(cv, x0, y0, x0 + tw, y0 + th, p)

        # ---- инфо-строка (клиент/папка) ----
        if info:
            iy1 = H - int(H * 0.055)
            iy0 = iy1 - int(H * 0.075)
            round_rect(cv, pad, iy0, W - pad, iy1, int(H * 0.015),
                       fill=CARD, outline=STROKE, width=1)
            cv.create_text(pad + int(W * 0.022), (iy0 + iy1) // 2, anchor="w",
                           text="   ".join(info[0].get("lines", [])),
                           fill=MUTED, font=self.f_label)

        cv.create_text(W - pad, H - int(H * 0.022), anchor="e",
                       text="soc.bitrone.az · %s" % time.strftime("%d.%m.%Y"),
                       fill=FOOT, font=self.f_foot)

    def tile(self, cv, x0, y0, x1, y1, page):
        acc = ACCENT.get(page.get("icon"), ACCENT[None])
        round_rect(cv, x0, y0, x1, y1, int(self.H * 0.02),
                   fill=TILE, outline=STROKE, width=1)
        # тонкая акцентная полоса сверху
        round_rect(cv, x0 + int((x1 - x0) * 0.06), y0 + int(self.H * 0.012),
                   x1 - int((x1 - x0) * 0.06), y0 + int(self.H * 0.018),
                   3, fill=acc, outline="")
        px = x0 + int((x1 - x0) * 0.08)
        cv.create_text(px, y0 + (y1 - y0) * 0.42, anchor="w",
                       text=str(page.get("big", "")), fill=acc, font=self.f_big)
        ly = y0 + (y1 - y0) * 0.70
        for ln in page.get("lines", [])[:3]:
            cv.create_text(px, ly, anchor="w", text=ln, fill=TXT, font=self.f_label,
                           width=int((x1 - x0) * 0.85))
            ly += self.f_label.cget("size") * 1.8

    # ---------------- богатый дашборд (health.json) ----------------
    def F2(self, px, bold=True):
        key = (px, bold)
        f = self._fcache.get(key)
        if f is None:
            f = tkfont.Font(family="DejaVu Sans", size=max(10, px),
                            weight="bold" if bold else "normal")
            self._fcache[key] = f
        return f

    def fit_font(self, text, max_w, base_px, bold=True):
        px = base_px
        while px > 13:
            f = self.F2(px, bold)
            if f.measure(text) <= max_w:
                return f
            px -= 2
        return self.F2(13, bold)

    def fmt_uptime(self, days, L):
        total_h = int(round(float(days) * 24))
        dd, hh = divmod(total_h, 24)
        if dd > 0:
            return "%d%s %d%s" % (dd, L["d_short"], hh, L["h_short"])
        return "%d%s" % (hh, L["h_short"])

    def build_panels(self):
        L = PANEL.get(self.lang, PANEL["az"])
        h = self.health[0] if self.health else {}
        pages = self.msg.get("pages", [])
        bk = next((p for p in pages if p.get("big") and p.get("icon")), None)
        panels, contrib = [], [self.msg.get("state", "ok")]

        if bk:
            panels.append({"label": L["backup"], "state": bk.get("icon"),
                           "big": bk.get("big", "—"), "lines": bk.get("lines", [])[:2]})

        st = h.get("stability")
        if st is not None:
            c = int(st.get("crashes_24h", 0) or 0)
            whea = int(st.get("whea", 0) or 0)
            s = "alert" if (c > 0 or whea > 0) else "ok"
            contrib.append(s)
            big = ("%d %s" % (c, L["crashes"])) if c > 0 else L["stable"]
            panels.append({"label": L["stab"], "state": s, "big": big,
                           "lines": [L["last24"] if c > 0 else L["stable24"],
                                     L["whea_no"] if whea == 0 else L["whea_yes"]]})

        dk = h.get("disks")
        if dk:
            smart = dk.get("smart", "ok")
            vols = dk.get("volumes", [])
            s = "ok"
            if smart == "bad":
                s = "alert"
            elif smart == "warn" or any(int(v.get("free_pct", 100)) < 15 for v in vols):
                s = "warn"
            contrib.append(s)
            bars = []
            for v in vols[:3]:
                name = v.get("vol", "")
                if v.get("label"):
                    name += " " + v["label"]
                fp = int(v.get("free_pct", 0))
                bars.append((name, fp, "warn" if fp < 15 else "ok"))
            smart_lbl = L["smart_ok"] if smart == "ok" else L["smart_bad"]
            tline = "%s°C · wear %s%%" % (dk.get("temp_c", "?"), dk.get("wear_pct", "?"))
            panels.append({"label": L["disks"] + " · " + smart_lbl, "state": s,
                           "bars": bars, "lines": [tline]})

        mem = h.get("memory")
        if mem:
            panels.append({"label": L["mem"], "state": None,
                           "big": "%s GB" % mem.get("total_gb", "?"),
                           "lines": ["ECC · %s" % mem.get("ecc", "?"),
                                     "%s %s" % (mem.get("modules", "?"), L["modules"])]})

        sy = h.get("system")
        if sy:
            ud = sy.get("uptime_days")
            big = self.fmt_uptime(ud, L) if ud is not None else "—"
            lines = [L["uptime"]]
            if sy.get("os"):
                osl = short_os(sy["os"])
                if len(osl) > 20:
                    osl = osl[:19].rstrip() + "…"
                lines.append(osl)
            panels.append({"label": L["sys"], "state": None, "big": big, "lines": lines[:2]})

        pt = h.get("patching")
        if pt is not None:
            up = int(pt.get("updates_pending", 0) or 0)
            pend = bool(pt.get("pending_reboot"))
            auto = pt.get("autoupdate", "on")
            s = "warn" if (up > 0 or pend or auto == "off") else "ok"
            contrib.append(s)
            big = ("%d %s" % (up, L["kb"])) if up > 0 else L["current"]
            panels.append({"label": L["upd"], "state": s, "big": big,
                           "lines": [L["autoupd_off"] if auto == "off" else L["autoupd_on"],
                                     L["reboot_yes"] if pend else L["reboot_no"]]})

        act = h.get("activation")
        if act is not None:
            ok = act.get("status") == "ok"
            s = "ok" if ok else "warn"
            contrib.append(s)
            panels.append({"label": L["act"], "state": s,
                           "big": L["active"] if ok else L["inactive"],
                           "lines": [L["win"], str(act.get("status", ""))]})

        rd = h.get("rds")
        if rd:
            running = rd.get("termservice") == "running"
            contrib.append("ok" if running else "warn")
            panels.append({"label": L["rdp"], "state": None if running else "warn",
                           "big": str(rd.get("sessions_active", "?")),
                           "lines": [L["sessions"], L["termok"] if running else L["termbad"]]})

        overall = max(contrib, key=lambda x: WORST.get(x, 0))
        return overall, self.banner_for(overall, h, L), panels

    def banner_for(self, overall, h, L):
        st = h.get("stability") or {}
        c = int(st.get("crashes_24h", 0) or 0)
        if overall == "alert":
            if c > 0:
                return {"state": "alert", "headline": L["b_unstable"],
                        "subline": L["b_unstable_sub"] % c}
            return {"state": "alert", "headline": L["b_critical"], "subline": L["b_critical_sub"]}
        if overall == "warn":
            return {"state": "warn", "headline": L["b_warn"], "subline": L["b_warn_sub"]}
        if overall == "busy":
            return {"state": "busy", "headline": L["b_busy"], "subline": ""}
        return {"state": "ok", "headline": L["b_ok"], "subline": L["b_ok_sub"]}

    def render_rich(self):
        cv, W, H = self.cv, self.W, self.H
        cv.delete("all")
        cv.configure(bg=BG)
        overall, banner, panels = self.build_panels()
        acc = ACCENT.get(banner["state"], ACCENT[None])
        h = self.health[0] if self.health else {}
        sy = h.get("system", {})

        # безопасные отступы под overscan монитора (настраиваются в box.conf)
        try:
            top = int(H * float(self.cfg.get("SAFE_TOP_PCT", 0) or 0) / 100.0)
            side = int(W * float(self.cfg.get("SAFE_SIDE_PCT", 0) or 0) / 100.0)
        except ValueError:
            top, side = int(H * 0.05), int(W * 0.03)
        pad = side + int(W * 0.02)

        # ---- шапка ----
        cy = top + int(H * 0.05)
        hy = top + int(H * 0.11)
        dx = pad
        if self.logo is not None:
            lw, lh = self.logo.width(), self.logo.height()
            px_pad, py_pad = int(W * 0.011), int(H * 0.016)
            round_rect(cv, dx, cy - lh // 2 - py_pad, dx + lw + 2 * px_pad,
                       cy + lh // 2 + py_pad, int(H * 0.016), fill="#FFFFFF", outline="")
            cv.create_image(dx + px_pad, cy, anchor="w", image=self.logo)
            dx += lw + 2 * px_pad + int(W * 0.018)
        else:
            cv.create_text(dx, cy, anchor="w", text="BITRONE", fill=TXT, font=self.f_brand)
            dx += self.f_brand.measure("BITRONE") + int(W * 0.012)
        sub = CARD_TTL[self.lang]
        if self.cfg.get("CLIENT"):
            sub += " · " + self.cfg["CLIENT"]
        if h.get("name"):
            sub += " · " + h["name"]
        cv.create_text(dx, cy, anchor="w", text=sub, fill=MUTED, font=self.f_card)
        cv.create_text(W - pad, cy - int(H * 0.016), anchor="e",
                       text=time.strftime("%H:%M"), fill=TXT, font=self.f_clock)
        osline = short_os(sy.get("os", ""))
        if sy.get("build"):
            osline = (osline + " · " + str(sy["build"])).strip(" ·")
        if osline:
            cv.create_text(W - pad, cy + int(H * 0.030), anchor="e",
                           text=osline, fill=MUTED, font=self.f_client)

        # ---- баннер состояния (во всю ширину) ----
        by0 = hy + int(H * 0.012)
        by1 = by0 + int(H * 0.15)
        round_rect(cv, pad, by0, W - pad, by1, int(H * 0.02),
                   fill=BANNER_BG.get(banner["state"], CARD), outline=acc, width=2)
        chip = int(H * 0.09)
        chx0 = pad + int(W * 0.016)
        chy0 = (by0 + by1) // 2 - chip // 2
        round_rect(cv, chx0, chy0, chx0 + chip, chy0 + chip, int(H * 0.014),
                   fill=acc, outline="")
        cv.create_text(chx0 + chip // 2, chy0 + chip // 2,
                       text=GLYPH.get(banner["state"], "•"), fill="#0B1630", font=self.f_glyph)
        tx = chx0 + chip + int(W * 0.022)
        if banner.get("subline"):
            cv.create_text(tx, (by0 + by1) // 2 - int(H * 0.022), anchor="w",
                           text=banner["headline"], fill=TXT, font=self.f_head)
            cv.create_text(tx, (by0 + by1) // 2 + int(H * 0.030), anchor="w",
                           text=banner["subline"], fill=MUTED, font=self.f_sub)
        else:
            cv.create_text(tx, (by0 + by1) // 2, anchor="w",
                           text=banner["headline"], fill=TXT, font=self.f_head)

        # ---- сетка панелей (до 4 в ряд) ----
        gy0 = by1 + int(H * 0.035)
        gy1 = H - top - int(H * 0.03)
        cols = 4 if len(panels) > 4 else max(1, len(panels))
        rows = (len(panels) + cols - 1) // cols if panels else 1
        gap = int(W * 0.016)
        tw = (W - 2 * pad - (cols - 1) * gap) / cols
        th = (gy1 - gy0 - (rows - 1) * gap) / rows
        for i, p in enumerate(panels):
            c, r = i % cols, i // cols
            x0 = pad + c * (tw + gap)
            y0 = gy0 + r * (th + gap)
            self.tile_rich(cv, x0, y0, x0 + tw, y0 + th, p)

        cv.create_text(W // 2, H - top - int(H * 0.008), anchor="center",
                       text="soc.bitrone.az · %s" % time.strftime("%d.%m.%Y %H:%M"),
                       fill=FOOT, font=self.f_foot)

    def tile_rich(self, cv, x0, y0, x1, y1, p):
        st = p.get("state")
        acc = ACCENT.get(st, ACCENT[None]) if st else ACCENT[None]
        round_rect(cv, x0, y0, x1, y1, int(self.H * 0.018),
                   fill=TILE, outline=STROKE, width=1)
        round_rect(cv, x0 + int((x1 - x0) * 0.05), y0 + int(self.H * 0.010),
                   x1 - int((x1 - x0) * 0.05), y0 + int(self.H * 0.016),
                   3, fill=acc, outline="")
        px = x0 + int((x1 - x0) * 0.08)
        cv.create_text(px, y0 + (y1 - y0) * 0.15, anchor="w", text=p.get("label", ""),
                       fill=MUTED, font=self.f_plabel, width=int((x1 - x0) * 0.90))
        if p.get("bars"):
            by = y0 + (y1 - y0) * 0.38
            barx = x0 + (x1 - x0) * 0.50
            barw = (x1 - x0) * 0.26
            bh = int(self.H * 0.007)
            for (name, pct, bs) in p["bars"]:
                cv.create_text(px, by, anchor="w", text=name, fill=TXT, font=self.f_pline)
                cv.create_rectangle(barx, by - bh, barx + barw, by + bh, fill=BG, outline="")
                fw = barw * max(0, min(100, pct)) / 100.0
                cv.create_rectangle(barx, by - bh, barx + fw, by + bh,
                                    fill=ACCENT.get(bs, ACCENT["ok"]), outline="")
                cv.create_text(x1 - int((x1 - x0) * 0.08), by, anchor="e",
                               text="%d%%" % pct, fill=MUTED, font=self.f_pline)
                by += (y1 - y0) * 0.17
            for ln in p.get("lines", [])[:1]:
                cv.create_text(px, y1 - (y1 - y0) * 0.12, anchor="w", text=ln,
                               fill=MUTED, font=self.f_pline)
        else:
            big_color = ACCENT.get(st) if st in ("ok", "warn", "alert", "busy") else TXT
            big = str(p.get("big", ""))
            bigfont = self.fit_font(big, (x1 - x0) * 0.84, self.W // 22)
            cv.create_text(px, y0 + (y1 - y0) * 0.45, anchor="w",
                           text=big, fill=big_color, font=bigfont)
            ly = y0 + (y1 - y0) * 0.71
            for ln in p.get("lines", [])[:2]:
                cv.create_text(px, ly, anchor="w", text=ln, fill=MUTED,
                               font=self.f_pline, width=int((x1 - x0) * 0.90))
                ly += self.f_pline.cget("size") * 2.1

    def run(self):
        self.root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="Bitrone Box — дашборд статуса (стиль soc.bitrone.az)")
    ap.add_argument("-c", "--config", default="/etc/bitrone-box/box.conf")
    args = ap.parse_args()
    cfg = box.load_config(args.config)
    Screen(cfg).run()


if __name__ == "__main__":
    main()
