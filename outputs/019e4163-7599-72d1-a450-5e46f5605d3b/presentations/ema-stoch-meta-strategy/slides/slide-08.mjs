import { base, title, footer, box, C } from "./common.mjs";

export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  base(slide, ctx, "λειτουργία");
  title(slide, ctx, "Πώς πρέπει να διαβάζεται το πείραμα", "Η αξία είναι στον καθαρό διαχωρισμό σήματος, στόχου, μοντέλου και εκτέλεσης.");
  box(slide, ctx, {
    x: 72,
    y: 205,
    w: 510,
    h: 170,
    heading: "Τι σημαίνει επιτυχία",
    body: "Το meta-filter κρατά αρκετές πράξεις ώστε να υπάρχει εμπορεύσιμη δραστηριότητα και βελτιώνει την ποιότητα των candidates χωρίς να σπάει τη χρονική αιτιότητα.",
    fill: C.paleTeal,
    accent: C.teal,
  });
  box(slide, ctx, {
    x: 660,
    y: 205,
    w: 510,
    h: 170,
    heading: "Τι δεν αποδεικνύει μόνο του",
    body: "Δεν υπάρχει υπόσχεση κερδοφορίας από το config. Χρειάζεται πλήρες run, fold diagnostics, out-of-sample backtest και έλεγχος σταθερότητας.",
    fill: C.paleRed,
    accent: C.red,
  });
  box(slide, ctx, {
    x: 72,
    y: 430,
    w: 510,
    h: 150,
    heading: "Κύριες δικλίδες",
    body: "purged διαίρεση\nnext-open είσοδος\nPIT χειρισμός δεδομένων\nεξαιρέσεις χαρακτηριστικών\nαναπαραγώγιμη εκτέλεση",
    fill: C.paper,
    accent: C.blue,
  });
  box(slide, ctx, {
    x: 660,
    y: 430,
    w: 510,
    h: 150,
    heading: "Επόμενη χρήση",
    body: "τρέξιμο base config\nέλεγχος πυκνότητας υποψηφίων\nστενή αναζήτηση Optuna\nσύγκριση με ωμό κανόνα και προηγούμενες οικογένειες",
    fill: C.paleGold,
    accent: C.gold,
  });
  footer(slide, ctx, 8);
  return slide;
}
