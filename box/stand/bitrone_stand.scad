// Bitrone Box — универсальная подставка для мини-ПК (OpenSCAD, параметрическая)
//
// ПК стоит вертикально в продольном пазу. Паз один на все модели (66 мм),
// под толщину конкретного ПК печатается сменный вкладыш (part = "liner").
// Спереди наклонная консоль: OLED 1.3", кнопка, световая полоса; внутри — RP2040-Zero.
//
// Экспорт STL: выберите part, затем F6 → File → Export → STL.
//   base         — корпус (PETG/ASA, 3 стенки, 25% заполнение; печатать дном вниз,
//                  поддержки «от стола» — только в полости консоли и в щели полосы)
//   liner        — вкладыш под толщину pc_w (PETG)
//   cover        — крышка дна консоли (4 самореза M3×8)
//   diffuser     — рассеиватель за щелью полосы (прозрачный/натуральный PETG)
//   button_cap   — колпачок кнопки
//   side_panel   — накладка на бок ПК (лучше лазером из акрила 3 мм; тут — для печати/шаблона)
//   all          — всё вместе для просмотра

part = "all";

// Толщина ВАШЕГО мини-ПК (узкая сторона), мм — измерьте штангенциркулем.
// Примерно: Lenovo ThinkCentre Tiny 34.5 · HP EliteDesk/ProDesk Mini 34.3 · Dell OptiPlex Micro 36
//           Beelink EQ/Mini S ~39–43 · GMKtec NucBox ~42 · Intel NUC slim 37 / tall 51
pc_w = 34.5;

/* [Корпус] */
L = 245;            // длина (ПК до 185 мм в глубину)
W = 96;             // ширина
H = 20;             // высота основания
R = 8;              // скругление углов
console_len = 50;   // длина консоли
console_h = 28;     // высота консоли у задней кромки
slot_w = 66;        // ширина паза (без вкладыша — ПК до ~64 мм)
slot_floor = 8;     // дно паза
slot_y0 = 60;       // начало паза: 10 мм воздуха между консолью и передом ПК

/* [Электроника] */
oled_win = [30, 16];        // окно экрана (активная зона 1.3")
oled_pcb = [36.5, 34.5];    // плата модуля 1.3" SH1106 с запасом
oled_y = 26;                // центр экрана по длине консоли
oled_dx = -6;               // смещение экрана от центра влево (справа кнопка)
oled_win_dy = 0;            // сдвиг окна относительно платы модуля (если активная зона не по центру)
btn_x = 80;                 // кнопка
btn_y = 26;
led_slit = [70, 4];         // щель полосы: длина × высота (10 LED WS2812 @ 144/м)
led_z = 5;

$fn = 48;
ang = atan((console_h - H) / console_len);
function zs(y) = H + (console_h - H) * y / console_len;   // высота наклонной грани

module rrect(w, l, r) { offset(r) offset(-r) square([w, l]); }

// на наклонной грани консоли: локальные X — поперёк, Y — вверх по склону, Z — наружу
module on_slope(x, y) { translate([x, y, zs(y)]) rotate([ang, 0, 0]) children(); }

module vents(x0, w, y0, y1, h) {
    for (y = [y0 + 15 : 22 : y1 - 15]) translate([x0, y, -1]) cube([w, 5, h + 2]);
}

