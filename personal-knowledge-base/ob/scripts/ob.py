#!/usr/bin/env python3
"""Local Obsidian vault helper CLI.

This wraps a few common filesystem operations around the user's configured
Obsidian vault so agent workflows can treat the vault like a lightweight
knowledge-base backend.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "0.2.0"
DEFAULT_VAULT_NAME = "知识库"
OBSIDIAN_STATE = Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"
CONFIG_PATH = Path.home() / ".config" / "ob" / "config.json"
SKIP_DIRS = {".obsidian", ".trash"}


def fail(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_obsidian_vaults() -> dict:
    if not OBSIDIAN_STATE.exists():
        return {}
    data = load_json(OBSIDIAN_STATE)
    return data.get("vaults", {})


def get_config() -> dict:
    return load_json(CONFIG_PATH)


def resolve_vault() -> Path:
    env_path = os.environ.get("OB_VAULT_PATH")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if path.exists():
            return path
        fail(f"OB_VAULT_PATH does not exist: {path}")

    config = get_config()
    configured_path = config.get("vault_path")
    if configured_path:
        path = Path(configured_path).expanduser().resolve()
        if path.exists():
            return path

    vaults = load_obsidian_vaults()
    target_name = config.get("vault_name", DEFAULT_VAULT_NAME)
    matches = []
    for item in vaults.values():
        path = Path(item["path"]).expanduser().resolve()
        if path.name == target_name:
            matches.append(path)

    if len(matches) == 1:
        return matches[0]

    if not matches and len(vaults) == 1:
        item = next(iter(vaults.values()))
        return Path(item["path"]).expanduser().resolve()

    if matches:
        fail(f"Multiple vaults matched name {target_name!r}; set OB_VAULT_PATH or {CONFIG_PATH}.")

    fail(f"Could not resolve an Obsidian vault. Check {OBSIDIAN_STATE} or set {CONFIG_PATH}.")


def relative_target(vault: Path, raw_path: str) -> Path:
    rel = Path(raw_path)
    if rel.is_absolute():
        candidate = rel.resolve()
        try:
            candidate.relative_to(vault)
        except ValueError as exc:
            raise SystemExit(f"Path must stay inside vault: {candidate}") from exc
        return candidate
    return (vault / rel).resolve()


def normalize_file_path(path: Path) -> Path:
    if path.suffix:
        return path
    return path.with_suffix(".md")


def read_stdin_if_needed() -> str:
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read()


def get_content(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return Path(args.file).read_text(encoding="utf-8")
    if getattr(args, "content", None) is not None:
        return args.content
    stdin = read_stdin_if_needed()
    if stdin:
        return stdin
    fail("No content provided. Use --file, --content, or stdin.")


def print_data(data, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def walk_markdown_files(vault: Path):
    for path in vault.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def cmd_version(_: argparse.Namespace) -> None:
    print(VERSION)


def cmd_config_show(args: argparse.Namespace) -> None:
    data = {
        "config_path": str(CONFIG_PATH),
        "obsidian_state_path": str(OBSIDIAN_STATE),
        "config": get_config(),
        "resolved_vault_path": str(resolve_vault()),
    }
    print_data(data, args.json)


def cmd_config_set(args: argparse.Namespace) -> None:
    config = get_config()
    if args.vault_path:
        config["vault_path"] = str(Path(args.vault_path).expanduser().resolve())
    if args.vault_name:
        config["vault_name"] = args.vault_name
    save_json(CONFIG_PATH, config)
    print(json.dumps(config, ensure_ascii=False, indent=2))


def cmd_check(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    obsidian_ok = shutil.which("obsidian") is not None
    data = {
        "status": "ok",
        "vault_exists": vault.exists(),
        "vault_path": str(vault),
        "obsidian_cli_installed": obsidian_ok,
        "obsidian_state_path": str(OBSIDIAN_STATE),
    }
    print_data(data, args.json)


def cmd_vault_list(args: argparse.Namespace) -> None:
    current = str(resolve_vault())
    rows = []
    for item in load_obsidian_vaults().values():
        path = str(Path(item["path"]).expanduser().resolve())
        rows.append(
            {
                "path": path,
                "is_current": path == current,
                "open": bool(item.get("open")),
                "timestamp": item.get("ts"),
            }
        )
    print_data(rows, args.json)


def cmd_vault_current(args: argparse.Namespace) -> None:
    data = {"path": str(resolve_vault())}
    print_data(data, args.json)


def cmd_open(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    target = relative_target(vault, args.path) if args.path else vault
    if not target.exists():
        fail(f"Path does not exist: {target}")
    if shutil.which("obsidian"):
        subprocess.run(["obsidian", "open", str(vault)], check=True)
    else:
        subprocess.run(["open", "-a", "Obsidian", str(vault)], check=True)
    print(str(target))


def cmd_ls(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    target = relative_target(vault, args.path or "")
    if not target.exists():
        fail(f"Path not found: {target}")
    if target.is_file():
        items = [{
            "name": target.name,
            "type": "file",
            "path": str(target.relative_to(vault)),
        }]
    else:
        items = []
        for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if child.name in SKIP_DIRS:
                continue
            items.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "path": str(child.relative_to(vault)),
                }
            )
    if args.json:
        print_data(items, True)
    else:
        for item in items:
            prefix = "d" if item["type"] == "dir" else "f"
            print(f"{prefix}\t{item['path']}")


def cmd_read(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    target = normalize_file_path(relative_target(vault, args.path))
    if not target.exists():
        fail(f"File not found: {target}")
    content = target.read_text(encoding="utf-8")
    if args.json:
        print_data(
            {
                "path": str(target.relative_to(vault)),
                "absolute_path": str(target),
                "content": content,
            },
            True,
        )
    else:
        print(content)


def cmd_search(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    needle = args.query.lower()
    matches = []
    if shutil.which("rg"):
        cmd = [
            "rg",
            "-n",
            "--no-heading",
            "--color",
            "never",
            "--glob",
            "!.obsidian/**",
            "--glob",
            "*.md",
            args.query,
            str(vault),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode not in (0, 1):
            fail(proc.stderr.strip() or "rg search failed")
        for raw in proc.stdout.splitlines():
            match = re.match(r"^(.*?):(\d+):(.*)$", raw)
            if not match:
                continue
            path_str, line_no, text = match.groups()
            try:
                rel = str(Path(path_str).resolve().relative_to(vault))
            except ValueError:
                continue
            matches.append({"path": rel, "line": int(line_no), "text": text.strip()[:200]})

        file_cmd = [
            "rg",
            "--files",
            str(vault),
            "--glob",
            "!.obsidian/**",
            "--glob",
            "*.md",
        ]
        proc = subprocess.run(file_cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            seen_paths = {item["path"] for item in matches}
            for raw in proc.stdout.splitlines():
                path = Path(raw).resolve()
                try:
                    rel = str(path.relative_to(vault))
                except ValueError:
                    continue
                if needle in rel.lower() and rel not in seen_paths:
                    matches.append({"path": rel, "line": 0, "text": rel})
    else:
        for path in walk_markdown_files(vault):
            rel = str(path.relative_to(vault))
            text = path.read_text(encoding="utf-8")
            if needle in rel.lower():
                matches.append({"path": rel, "line": 0, "text": rel})
            for line_no, line in enumerate(text.splitlines(), start=1):
                if needle in line.lower():
                    matches.append({"path": rel, "line": line_no, "text": line.strip()[:200]})
    print_data(matches, args.json)


def write_file(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def cmd_mkdir(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    target = relative_target(vault, args.path)
    target.mkdir(parents=True, exist_ok=True)
    print(str(target))


def cmd_save(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    target = normalize_file_path(relative_target(vault, args.path))
    content = get_content(args)
    write_file(target, content)
    payload = {"path": str(target.relative_to(vault)), "absolute_path": str(target)}
    print_data(payload, args.json)


def cmd_update(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    target = normalize_file_path(relative_target(vault, args.path))
    if not target.exists():
        fail(f"File not found: {target}")
    content = get_content(args)
    write_file(target, content)
    payload = {"path": str(target.relative_to(vault)), "absolute_path": str(target)}
    print_data(payload, args.json)


def cmd_append(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    target = normalize_file_path(relative_target(vault, args.path))
    content = get_content(args)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(content)
    payload = {"path": str(target.relative_to(vault)), "absolute_path": str(target)}
    print_data(payload, args.json)


def cmd_mv(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    src = normalize_file_path(relative_target(vault, args.src))
    dst = normalize_file_path(relative_target(vault, args.dst))
    if not src.exists():
        fail(f"Source not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    print(json.dumps({"from": str(src.relative_to(vault)), "to": str(dst.relative_to(vault))}, ensure_ascii=False))


def cmd_rm(args: argparse.Namespace) -> None:
    vault = resolve_vault()
    target = relative_target(vault, args.path)
    if not target.exists():
        fail(f"Path not found: {target}")
    if target.is_dir():
        if not args.recursive:
            fail("Directory deletion requires --recursive.")
        shutil.rmtree(target)
    else:
        target.unlink()
    print(str(target))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ob")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("version")
    p.set_defaults(func=cmd_version)

    p = sub.add_parser("check")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("config")
    config_sub = p.add_subparsers(dest="config_command", required=True)
    show = config_sub.add_parser("show")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_config_show)
    setp = config_sub.add_parser("set")
    setp.add_argument("--vault-path")
    setp.add_argument("--vault-name")
    setp.set_defaults(func=cmd_config_set)

    p = sub.add_parser("vault")
    vault_sub = p.add_subparsers(dest="vault_command", required=True)
    ls = vault_sub.add_parser("list")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=cmd_vault_list)
    current = vault_sub.add_parser("current")
    current.add_argument("--json", action="store_true")
    current.set_defaults(func=cmd_vault_current)

    p = sub.add_parser("open")
    p.add_argument("path", nargs="?")
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("ls")
    p.add_argument("path", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ls)

    p = sub.add_parser("read")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("mkdir")
    p.add_argument("path")
    p.set_defaults(func=cmd_mkdir)

    for name, func in (("save", cmd_save), ("update", cmd_update), ("append", cmd_append)):
        p = sub.add_parser(name)
        p.add_argument("path")
        p.add_argument("--file")
        p.add_argument("--content")
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=func)

    p = sub.add_parser("mv")
    p.add_argument("src")
    p.add_argument("dst")
    p.set_defaults(func=cmd_mv)

    p = sub.add_parser("rm")
    p.add_argument("path")
    p.add_argument("--recursive", action="store_true")
    p.set_defaults(func=cmd_rm)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
