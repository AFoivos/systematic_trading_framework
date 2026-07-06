from __future__ import annotations

import argparse
import base64
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path("/workspace").resolve()
PROTECTED_NAMES = {".git"}
PROTECTED_SUFFIXES = {".pem", ".key"}
PROTECTED_FILENAMES = {".env", "id_rsa", "id_ed25519"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def decode_b64(value: str) -> str:
    try:
        return base64.b64decode(value.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        fail(f"Invalid base64 content: {exc}")


def resolve_repo_path(path: str) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        fail("Absolute paths are not allowed")

    resolved = (REPO_ROOT / raw).resolve()
    if resolved != REPO_ROOT and REPO_ROOT not in resolved.parents:
        fail(f"Path escapes repo root: {path}")

    rel_parts = resolved.relative_to(REPO_ROOT).parts
    if any(part in PROTECTED_NAMES for part in rel_parts):
        fail("Refusing to touch .git")

    name = resolved.name
    if name in PROTECTED_FILENAMES or name.startswith(".env.") or resolved.suffix in PROTECTED_SUFFIXES:
        fail(f"Refusing to touch protected/secret-looking file: {path}")

    return resolved


def write_file(path: str, content_b64: str, overwrite: bool) -> None:
    dst = resolve_repo_path(path)
    if dst.exists() and not overwrite:
        fail(f"File already exists: {path}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    content = decode_b64(content_b64)
    dst.write_text(content, encoding="utf-8")
    print({"ok": True, "operation": "write", "path": path, "bytes": len(content.encode("utf-8"))})


def append_file(path: str, content_b64: str) -> None:
    dst = resolve_repo_path(path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    content = decode_b64(content_b64)
    with dst.open("a", encoding="utf-8") as fh:
        fh.write(content)
    print({"ok": True, "operation": "append", "path": path, "bytes": len(content.encode("utf-8"))})


def replace_text(path: str, old_b64: str, new_b64: str, count: int) -> None:
    dst = resolve_repo_path(path)
    if not dst.exists():
        fail(f"File does not exist: {path}")

    text = dst.read_text(encoding="utf-8")
    old = decode_b64(old_b64)
    new = decode_b64(new_b64)

    if old not in text:
        fail("Old text not found")

    updated = text.replace(old, new, count if count >= 0 else text.count(old))
    dst.write_text(updated, encoding="utf-8")
    print({"ok": True, "operation": "replace", "path": path, "replacements": text.count(old) if count < 0 else min(text.count(old), count)})


def apply_patch(patch_b64: str) -> None:
    patch = decode_b64(patch_b64)

    protected_markers = [
        " /",
        "../",
        "a/.git",
        "b/.git",
        ".env",
        ".pem",
        ".key",
        "id_rsa",
        "id_ed25519",
    ]
    for marker in protected_markers:
        if marker in patch:
            fail(f"Patch contains protected marker: {marker}")

    proc = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        input=patch,
        text=True,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    if proc.returncode != 0:
        print(proc.stdout, file=sys.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)

    print({"ok": True, "operation": "apply_patch"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe repo write bridge for ChatGPT MCP.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write")
    p_write.add_argument("path")
    p_write.add_argument("content_b64")
    p_write.add_argument("--no-overwrite", action="store_true")

    p_append = sub.add_parser("append")
    p_append.add_argument("path")
    p_append.add_argument("content_b64")

    p_replace = sub.add_parser("replace")
    p_replace.add_argument("path")
    p_replace.add_argument("old_b64")
    p_replace.add_argument("new_b64")
    p_replace.add_argument("--count", type=int, default=1)

    p_patch = sub.add_parser("apply-patch")
    p_patch.add_argument("patch_b64")

    args = parser.parse_args()

    if args.cmd == "write":
        write_file(args.path, args.content_b64, overwrite=not args.no_overwrite)
    elif args.cmd == "append":
        append_file(args.path, args.content_b64)
    elif args.cmd == "replace":
        replace_text(args.path, args.old_b64, args.new_b64, args.count)
    elif args.cmd == "apply-patch":
        apply_patch(args.patch_b64)
    else:
        fail(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    main()
