import { base, title, footer, box, callout, C } from "./common.mjs";

export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  base(slide, ctx, "στρατηγική");
  title(
    slide,
    ctx,
    "EMA + στοχαστικό μετα-φίλτρο",
    "Κανόνας για υποψήφιες πράξεις, μοντέλο για ποιοτικό φιλτράρισμα."
  );
  callout(
    slide,
    ctx,
    860,
    64,
    300,
    116,
    "Δεν προβλέπει κάθε μπάρα. Αξιολογεί μόνο υποψήφιες πράξεις.",
    C.paleTeal,
    C.teal
  );
  box(slide, ctx, {
    x: 74,
    y: 230,
    w: 330,
    h: 230,
    heading: "Τι κάνει ο κανόνας",
    body: "Εντοπίζει περιβάλλον τάσης με EMA 50 / EMA 150 και χρονίζει υποχώρηση με στοχαστικό RSI.",
    fill: C.paper,
    accent: C.blue,
  });
  box(slide, ctx, {
    x: 456,
    y: 230,
    w: 330,
    h: 230,
    heading: "Τι κάνει το μοντέλο",
    body: "Βαθμολογεί αν η υποψήφια πράξη αξίζει να εκτελεστεί, με βάση ATR, VWAP, όγκο, ορμή, καθεστώς και δομή.",
    fill: C.paper,
    accent: C.teal,
  });
  box(slide, ctx, {
    x: 838,
    y: 230,
    w: 330,
    h: 230,
    heading: "Τι αποφεύγει",
    body: "Δεν δίνει στο μοντέλο το τελικό flag εισόδου ως χαρακτηριστικό, ώστε να μη μάθει μηχανικά τον κανόνα.",
    fill: C.paper,
    accent: C.red,
  });
  ctx.addText(slide, {
    x: 78,
    y: 522,
    w: 980,
    h: 54,
    text: "Θέση της στρατηγικής: αιτιατή και ελέγξιμη μετα-ετικετοποίηση για επιλογή πράξεων, όχι γενικός προβλέπτης κατεύθυνσης.",
    fontSize: 22,
    bold: true,
    color: C.ink,
  });
  footer(slide, ctx, 1);
  return slide;
}
