#!/usr/bin/env python3
"""Install one shared skill and opt-in rules, or initialize project knowledge."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import sys
import tempfile


SKILL_NAME = "code-design-planner"
RELEASE_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/planner.md",
    "references/reviewer.md",
    "references/integrations.md",
    "assets/design-template.md",
    "assets/project-agents.md",
    "assets/global-agents.md",
)
BEGIN = "<!-- BEGIN code-design-planner -->"
END = "<!-- END code-design-planner -->"
SOURCE_ROOT = Path(__file__).resolve().parent.parent


class InstallError(Exception):
    """An expected validation error, before any planned writes."""


def absolute_path(value: str | Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def check_path(path: Path, *, directory: bool = False) -> None:
    """Reject symlinks and wrong types throughout a destination's ancestry.

    macOS's system-owned /var and /tmp aliases are accepted so standard
    temporary directories work. User-created symlinks remain disallowed.
    """
    aliases = {Path("/var"): Path("/private/var"), Path("/tmp"): Path("/private/tmp")}
    for component in reversed((path, *path.parents)):
        if component.is_symlink():
            system_alias = (
                sys.platform == "darwin"
                and component in aliases
                and component.resolve() == aliases[component]
            )
            if not system_alias:
                raise InstallError(f"Refusing symlink: {component}")
        if component.exists():
            needs_directory = component != path or directory
            if needs_directory and not component.is_dir():
                raise InstallError(f"Expected directory: {component}")
            if not needs_directory and not component.is_file():
                raise InstallError(f"Expected regular file: {component}")


def source_bytes(relative: str) -> bytes:
    source = SOURCE_ROOT / relative
    check_path(source)
    if not source.is_file():
        raise InstallError(f"Missing release file: {relative}")
    return source.read_bytes()


def decode_text(data: bytes, path: Path | str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InstallError(f"Expected UTF-8 text: {path}") from exc


def managed_rules(existing: bytes, template: bytes, *, update: bool) -> bytes:
    text = decode_text(existing, "global AGENTS.md")
    rules = decode_text(template, "assets/global-agents.md").strip()
    if not rules or BEGIN in rules or END in rules:
        raise InstallError("Global rules template must be nonempty and have no managed markers")
    block = f"{BEGIN}\n{rules}\n{END}"
    if BEGIN not in text and END not in text:
        separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
        return (text + separator + block + "\n").encode("utf-8")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise InstallError("Malformed global AGENTS.md managed markers; merge manually")
    start, end = text.index(BEGIN), text.index(END) + len(END)
    if start >= end - len(END):
        raise InstallError("Malformed global AGENTS.md managed marker order; merge manually")
    if text[start:end] != block and not update:
        raise InstallError("Global managed rules differ; use --update or merge manually")
    return (text[:start] + block + text[end:]).encode("utf-8")


def plan_file(path: Path, data: bytes, writes: dict[Path, bytes], *, update: bool) -> bool:
    check_path(path)
    if path.exists():
        if path.read_bytes() == data:
            return False
        if not update:
            raise InstallError(f"Existing file differs: {path}; use --update or merge manually")
    previous = writes.get(path)
    if previous is not None and previous != data:
        raise InstallError(f"Conflicting installation destinations: {path}")
    writes[path] = data
    return True


def plan_install(args: argparse.Namespace) -> tuple[dict[Path, bytes], int]:
    # Read the entire release before examining or modifying the installation.
    release = {relative: source_bytes(relative) for relative in RELEASE_FILES}
    destination = absolute_path(args.skills_dir) / SKILL_NAME
    check_path(destination, directory=True)
    writes: dict[Path, bytes] = {}
    unchanged = 0
    for relative, content in release.items():
        unchanged += not plan_file(destination / relative, content, writes, update=args.update)
    if args.with_global_rules:
        codex_home = absolute_path(args.codex_home)
        override_path = codex_home / "AGENTS.override.md"
        check_path(override_path)
        if override_path.exists() and override_path.read_bytes().strip():
            raise InstallError(
                f"Nonempty {override_path} takes precedence over AGENTS.md; "
                "preserve the override and manually merge assets/global-agents.md "
                "into the effective instructions. No files were written"
            )
        rules_path = codex_home / "AGENTS.md"
        check_path(rules_path)
        existing = rules_path.read_bytes() if rules_path.exists() else b""
        content = managed_rules(existing, release["assets/global-agents.md"], update=args.update)
        unchanged += not plan_file(rules_path, content, writes, update=True)
    return writes, unchanged


def plan_project(args: argparse.Namespace) -> tuple[dict[Path, bytes], int]:
    content = source_bytes("assets/project-agents.md")
    destination = absolute_path(args.path) / "AGENTS.md"
    check_path(destination)
    if destination.exists() and destination.read_bytes() != content:
        raise InstallError(
            f"Project AGENTS.md already exists: {destination}; "
            "merge assets/project-agents.md manually, preserving project knowledge"
        )
    writes: dict[Path, bytes] = {}
    changed = plan_file(destination, content, writes, update=False)
    return writes, int(not changed)


def validate_write_set(writes: dict[Path, bytes]) -> None:
    """Catch cross-output file/directory collisions before creating anything."""
    for path in writes:
        check_path(path)
        if any(parent in writes for parent in path.parents):
            raise InstallError(f"Conflicting file and directory destinations: {path}")


def atomic_write(path: Path, data: bytes) -> None:
    # Recheck immediately before writing; deterministic conflicts were already
    # preflighted across the entire operation. Each file replacement is atomic.
    check_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".code-design-planner-", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    install = commands.add_parser("install", help="Install the skill once in a shared skills directory")
    install.add_argument("--skills-dir", default=str(Path.home() / ".agents/skills"), help="Shared skill parent directory (default: ~/.agents/skills)")
    install.add_argument("--with-global-rules", action="store_true", help="Explicitly add a managed block to CODEX_HOME/AGENTS.md")
    install.add_argument("--codex-home", default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")), help="Global rules directory (default: $CODEX_HOME or ~/.codex)")
    install.add_argument("--update", action="store_true", help="Replace differing release files and the managed rules block; retain other files")
    install.add_argument("--dry-run", action="store_true", help="Validate and report without writing")
    project = commands.add_parser("project", help="Create only a project's AGENTS.md knowledge template")
    project.add_argument("--path", required=True, help="Project directory")
    project.add_argument("--dry-run", action="store_true", help="Validate and report without writing")
    return cli


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        writes, unchanged = plan_install(args) if args.command == "install" else plan_project(args)
        validate_write_set(writes)
        for path, content in writes.items():
            if not args.dry_run:
                atomic_write(path, content)
            print(f"{'Would write' if args.dry_run else 'Wrote'}: {path}")
        print(f"{'Dry run' if args.dry_run else 'Complete'}: {len(writes)} file(s) {'to write' if args.dry_run else 'written'}, {unchanged} unchanged.")
        return 0
    except (InstallError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
