from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted

ROOT = Path('.')
OUTPUT_BASE = ROOT / 'output' / 'pdf' / 'files'
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {'.git', 'venv', 'notebooks', '__pycache__'}
EXCLUDE_FILES = {'requirements.txt'}


def should_exclude(rel: Path) -> bool:
    if rel.name in EXCLUDE_FILES:
        return True
    parts = rel.parts
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    # avoid exporting generated PDFs to prevent recursion
    if len(parts) >= 2 and parts[0] == 'output' and parts[1] == 'pdf':
        return True
    if len(parts) >= 2 and parts[0] == 'tmp' and parts[1] == 'pdfs':
        return True
    return False


def list_files() -> list[Path]:
    files: list[Path] = []
    for p in ROOT.rglob('*'):
        if p.is_dir():
            continue
        rel = p.relative_to(ROOT)
        if should_exclude(rel):
            continue
        files.append(rel)
    return sorted(files)


def is_text_file(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except Exception:
        return False
    if b'\x00' in data:
        return False
    try:
        data.decode('utf-8')
        return True
    except Exception:
        return False


def wrap_text(text: str, width: int = 110) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.replace('\t', '    ')
        if len(line) <= width:
            lines.append(line)
            continue
        indent = len(line) - len(line.lstrip(' '))
        base = line.lstrip(' ')
        avail = max(width - indent, 10)
        wrapped = textwrap.wrap(
            base,
            width=avail,
            break_long_words=True,
            break_on_hyphens=False,
        )
        if not wrapped:
            lines.append(line)
        else:
            for w in wrapped:
                lines.append((' ' * indent) + w)
    return '\n'.join(lines)


def sha256_hex(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def build_pdf_for_file(rel: Path) -> None:
    src_path = ROOT / rel
    out_dir = OUTPUT_BASE / rel.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{rel.name}.pdf"

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='FileTitle', parent=styles['Heading1'], spaceAfter=12))
    styles.add(ParagraphStyle(name='Body', parent=styles['BodyText'], leading=12))
    styles.add(ParagraphStyle(name='Mono', parent=styles['BodyText'], fontName='Courier', fontSize=8, leading=9))

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=str(rel),
        author='Codex',
    )

    story = []
    story.append(Paragraph(f"File: {rel.as_posix()}", styles['FileTitle']))
    try:
        size = src_path.stat().st_size
    except Exception:
        size = 0
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d')} (local)", styles['Body']))
    story.append(Paragraph(f"Size: {size} bytes", styles['Body']))
    story.append(Spacer(1, 8))

    if is_text_file(src_path):
        text = src_path.read_text(encoding='utf-8', errors='replace')
        text = wrap_text(text, width=110)
        if not text.strip():
            text = '[empty file]'
        story.append(Preformatted(text, styles['Mono']))
    else:
        digest = sha256_hex(src_path)
        story.append(Paragraph('Binary file (not rendered as text).', styles['Body']))
        story.append(Paragraph(f"SHA256: {digest}", styles['Body']))

    doc.build(story)


def main() -> None:
    files = list_files()
    for rel in files:
        build_pdf_for_file(rel)


if __name__ == '__main__':
    main()
