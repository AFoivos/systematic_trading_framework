import { base, title, footer, flowBox, C } from "./common.mjs";

export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  base(slide, ctx, "αρχιτεκτονική");
  title(slide, ctx, "Η στρατηγική είναι στρωματοποιημένη", "Κάθε επίπεδο έχει διαφορετική ευθύνη και καθαρά όρια.");
  const y = 260;
  const w = 162;
  const h = 150;
  const xs = [70, 265, 460, 655, 850, 1045];
  flowBox(slide, ctx, xs[0], y, w, h, "Δεδομένα", "OHLCV με PIT κανόνες", C.paper, C.slate);
  flowBox(slide, ctx, xs[1], y, w, h, "Συμφραζόμενα", "ATR, VWAP, όγκος, ορμή, session", C.paleBlue, C.blue);
  flowBox(slide, ctx, xs[2], y, w, h, "Κανόνας", "EMA trend + StochRSI pullback", C.paleGold, C.gold);
  flowBox(slide, ctx, xs[3], y, w, h, "Μετα-στόχος", "τριπλό όριο και R", C.paleRed, C.red);
  flowBox(slide, ctx, xs[4], y, w, h, "Μοντέλο", "XGBoost πιθανότητα επιτυχίας", C.paleTeal, C.teal);
  flowBox(slide, ctx, xs[5], y, w, h, "Εκτέλεση", "ίδια πλευρά ή επίπεδη θέση", C.paper, C.green);
  for (const x of [235, 430, 625, 820, 1015]) {
    ctx.addShape(slide, { x, y: y + 74, w: 28, h: 2, fill: C.muted });
    ctx.addShape(slide, { x: x + 26, y: y + 69, w: 2, h: 12, fill: C.muted });
  }
  ctx.addShape(slide, { x: 160, y: 500, w: 920, h: 64, fill: C.ink });
  ctx.addText(slide, {
    x: 190,
    y: 516,
    w: 860,
    h: 48,
    text: "Ο τελικός κανόνας εισόδου δεν γίνεται χαρακτηριστικό πρόβλεψης. Μένει μόνο ως λειτουργική στήλη πλευράς και υποψηφιότητας.",
    fontSize: 19,
    bold: true,
    color: "#FFFFFF",
    align: "center",
  });
  footer(slide, ctx, 3);
  return slide;
}
