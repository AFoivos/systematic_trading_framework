from __future__ import annotations

import ast
import html
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

ROOT = Path('.')
OUTPUT_DIR = ROOT / 'output' / 'pdf'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PDF = OUTPUT_DIR / 'systematic_trading_framework_code_reference.pdf'

EXCLUDE_DIRS = {'.git', 'notebooks', 'tmp', 'venv', '__pycache__'}
EXCLUDE_NAMES = {'.DS_Store'}


def list_files() -> list[Path]:
    files: list[Path] = []
    for p in ROOT.rglob('*'):
        if p.is_dir():
            continue
        rel = p.relative_to(ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if rel.name in EXCLUDE_NAMES:
            continue
        if rel == OUTPUT_PDF.relative_to(ROOT):
            # avoid self-reference if rerun
            continue
        files.append(rel)
    return sorted(files)


def workflow_role_for_path(rel: Path) -> str:
    path = rel.as_posix()
    if path.startswith('src/data'):
        return 'Data ingestion and validation'
    if path.startswith('src/features'):
        return 'Feature engineering'
    if path.startswith('src/signals'):
        return 'Signal generation and transformation'
    if path.startswith('src/backtesting'):
        return 'Backtesting and performance accounting'
    if path.startswith('src/risk'):
        return 'Risk controls and position sizing'
    if path.startswith('src/experiments'):
        return 'Experiment orchestration and model integration'
    if path.startswith('src/models'):
        return 'Model implementations'
    if path.startswith('src/utils'):
        return 'Utilities and infrastructure'
    if path.startswith('src/evaluation'):
        return 'Evaluation and reporting (minimal stub)'
    if path.startswith('config/'):
        return 'Experiment configuration'
    if path.startswith('tests/'):
        return 'Testing and verification'
    if path == 'README.md':
        return 'Project overview and usage guide'
    if path == 'requirements.txt':
        return 'Python dependencies'
    if path in {'.gitignore', '.gitattributes'}:
        return 'Repository hygiene and git configuration'
    if path.endswith('.gitkeep'):
        return 'Repository structure placeholder'
    if path.startswith('logs/'):
        return 'Run artifacts (backtest outputs)'
    if path.startswith('output/'):
        return 'Generated artifacts'
    if path.startswith('plots/'):
        return 'Generated plots'
    return 'Misc'


def get_imports(tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ''
            imports.append(mod)
    return sorted({i for i in imports if i})


def format_signature(func: ast.FunctionDef) -> str:
    args = []
    for a in func.args.args:
        args.append(a.arg)
    if func.args.vararg:
        args.append('*' + func.args.vararg.arg)
    for a in func.args.kwonlyargs:
        args.append(a.arg)
    if func.args.kwarg:
        args.append('**' + func.args.kwarg.arg)
    return f"{func.name}({', '.join(args)})"


def first_paragraph(doc: str | None, max_chars: int = 600) -> str:
    if not doc:
        return ''
    text = doc.strip().replace('\r\n', '\n')
    # take first paragraph
    para = text.split('\n\n')[0]
    if len(para) > max_chars:
        para = para[:max_chars].rsplit(' ', 1)[0] + '...'
    return para


def infer_description(name: str) -> str:
    lname = name.lower()
    if lname.startswith('compute_'):
        return 'Computes a derived series or metric from inputs.'
    if lname.startswith('add_'):
        return 'Adds derived features or columns to a DataFrame.'
    if lname.startswith('load_'):
        return 'Loads data from a configured source and returns a normalized structure.'
    if lname.startswith('validate_'):
        return 'Validates input data integrity and raises on violations.'
    if lname.startswith('run_'):
        return 'Runs a pipeline or process end to end.'
    if lname.startswith('train_'):
        return 'Trains a model or creates a fitted estimator.'
    if lname.startswith('predict_'):
        return 'Generates predictions from a fitted model.'
    if lname.endswith('_signal') or 'signal' in lname:
        return 'Creates or transforms a trading signal.'
    if lname.endswith('_config'):
        return 'Defines a configuration container for model parameters.'
    return 'Utility or helper function.'


def summarize_python_file(rel: Path, content: str) -> dict:
    tree = ast.parse(content)
    imports = get_imports(tree)
    items = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node)
            items.append({
                'kind': 'class',
                'name': node.name,
                'signature': node.name,
                'doc': first_paragraph(doc) or f"No docstring. Inferred purpose: {infer_description(node.name)}",
                'methods': [n for n in node.body if isinstance(n, ast.FunctionDef)],
            })
        elif isinstance(node, ast.FunctionDef):
            doc = ast.get_docstring(node)
            items.append({
                'kind': 'function',
                'name': node.name,
                'signature': format_signature(node),
                'doc': first_paragraph(doc) or f"No docstring. Inferred purpose: {infer_description(node.name)}",
            })
    return {'imports': imports, 'items': items}


def top_level_keys_from_yaml(text: str) -> list[str]:
    keys: list[str] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line.startswith(' ') or line.startswith('\t'):
            continue
        if ':' in line:
            key = line.split(':', 1)[0].strip()
            if key:
                keys.append(key)
    return sorted(set(keys))


def escape(s: str) -> str:
    return html.escape(s, quote=False)


def main() -> None:
    files = list_files()

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='H1', parent=styles['Heading1'], spaceAfter=12))
    styles.add(ParagraphStyle(name='H2', parent=styles['Heading2'], spaceAfter=6))
    styles.add(ParagraphStyle(name='H3', parent=styles['Heading3'], spaceAfter=4))
    styles.add(ParagraphStyle(name='Body', parent=styles['BodyText'], leading=12))
    styles.add(ParagraphStyle(name='Mono', parent=styles['BodyText'], fontName='Courier', leading=11))

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title='Systematic Trading Framework - Code Reference',
        author='Codex',
    )

    story = []

    story.append(Paragraph('Systematic Trading Framework - Code Reference', styles['H1']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d')} (local)", styles['Body']))
    story.append(Spacer(1, 8))
    story.append(Paragraph('Scope', styles['H2']))
    story.append(Paragraph(
        'This document explains each non-notebook file in the repository, with a focus on code files. '
        'For Python modules, it documents every top-level def and class, plus methods inside classes, '
        'and describes where each file sits in the project workflow. Notebooks are excluded by request.',
        styles['Body'],
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph('Workflow Overview', styles['H2']))
    story.append(Paragraph(
        'Data ingestion and validation -> Feature engineering -> Modeling -> Signal generation -> '
        'Backtesting -> Evaluation -> Logging and diagnostics. Utilities and configs support the pipeline.',
        styles['Body'],
    ))
    story.append(PageBreak())

    for rel in files:
        path_str = rel.as_posix()
        role = workflow_role_for_path(rel)
        story.append(Paragraph(f"File: {escape(path_str)}", styles['H2']))
        story.append(Paragraph(f"Workflow role: {escape(role)}", styles['Body']))

        full_path = ROOT / rel
        suffix = rel.suffix.lower()

        if suffix == '.py':
            content = full_path.read_text(encoding='utf-8')
            summary = summarize_python_file(rel, content)
            if summary['imports']:
                story.append(Paragraph('Imports:', styles['H3']))
                story.append(Paragraph(escape(', '.join(summary['imports'])), styles['Body']))
            if not summary['items']:
                story.append(Paragraph('No top-level defs or classes.', styles['Body']))
            else:
                story.append(Paragraph('Definitions:', styles['H3']))
                for item in summary['items']:
                    if item['kind'] == 'class':
                        story.append(Paragraph(f"Class: {escape(item['signature'])}", styles['Mono']))
                        story.append(Paragraph(escape(item['doc']), styles['Body']))
                        # methods
                        methods = item.get('methods', [])
                        for m in methods:
                            m_doc = first_paragraph(ast.get_docstring(m)) or f"No docstring. Inferred purpose: {infer_description(m.name)}"
                            story.append(Paragraph(f"Method: {escape(format_signature(m))}", styles['Mono']))
                            story.append(Paragraph(escape(m_doc), styles['Body']))
                    else:
                        story.append(Paragraph(f"Function: {escape(item['signature'])}", styles['Mono']))
                        story.append(Paragraph(escape(item['doc']), styles['Body']))
        elif suffix in {'.yaml', '.yml'}:
            text = full_path.read_text(encoding='utf-8')
            keys = top_level_keys_from_yaml(text)
            story.append(Paragraph('Type: YAML configuration', styles['Body']))
            if keys:
                story.append(Paragraph('Top-level keys: ' + escape(', '.join(keys)), styles['Body']))
            else:
                story.append(Paragraph('Empty or placeholder YAML.', styles['Body']))
        elif suffix == '.json':
            import json
            story.append(Paragraph('Type: JSON artifact', styles['Body']))
            try:
                data = json.loads(full_path.read_text(encoding='utf-8'))
                story.append(Paragraph('Top-level keys: ' + escape(', '.join(sorted(data.keys()))), styles['Body']))
            except Exception:
                story.append(Paragraph('Unreadable JSON or non-standard content.', styles['Body']))
        elif suffix == '.csv':
            story.append(Paragraph('Type: CSV artifact', styles['Body']))
            try:
                first_line = full_path.read_text(encoding='utf-8').splitlines()[0]
                story.append(Paragraph('Header: ' + escape(first_line), styles['Body']))
            except Exception:
                story.append(Paragraph('Unreadable CSV or empty file.', styles['Body']))
        elif suffix == '.md':
            story.append(Paragraph('Type: Markdown documentation', styles['Body']))
        elif suffix in {'.png', '.pdf'}:
            story.append(Paragraph('Type: binary artifact (image or PDF).', styles['Body']))
            story.append(Paragraph('Not parsed for code. Included as generated output.', styles['Body']))
        else:
            story.append(Paragraph('Type: text or metadata file.', styles['Body']))

        story.append(Spacer(1, 10))

    doc.build(story)


if __name__ == '__main__':
    main()
