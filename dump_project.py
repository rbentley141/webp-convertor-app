#!/usr/bin/env python3
"""
dump_project.py

Creates a ChatGPT-friendly project dump:
- Prints a directory tree (excluding .venv, __pycache__, *.egg-info, etc.)
- Includes contents of ONLY .py files (skips binaries like .onnx)
- Writes to a single output file at the repo root by default

Usage:
  python dump_project.py
  python dump_project.py --root . --out project_dump.txt --max-bytes 200000
"""

from __future__ import annotations
import argparse
import os
from pathlib import Path

EXCLUDE_DIRS_DEFAULT = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".cache",
    "dist",
    "build",
    "node_modules",
    ".eggs",
    "old",
}
EXCLUDE_SUFFIXES_DEFAULT = {
    ".egg-info",
}
EXCLUDE_FILES_DEFAULT = {
    ".DS_Store",
    "dump_project.py",
}

# Binary / unreadable or “do not include” extensions
SKIP_EXTS_DEFAULT = {
    ".onnx",
    ".pt",
    ".pth",
    ".pkl",
    ".pickle",
    ".npz",
    ".npy",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".bin",
    ".dat",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".pdf",
    ".mp4",
    ".mov",
    ".avi",
    ".wav",
    ".mp3",
}


def is_excluded_dir(path: Path, exclude_dirs: set[str], exclude_suffixes: set[str]) -> bool:
    name = path.name
    if name in exclude_dirs:
        return True
    for suf in exclude_suffixes:
        if name.endswith(suf):
            return True
    return False


def safe_read_text(path: Path, max_bytes: int) -> tuple[str, bool]:
    """
    Returns (text, truncated)
    Reads file as UTF-8 with replacement; caps at max_bytes.
    """
    data = path.read_bytes()
    truncated = False
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True
    text = data.decode("utf-8", errors="replace")
    return text, truncated


def render_ascii_tree(
    root: Path,
    exclude_dirs: set[str],
    exclude_suffixes: set[str],
    exclude_files: set[str],
) -> str:
    """
    Renders an ASCII tree similar to `tree`, with exclusions applied.
    """
    lines: list[str] = [str(root.name) + "/"]

    def list_dir(d: Path) -> tuple[list[Path], list[Path]]:
        try:
            entries = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return [], []

        dirs: list[Path] = []
        files: list[Path] = []
        for p in entries:
            if p.is_dir():
                if is_excluded_dir(p, exclude_dirs, exclude_suffixes):
                    continue
                dirs.append(p)
            else:
                if p.name in exclude_files:
                    continue
                files.append(p)
        return dirs, files

    def walk_dir(d: Path, prefix: str = "") -> None:
        dirs, files = list_dir(d)
        entries = dirs + files
        for i, p in enumerate(entries):
            last = i == len(entries) - 1
            connector = "└── " if last else "├── "
            if p.is_dir():
                lines.append(prefix + connector + p.name + "/")
                extension_prefix = "    " if last else "│   "
                walk_dir(p, prefix + extension_prefix)
            else:
                lines.append(prefix + connector + p.name)

    walk_dir(root)
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Dump project structure + .py contents for ChatGPT.")
    ap.add_argument("--root", type=Path, default=Path("."), help="Project root (default: .)")
    ap.add_argument("--out", type=Path, default=Path("project_dump.txt"), help="Output file (default: project_dump.txt)")
    ap.add_argument("--max-bytes", type=int, default=200_000, help="Max bytes per file (default: 200000)")
    ap.add_argument(
        "--include-nonpy-names",
        action="store_true",
        help="Also list non-.py filenames in the file list (contents still only for .py).",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    out = (root / args.out) if not args.out.is_absolute() else args.out

    exclude_dirs = set(EXCLUDE_DIRS_DEFAULT)
    exclude_suffixes = set(EXCLUDE_SUFFIXES_DEFAULT)
    exclude_files = set(EXCLUDE_FILES_DEFAULT)
    skip_exts = set(SKIP_EXTS_DEFAULT)

    # Exclude this script and the output file explicitly
    self_path = Path(__file__).resolve()
    exclude_files.add(self_path.name)
    exclude_files.add(out.name)

    tree_str = render_ascii_tree(root, exclude_dirs, exclude_suffixes, exclude_files)

    py_files: list[Path] = []
    other_files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not is_excluded_dir(dp / d, exclude_dirs, exclude_suffixes)]
        for fn in filenames:
            if fn in exclude_files:
                continue
            p = dp / fn
            if p.suffix.lower() in skip_exts:
                continue
            if p.suffix.lower() == ".py" or p.suffix.lower() == ".toml" or p.suffix.lower() == ".sh":
                py_files.append(p)
            else:
                other_files.append(p)

    # If the script lives inside root (it does in your case), double-protect against it
    py_files = [p for p in py_files if p.resolve() != self_path]

    py_files.sort(key=lambda p: str(p.relative_to(root)))
    other_files.sort(key=lambda p: str(p.relative_to(root)))

    with out.open("w", encoding="utf-8") as f:
        f.write("# PROJECT DUMP FOR CHATGPT\n\n")
        f.write("## Directory tree\n\n```text\n")
        f.write(tree_str)
        f.write("```\n\n")

        f.write("## Files included\n\n")
        f.write("### Python files (.py) (contents included)\n\n")
        for p in py_files:
            f.write(f"- {p.relative_to(root)}\n")
        f.write("\n")

        if args.include_nonpy_names:
            f.write("### Other files (names only; contents excluded)\n\n")
            for p in other_files:
                f.write(f"- {p.relative_to(root)}\n")
            f.write("\n")

        f.write("## Python file contents\n\n")
        for p in py_files:
            rel = p.relative_to(root)
            f.write(f"### {rel}\n\n```python\n")
            try:
                text, truncated = safe_read_text(p, args.max_bytes)
                f.write(text)
                if not text.endswith("\n"):
                    f.write("\n")
                if truncated:
                    f.write("\n# [TRUNCATED: file exceeded max-bytes]\n")
            except Exception as e:
                f.write(f"# [ERROR READING FILE: {e}]\n")
            f.write("```\n\n")

    print(f"Wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
