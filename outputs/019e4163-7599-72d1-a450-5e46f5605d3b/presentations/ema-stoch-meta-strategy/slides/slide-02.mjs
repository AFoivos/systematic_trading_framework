import { base, title, footer, box, C } from "./common.mjs";

export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  base(slide, ctx, "σκοπός");
  title(slide, ctx, "Πού αποσκοπεί", "Να ξεχωρίσει ποιες τεχνικά εύλογες πράξεις αξίζουν έκθεση.");
  box(slide, ctx, {
    x: 80,
    y: 205,
    w: 330,
    h: 275,
    heading: "1. Καθαρό σύμπαν γεγονότων",
    body: "Το μοντέλο εκπαιδεύεται μόνο σε στιγμές όπου ο κανόνας δημιούργησε υποψήφια πράξη. Έτσι το πρόβλημα είναι ποιότητα πράξης, όχι γενική πρόβλεψη τιμής.",
    fill: C.paleBlue,
    accent: C.blue,
  });
  box(slide, ctx, {
    x: 455,
    y: 205,
    w: 330,
    h: 275,
    heading: "2. Μείωση κακών εκτελέσεων",
    body: "Το μετα-φίλτρο κόβει υποψήφιες πράξεις όταν το περιβάλλον μεταβλητότητας, όγκου, ορμής ή δομής δεν ευνοεί το setup.",
    fill: C.paleTeal,
    accent: C.teal,
  });
  box(slide, ctx, {
    x: 830,
    y: 205,
    w: 330,
    h: 275,
    heading: "3. Αναπαραγωγιμότητα",
    body: "Η ροή κρατά σταθερό seed, purged διαίρεση, point-in-time χαρακτηριστικά και next-open είσοδο για να μην κρύβεται lookahead.",
    fill: C.paleGold,
    accent: C.gold,
  });
  ctx.addShape(slide, { x: 80, y: 540, w: 1080, h: 62, fill: C.ink });
  ctx.addText(slide, {
    x: 110,
    y: 556,
    w: 1020,
    h: 30,
    text: "Κεντρική θέση: ο κανόνας παράγει ευκαιρίες, το μοντέλο αποφασίζει αν το περιβάλλον αξίζει ρίσκο.",
    fontSize: 20,
    bold: true,
    color: "#FFFFFF",
    align: "center",
  });
  footer(slide, ctx, 2);
  return slide;
}
