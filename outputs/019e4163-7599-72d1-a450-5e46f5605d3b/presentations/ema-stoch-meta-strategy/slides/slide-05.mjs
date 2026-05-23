import { base, title, footer, box, pill, C } from "./common.mjs";

export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  base(slide, ctx, "μετα-μοντέλο");
  title(slide, ctx, "Το μοντέλο βλέπει περιβάλλον", "Η πρόβλεψη είναι P(υποψήφια πράξη πετυχαίνει), όχι P(τιμή ανεβαίνει).");
  const families = [
    ["Μεταβλητότητα", "vol_rolling_24 / 48\nATR και ATR / τιμή", C.paleBlue, C.blue],
    ["Όγκος", "volume_z_20\nvolume_over_atr_24", C.paleTeal, C.teal],
    ["VWAP", "vwap_20\nclose_over_vwap_20", C.paleGold, C.gold],
    ["Ορμή", "roc_6 / 12 / 24\nlagged returns", C.paper, C.slate],
    ["Χρόνος", "ώρα, ημέρα\nsession context", C.paleGreen, C.green],
    ["Δομή", "swing context\nrange position", C.paper, C.blue],
  ];
  let x = 72;
  let y = 205;
  families.forEach((f, i) => {
    box(slide, ctx, { x, y, w: 340, h: 132, heading: f[0], body: f[1], fill: f[2], accent: f[3] });
    x += 382;
    if (i === 2) {
      x = 72;
      y = 370;
    }
  });
  ctx.addShape(slide, { x: 70, y: 552, w: 510, h: 62, fill: C.paleRed, line: ctx.line(C.red, 1.2) });
  ctx.addText(slide, { x: 94, y: 562, w: 462, h: 44, text: "Εξαιρούνται: signal_candidate, signal_side, τελικές είσοδοι, ετικέτες, προβλέψεις.", fontSize: 15, bold: true, color: C.ink, align: "center" });
  ctx.addShape(slide, { x: 662, y: 552, w: 506, h: 62, fill: C.paleTeal, line: ctx.line(C.teal, 1.2) });
  ctx.addText(slide, { x: 690, y: 562, w: 450, h: 44, text: "Παραμένουν: αποστάσεις EMA, κλίσεις, μπάρες από διασταύρωση, K/D spread και συμφραζόμενα.", fontSize: 15, bold: true, color: C.ink, align: "center" });
  footer(slide, ctx, 5);
  return slide;
}
