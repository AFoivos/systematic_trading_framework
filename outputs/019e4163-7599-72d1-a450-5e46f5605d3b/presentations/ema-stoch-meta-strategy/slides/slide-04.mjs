import { base, title, footer, box, pill, C } from "./common.mjs";

export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  base(slide, ctx, "σήμα");
  title(slide, ctx, "Πώς γεννιέται η υποψήφια πράξη", "Το σήμα είναι κανόνας χρονισμού μέσα σε trend context.");
  ctx.addText(slide, { x: 88, y: 190, w: 450, h: 28, text: "Μακρά πλευρά", fontSize: 22, bold: true, color: C.blue });
  ctx.addText(slide, { x: 700, y: 190, w: 450, h: 28, text: "Βραχεία πλευρά", fontSize: 22, bold: true, color: C.red });
  box(slide, ctx, {
    x: 74,
    y: 235,
    w: 500,
    h: 220,
    heading: "Συνθήκες μακράς υποψηφιότητας",
    body: "EMA 50 περνά πάνω από EMA 150\nStochRSI γίνεται oversold μετά τη διασταύρωση\nΑνάκτηση από oversold\nΠροαιρετική επιβεβαίωση K > D\nΤιμή πάνω από αργό EMA",
    fill: C.paleBlue,
    accent: C.blue,
  });
  box(slide, ctx, {
    x: 668,
    y: 235,
    w: 500,
    h: 220,
    heading: "Συνθήκες βραχείας υποψηφιότητας",
    body: "EMA 50 περνά κάτω από EMA 150\nStochRSI γίνεται overbought μετά τη διασταύρωση\nΠτώση από overbought\nΠροαιρετική επιβεβαίωση K < D\nΤιμή κάτω από αργό EMA",
    fill: C.paleRed,
    accent: C.red,
  });
  pill(slide, ctx, 92, 502, 220, "signal_side = +1", C.paper, C.blue);
  pill(slide, ctx, 326, 502, 220, "signal_candidate = 1", C.paper, C.blue);
  pill(slide, ctx, 690, 502, 220, "signal_side = -1", C.paper, C.red);
  pill(slide, ctx, 924, 502, 220, "signal_candidate = 1", C.paper, C.red);
  ctx.addText(slide, {
    x: 176,
    y: 588,
    w: 890,
    h: 52,
    text: "Ο κανόνας χρησιμοποιεί τρέχουσες και προηγούμενες τιμές. Η είσοδος τιμολογείται αργότερα από το στρώμα στόχου και οπισθοελέγχου.",
    fontSize: 16,
    color: C.ink,
    align: "center",
  });
  footer(slide, ctx, 4);
  return slide;
}
