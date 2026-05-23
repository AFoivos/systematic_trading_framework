import { base, title, footer, box, C } from "./common.mjs";

export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  base(slide, ctx, "βελτιστοποίηση");
  title(slide, ctx, "Η βελτιστοποίηση μένει εντός στρατηγικής", "Ο χώρος αναζήτησης αλλάζει μόνο παραμέτρους που έχουν πραγματική υπόθεση.");
  box(slide, ctx, {
    x: 72,
    y: 210,
    w: 340,
    h: 260,
    heading: "Παράμετροι σήματος",
    body: "oversold / overbought\nmax_bars_after_cross\nεπιβεβαίωση K/D\nμόνο πρώτη υποχώρηση",
    fill: C.paleGold,
    accent: C.gold,
  });
  box(slide, ctx, {
    x: 452,
    y: 210,
    w: 340,
    h: 260,
    heading: "Παράμετροι στόχου",
    body: "upper_mult / lower_mult\nmax_holding\nvol_window\nR-compatible diagnostics",
    fill: C.paleRed,
    accent: C.red,
  });
  box(slide, ctx, {
    x: 832,
    y: 210,
    w: 340,
    h: 260,
    heading: "Παράμετροι μοντέλου",
    body: "n_estimators\nlearning_rate\nmax_depth\nregularization\nprobability threshold",
    fill: C.paleTeal,
    accent: C.teal,
  });
  ctx.addText(slide, {
    x: 112,
    y: 545,
    w: 1020,
    h: 58,
    text: "Δεν εισάγει άσχετες διαστάσεις αναζήτησης. Αλλάζει μόνο σημεία που αντιστοιχούν σε πραγματική στρατηγική υπόθεση.",
    fontSize: 18,
    bold: true,
    color: C.ink,
    align: "center",
  });
  footer(slide, ctx, 7);
  return slide;
}