module base() {
    difference() {
        union() {
            linear_extrude(H) rrect(W, L, R);
            intersection() {
                linear_extrude(console_h + 1) rrect(W, L, R);
                rotate([90, 0, 90]) linear_extrude(W)
                    polygon([[0, 0], [console_len, 0], [console_len, console_h], [0, H]]);
            }
        }
        // паз под ПК
        translate([(W - slot_w) / 2, slot_y0, slot_floor]) cube([slot_w, L, H]);
        // вентиляция дна паза
        vents(W / 2 - 18, 36, slot_y0, L, slot_floor);
        // полость консоли (открыта снизу, закрывается крышкой)
        translate([12, 3, -1]) cube([W - 24, console_len - 4, 17]);
        // OLED: окно в обшивке 1.6 мм + карман под модуль
        on_slope(W / 2 + oled_dx, oled_y) {
            translate([-oled_win[0] / 2, -oled_win[1] / 2 + oled_win_dy, -2]) cube([oled_win[0], oled_win[1], 5]);
            translate([-oled_pcb[0] / 2, -oled_pcb[1] / 2, -1.6 - 14]) cube([oled_pcb[0], oled_pcb[1], 14]);
        }
        // кнопка: отверстие + гнездо под тактовую кнопку 6×6 снизу
        on_slope(btn_x, btn_y) {
            translate([0, 0, -3]) cylinder(d = 7, h = 6);
            translate([0, 0, -16]) cylinder(d = 12, h = 14);
        }
        // щель световой полосы спереди
        translate([(W - led_slit[0]) / 2, -1, led_z]) cube([led_slit[0], 5, led_slit[1]]);
        // надпись спереди
        translate([W / 2, 0.6, 14.5]) rotate([90, 0, 0]) linear_extrude(1)
            text("BITRONE BOX", size = 4.2, font = "Liberation Sans:style=Bold",
                 halign = "center", valign = "center", spacing = 1.15);
        // канал USB-кабеля по дну: из полости консоли назад
        translate([16, 40, -1]) cube([9, L, 6]);
        // гнездо крышки дна + отверстия под саморезы M3
        translate([4, 1, -1]) cube([W - 8, 49, 2.6]);
        for (p = [[8, 5], [W - 8, 5], [8, 46], [W - 8, 46]])
            translate([p[0], p[1], -1]) cylinder(d = 2.5, h = 10);
    }
}

module cover() {
    cw = W - 8 - 0.4; cl = 49 - 0.4;
    difference() {
        cube([cw, cl, 1.6]);
        for (p = [[4, 4], [W - 12, 4], [4, 45], [W - 12, 45]])
            translate([p[0] - 0.2, p[1] - 0.2, -1]) { cylinder(d = 3.4, h = 4); translate([0, 0, 1.6]) cylinder(d1 = 3.4, d2 = 6.4, h = 1.5); }
        translate([12 - 0.2, 39, -1]) cube([9, 20, 4]);   // проход кабеля в канал
        for (x = [20 : 8 : cw - 20]) translate([x, 20, -1]) cube([3, 14, 4]);  // вентиляция платы
    }
}

module liner(w = pc_w) {
    gap = w + 0.8;
    ow = slot_w - 0.6;
    lh = H - slot_floor;
    ll = L - slot_y0 - 0.4;
    wall = (ow - gap) / 2;
    assert(gap <= ow - 2.4, "ПК шире 63 мм — вкладыш не нужен, ставьте прямо в паз");
    difference() {
        cube([ow, ll, lh]);
        translate([(ow - gap) / 2, -1, 2]) cube([gap, ll + 2, lh]);
        for (y = [15 : 22 : ll - 15]) translate([ow / 2 - 18, y, -1]) cube([36, 5, 4]);
        // маркировка толщины на верхней кромке левой стенки
        translate([wall / 2, 12, lh - 0.6]) rotate([0, 0, 90]) linear_extrude(1)
            text(str(w), size = min(3.5, wall - 1.5), halign = "left", valign = "center");
    }
}

module diffuser() { cube([led_slit[0] + 6, 1.2, 12]); }

module button_cap() {
    cylinder(d = 10, h = 1.2);
    cylinder(d = 6.4, h = 1.2 + 4.5);
}

module side_panel() {
    difference() {
        linear_extrude(3) rrect(150, 140, 6);
        // гнёзда под неодимовые магниты 10×2 с обратной стороны
        for (p = [[15, 15], [135, 15], [15, 125], [135, 125]]) translate([p[0], p[1], -1]) cylinder(d = 10.3, h = 3);
    }
}

if (part == "base") base();
else if (part == "liner") liner();
else if (part == "cover") cover();
else if (part == "diffuser") diffuser();
else if (part == "button_cap") button_cap();
else if (part == "side_panel") side_panel();
else {
    color("#13254A") base();
    color("#3B9EFF") translate([(W - slot_w) / 2 + 0.3, slot_y0 + 0.2, slot_floor]) liner();
    color("#2A2E36", 0.9) translate([(W - pc_w) / 2, slot_y0 + 1, slot_floor + 2]) cube([pc_w, 180, 180]);
    color("#1A3263") translate([W / 2 + pc_w / 2, slot_y0 + 20, slot_floor + 22]) rotate([90, 0, 90]) side_panel();
    color("#5BD455") translate([(W - led_slit[0]) / 2, 0, led_z]) cube([led_slit[0], 1, led_slit[1]]);
}
