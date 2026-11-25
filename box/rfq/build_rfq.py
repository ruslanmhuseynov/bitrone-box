"""RFQ (Request for Quotation) for Bitrone Box manufacturing — English PDF for factories.

    python box/rfq/build_rfq.py            # -> box/rfq/Bitrone-Box-RFQ.pdf
Needs reportlab. Contact fields are placeholders — fill CONTACT before sending.
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
RENDER = os.path.join(ROOT, "box", "enclosure", "render_en.png")
LOGO = os.path.join(ROOT, "frontend", "logo.png")
OUT = os.path.join(HERE, "Bitrone-Box-RFQ.pdf")

RFQ_NO = "BB-RFQ-2026-01"
DATE = "12 October 2026"
REPLY_BY = "2 November 2026"
CONTACT = {
    "Company": "Bitrone — Baku, Azerbaijan",
    "Contact person": "_______________________",
    "E-mail": "_______________________",
    "WhatsApp / phone": "+994 __ ___ __ __",
    "Delivery address": "Baku, Azerbaijan (exact address on order)",
}

NAVY = colors.HexColor("#0A1428")
BLUE = colors.HexColor("#1E7BE0")
GREEN = colors.HexColor("#3BA935")
GREY = colors.HexColor("#5A6E93")
LIGHT = colors.HexColor("#EEF2F8")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=20, textColor=NAVY,
                    spaceAfter=4, leading=24)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=NAVY,
                    spaceBefore=12, spaceAfter=5, keepWithNext=1)
B = ParagraphStyle("B", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13.5, alignment=TA_LEFT)
S = ParagraphStyle("S", parent=B, fontSize=8.5, leading=11.5, textColor=GREY)
C = ParagraphStyle("C", parent=B, fontSize=8.5, leading=11)
CB = ParagraphStyle("CB", parent=C, fontName="Helvetica-Bold")


def p(t, st=B):
    return Paragraph(t, st)


def bullets(items):
    return [p("&bull;&nbsp; " + t) for t in items]


def table(rows, widths, header=True, zebra=True):
    data = [[p(c, CB if (header and i == 0) else C) if isinstance(c, str) else c for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D3E3")),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), LIGHT)]
    if zebra:
        for i in range(2 if header else 1, len(rows), 2):
            st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8FAFD")))
    t.setStyle(TableStyle(st))
    return t


def on_page(canv, doc):
    canv.saveState()
    w, h = A4
    canv.setFillColor(NAVY)
    canv.rect(0, h - 14 * mm, w, 14 * mm, stroke=0, fill=1)
    canv.setFillColor(colors.white)
    canv.setFont("Helvetica-Bold", 10)
    canv.drawString(18 * mm, h - 9 * mm, "BITRONE  |  Request for Quotation  %s" % RFQ_NO)
    canv.setFont("Helvetica", 8.5)
    canv.drawRightString(w - 18 * mm, h - 9 * mm, "Bitrone Box — backup appliance")
    canv.setFillColor(GREY)
    canv.setFont("Helvetica", 7.5)
    canv.drawString(18 * mm, 10 * mm, "Confidential. Designs, logo and documentation are the property of Bitrone "
                                      "and may not be used for other customers.")
    canv.drawRightString(w - 18 * mm, 10 * mm, "Page %d" % doc.page)
    canv.restoreState()


def build():
    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=22 * mm, bottomMargin=18 * mm,
                            title="Bitrone Box — Request for Quotation", author="Bitrone")
    W = A4[0] - 36 * mm
    s = []

    head = Table([[Image(LOGO, width=38 * mm, height=38 * mm * 772 / 1434),
                   [p("Request for Quotation", H1),
                    p("<b>Bitrone Box</b> — branded network backup appliance<br/>"
                      "RFQ No. <b>%s</b> &nbsp;·&nbsp; Date: %s &nbsp;·&nbsp; Please reply by <b>%s</b>"
                      % (RFQ_NO, DATE, REPLY_BY), B)]]],
                 colWidths=[44 * mm, W - 44 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    s += [head, Spacer(1, 6)]

    s.append(p("1. About us", H2))
    s.append(p("Bitrone is a managed cybersecurity (SOC) provider in Baku, Azerbaijan. We protect small and "
               "medium businesses 24/7. <b>Bitrone Box</b> is a small appliance we install at each client's "
               "office: it receives encrypted backups of the client's critical data over the local network and "
               "shows the protection status on a front colour display. We are looking for a manufacturer for "
               "<b>samples, a pilot series and later volume production</b>."))

    s.append(p("2. Product overview", H2))
    s.append(Image(RENDER, width=W, height=W * 1000 / 1600))
    s.append(Spacer(1, 4))
    s.append(table([
        ["Parameter", "Value"],
        ["Outer dimensions", "108 × 130 × 42 mm (W × D × H)"],
        ["Computer", "Raspberry Pi 4 Model B, 2 GB (genuine)"],
        ["Storage", "2.5\" SATA SSD, 7 mm — <b>supplied and installed by Bitrone, NOT part of this RFQ</b>"],
        ["Display", "LILYGO T-Display-S3, 1.9\" 170×320 colour IPS, behind a window in the front wall"],
        ["Enclosure", "3 parts: tray, lid, internal shelf + logo inlays (front and lid) — files provided"],
        ["Colour", "Matte black / graphite; logo in brand green (sRGB #5BD455 — please propose closest Pantone)"],
        ["Power", "Official Raspberry Pi 15 W USB-C power supply, plug type C/F (230 V, Azerbaijan)"],
    ], [42 * mm, W - 42 * mm]))

    s.append(p("3. Scope — please quote each option separately", H2))
    s.append(table([
        ["Option", "Scope"],
        ["<b>A — Full box build</b> (preferred)",
         "Source all components in section 4 (except SSD), produce the enclosure, assemble, flash the display "
         "firmware we provide, test, label with serial number and pack. SSD bay left empty; lid closed with "
         "screws (we open it to install the SSD)."],
        ["<b>B — Enclosure only</b>",
         "Tray + lid + shelf with two-colour logo, screws and rubber feet. Pilot: 3D printing; volume: injection "
         "moulding (please quote tooling)."],
        ["<b>C — Component kit</b>",
         "Components of section 4 packed per unit, without enclosure and without assembly."],
    ], [46 * mm, W - 46 * mm]))

    s.append(p("4. Bill of materials (per unit)", H2))
    s.append(table([
        ["#", "Item", "Specification / requirements", "Qty"],
        ["1", "Single-board computer", "Raspberry Pi 4 Model B, 2 GB RAM, genuine (official distributor). "
                                       "Please also quote 4 GB as an option.", "1"],
        ["2", "Power supply", "Official Raspberry Pi 15 W USB-C PSU, EU plug (type C/F). CE marked.", "1"],
        ["3", "Display", "LILYGO T-Display-S3, <b>non-touch, soldered pin header (H577)</b>. "
                         "NOT the shell / battery / touch versions.", "1"],
        ["4", "USB 3.0 to SATA adapter", "For 2.5\" drives, cable 15–30 cm, <b>UASP</b>, chipset "
                                         "<b>ASMedia ASM1153E / ASM225CM / ASM235CM</b>. "
                                         "<b>JMicron JMS578 / JMS567 not accepted</b> (instability with "
                                         "Raspberry Pi).", "1"],
        ["5", "Jumper wires", "Dupont female–female, 20 cm (5V, GND, TX, RX)", "4"],
        ["6", "Heatsinks", "Raspberry Pi 4 set (CPU, RAM, USB controller), thermal tape", "1 set"],
        ["7", "Enclosure — tray", "Per STL file. Wall 2.4 mm. Front window for display, rear I/O window, "
                                  "side cut-outs, 4 screw posts", "1"],
        ["8", "Enclosure — lid", "Per STL. Ventilation slots + logo inlay", "1"],
        ["9", "Enclosure — shelf", "Per STL. Raspberry Pi standoffs (M2.5)", "1"],
        ["10", "Logo inlays", "Front + lid, brand green, flush with surface (2nd colour). Alternative "
                              "processes welcome: double-shot, pad print, UV print.", "2"],
        ["11", "Screws", "Lid: M3×8 self-tapping (4) · Pi: M2.5×6 (4) · Shelf: M2.2×6 self-tapping (4)", "12"],
        ["12", "Rubber feet", "Ø 12 mm, self-adhesive, black", "4"],
        ["13", "Serial label", "Bottom label with serial number BX-0001… and QR code (data supplied by us)", "1"],
        ["14", "Packaging", "Printed carton box (artwork from us) + quick-start card (A6, 2 sides)", "1"],
        ["—", "<b>Not included</b>", "2.5\" SSD — supplied and installed by Bitrone", "—"],
    ], [8 * mm, 34 * mm, W - 52 * mm, 10 * mm]))

    s.append(p("5. Enclosure requirements", H2))
    s += bullets([
        "Design files: STL (attached); STEP can be provided. Parametric source available — we can adjust "
        "dimensions to your process (draft angles, ribs, bosses for injection moulding).",
        "<b>Pilot (≤ 50 pcs):</b> 3D printing — FDM PETG/ASA, or SLS/MJF PA12 dyed black. Please state the "
        "process you propose and the surface finish.",
        "<b>Volume (≥ 500 pcs):</b> injection moulding, PC/ABS or ABS, UL94 V-0 preferred, matte texture "
        "(e.g. MT-11010). Please quote tooling (NRE), cavities and tool life.",
        "Tolerance ±0.2 mm on fit-critical features (display rails, Pi standoffs, port windows).",
        "Logo: Bitrone mark and word-mark on front and lid, in brand green. Vector artwork provided.",
        "Operating environment: office, 0–40 °C, 24/7 operation. Passive cooling via lid and side slots.",
    ])

    s.append(p("6. Assembly instructions (option A)", H2))
    s.append(table([
        ["Step", "Operation"],
        ["1", "Apply heatsinks to Raspberry Pi 4 (CPU, RAM, USB controller)."],
        ["2", "Mount Raspberry Pi on the shelf standoffs with 4 × M2.5×6 screws; Ethernet/USB ports facing the "
              "rear window."],
        ["3", "Connect display to Pi GPIO with 4 jumper wires: Pi pin 2 (5V) → display 5V; Pi pin 6 (GND) → "
              "GND; Pi pin 8 (GPIO14 TXD) → display GPIO44 (RX); Pi pin 10 (GPIO15 RXD) → display GPIO43 (TX). "
              "Final pin-out is confirmed in our assembly sheet."],
        ["4", "Flash display firmware: MicroPython for ESP32-S3 + our files (provided with step-by-step "
              "procedure). Power-on test must show the Bitrone start screen."],
        ["5", "Slide the display into the front rails behind the window (screen centred in the window)."],
        ["6", "Place the USB–SATA adapter in the SSD bay (SSD itself NOT installed); route its USB plug through "
              "the rear slot."],
        ["7", "Insert shelf with Pi into the tray, fix with 4 × M2.2 screws. Close the lid with 4 × M3×8."],
        ["8", "Stick 4 rubber feet and the serial label; pack with PSU and quick-start card."],
    ], [12 * mm, W - 12 * mm]))

    s.append(p("7. Testing and quality control", H2))
    s += bullets([
        "100 % power-on test: Raspberry Pi boots from our test medium (provided), display shows the start "
        "screen, Ethernet link LED active.",
        "Visual inspection: no scratches, logo sharp and aligned, no gaps at the lid (< 0.3 mm).",
        "Test report and photos per batch; serial numbers list (BX-xxxx) matched to Raspberry Pi serials.",
        "Samples must be approved by us before the pilot series.",
    ])

    s.append(p("8. Quantities to quote", H2))
    s.append(table([
        ["Stage", "Quantity", "Notes"],
        ["Samples", "2 pcs", "for approval — please state cost and lead time"],
        ["Pilot", "10 pcs", "after sample approval"],
        ["Series", "50 / 100 / 500 pcs", "price per tier; 500 pcs — also with injection-moulded enclosure"],
    ], [30 * mm, 36 * mm, W - 66 * mm]))

    s.append(KeepTogether([
        p("9. Please include in your quotation", H2),
        *bullets([
            "Unit price for options A, B and C at each quantity tier (USD or EUR).",
            "Tooling / NRE / setup costs, and sample cost.",
            "Lead time: samples, pilot, series. MOQ.",
            "Shipping to Baku, Azerbaijan — DAP/DDP Baku price, and EXW/FOB as alternative. "
            "Proposed carrier and transit time.",
            "Payment terms, warranty period, return policy for defective units.",
            "Certificates: CE / RoHS (power supply, finished product), HS codes for customs.",
            "Your experience with Raspberry Pi based products (photos or references welcome).",
            "Any suggestions to reduce cost or improve the design.",
        ]),
    ]))

    s.append(p("10. Intellectual property and confidentiality", H2))
    s.append(p("The enclosure design, logo, firmware and documentation are the property of Bitrone. They are "
               "shared only for this quotation and may not be used, copied or sold for other customers. "
               "Moulds paid by Bitrone remain Bitrone's property. We are ready to sign an NDA."))

    s.append(p("11. Attachments", H2))
    s += bullets([
        "Renders of Bitrone Box (this document).",
        "STL files: bitrone_box_tray, bitrone_box_lid, bitrone_box_shelf, bitrone_box_logo_front, "
        "bitrone_box_logo_lid.",
        "Logo in vector format (on request).",
    ])

    s.append(p("12. Contact", H2))
    s.append(table([[k, v] for k, v in CONTACT.items()], [42 * mm, W - 42 * mm], header=False))
    s.append(Spacer(1, 8))
    s.append(p("Thank you — we look forward to your quotation.", B))

    doc.build(s, onFirstPage=on_page, onLaterPages=on_page)
    print(OUT)


if __name__ == "__main__":
    build()
