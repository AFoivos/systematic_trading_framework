import { base, title, footer, box, arrow, C } from "./common.mjs";

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  base(slide, ctx, "στόχος");
  title(slide, ctx, "Ο στόχος μετρά αν η πράξη άξιζε το ρίσκο", "Μετα-ετικετοποίηση τριπλού ορίου με next-open είσοδο και R diagnostics.");
  const y = 270;
  box(slide, ctx, { x: 80, y, w: 250, h: 150, heading: "t: σήμα", body: "Ο κανόνας παράγει side και candidate στο κλείσιμο της μπάρας.", fill: C.paper, accent: C.blue });
  arrow(slide, ctx, 350, y + 52);
  box(slide, ctx, { x: 400, y, w: 250, h: 150, heading: "t+1: είσοδος", body: "Η τιμή εισόδου είναι το επόμενο open, όχι το ίδιο close.", fill: C.paleGold, accent: C.gold });
  arrow(slide, ctx, 670, y + 52);
  box(slide, ctx, { x: 720, y, w: 250, h: 150, heading: "ορίζοντας", body: "Άνω όριο, κάτω όριο ή κάθετο όριο max_holding.", fill: C.paleRed, accent: C.red });
  arrow(slide, ctx, 990, y + 52);
  ctx.addShape(slide, { x: 1040, y, w: 150, h: 150, fill: C.paleTeal, line: ctx.line(C.line, 1) });
  ctx.addShape(slide, { x: 1040, y, w: 6, h: 150, fill: C.teal });
  ctx.addText(slide, { x: 1058, y: y + 16, w: 120, h: 28, text: "label", fontSize: 18, bold: true, color: C.ink });
  ctx.addText(slide, { x: 1058, y: y + 58, w: 120, h: 48, text: "1 = profit\n0 = stop", fontSize: 13, color: C.slate, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
  ctx.addShape(slide, { x: 128, y: 490, w: 980, h: 74, fill: C.ink, line: ctx.line(C.ink, 1) });
  ctx.addText(slide, { x: 176, y: 504, w: 885, h: 48, text: "Η μεταβλητότητα και η απόσταση stop λαμβάνονται από πληροφορία διαθέσιμη στη στιγμή του γεγονότος εισόδου.", fontSize: 18, bold: true, color: "#FFFFFF", align: "center" });
  footer(slide, ctx, 6);
  return slide;
}
