export const C = {
  bg: "#F7F4EF",
  paper: "#FFFFFF",
  ink: "#14213D",
  muted: "#5E6472",
  line: "#D7D1C7",
  teal: "#1B998B",
  blue: "#33658A",
  red: "#C44536",
  gold: "#E09F3E",
  green: "#2A9D8F",
  slate: "#283845",
  paleTeal: "#DDF0EC",
  paleBlue: "#E2ECF4",
  paleGold: "#F8E7C6",
  paleRed: "#F3D8D2",
  paleGreen: "#DCEFEA",
};

export function base(slide, ctx, section = "") {
  ctx.addShape(slide, { x: 0, y: 0, w: ctx.W, h: ctx.H, fill: C.bg });
  ctx.addShape(slide, { x: 0, y: 0, w: 18, h: ctx.H, fill: C.ink });
  ctx.addShape(slide, { x: 18, y: 0, w: 5, h: ctx.H, fill: C.teal });
  if (section) {
    ctx.addText(slide, {
      x: 56,
      y: 26,
      w: 520,
      h: 18,
      text: section.toUpperCase(),
      fontSize: 13,
      bold: true,
      color: C.teal,
      typeface: ctx.fonts.body,
    });
  }
}

export function title(slide, ctx, text, sub = "") {
  ctx.addText(slide, {
    x: 56,
    y: 54,
    w: 780,
    h: 92,
    text,
    fontSize: 36,
    bold: true,
    color: C.ink,
    typeface: ctx.fonts.title,
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });
  if (sub) {
    ctx.addText(slide, {
      x: 58,
      y: 148,
      w: 760,
      h: 42,
      text: sub,
      fontSize: 18,
      color: C.muted,
      typeface: ctx.fonts.body,
      insets: { left: 0, right: 0, top: 0, bottom: 0 },
    });
  }
}

export function footer(slide, ctx, n, label = "EMA + στοχαστικό μετα-φίλτρο") {
  ctx.addShape(slide, { x: 56, y: 674, w: 1110, h: 1, fill: C.line });
  ctx.addText(slide, {
    x: 56,
    y: 685,
    w: 760,
    h: 18,
    text: label,
    fontSize: 10,
    color: C.muted,
  });
  ctx.addText(slide, {
    x: 1110,
    y: 685,
    w: 90,
    h: 18,
    text: String(n).padStart(2, "0"),
    fontSize: 10,
    color: C.muted,
    align: "right",
  });
}

export function box(slide, ctx, { x, y, w, h, heading, body, fill = C.paper, stroke = C.line, accent = C.teal }) {
  ctx.addShape(slide, { x, y, w, h, fill, line: ctx.line(stroke, 1) });
  ctx.addShape(slide, { x, y, w: 6, h, fill: accent });
  ctx.addText(slide, {
    x: x + 18,
    y: y + 16,
    w: w - 30,
    h: 28,
    text: heading,
    fontSize: 18,
    bold: true,
    color: C.ink,
  });
  ctx.addText(slide, {
    x: x + 18,
    y: y + 52,
    w: w - 30,
    h: h - 62,
    text: body,
    fontSize: 13,
    color: C.slate,
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

export function pill(slide, ctx, x, y, w, text, fill = C.paleTeal, color = C.ink) {
  ctx.addShape(slide, { x, y, w, h: 34, fill, line: ctx.line(C.line, 0.8) });
  ctx.addText(slide, {
    x: x + 10,
    y: y + 8,
    w: w - 20,
    h: 18,
    text,
    fontSize: 12,
    bold: true,
    color,
    align: "center",
  });
}

export function small(slide, ctx, x, y, w, text, color = C.muted) {
  ctx.addText(slide, {
    x,
    y,
    w,
    h: 34,
    text,
    fontSize: 11,
    color,
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

export function flowBox(slide, ctx, x, y, w, h, top, bottom, fill, accent) {
  ctx.addShape(slide, { x, y, w, h, fill, line: ctx.line(C.line, 1) });
  ctx.addShape(slide, { x, y, w, h: 8, fill: accent });
  ctx.addText(slide, { x: x + 12, y: y + 20, w: w - 24, h: 28, text: top, fontSize: 15, bold: true, color: C.ink, align: "center" });
  ctx.addText(slide, { x: x + 10, y: y + 54, w: w - 20, h: h - 58, text: bottom, fontSize: 10.5, color: C.slate, align: "center" });
}

export function arrow(slide, ctx, x, y, text = "→") {
  ctx.addText(slide, { x, y, w: 42, h: 34, text, fontSize: 28, bold: true, color: C.muted, align: "center" });
}

export function callout(slide, ctx, x, y, w, h, text, fill = C.paleGold, accent = C.gold) {
  ctx.addShape(slide, { x, y, w, h, fill, line: ctx.line(accent, 1.2) });
  ctx.addText(slide, { x: x + 18, y: y + 16, w: w - 36, h: h - 28, text, fontSize: 17, bold: true, color: C.ink, align: "center" });
}
