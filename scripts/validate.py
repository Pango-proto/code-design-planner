#!/usr/bin/env python3
"""Validate the distributed skill's structure, using only the standard library.

The YAML reader intentionally supports a small schema: indented mappings,
strings (plain, quoted, or block), and booleans. It is not a general YAML parser.
Markdown checks cover inline links and reference definitions outside code.
Structural success does not prove workflow execution or design correctness.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


REQUIRED_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/planner.md",
    "references/reviewer.md",
    "references/integrations.md",
    "assets/design-template.md",
    "assets/project-agents.md",
    "assets/global-agents.md",
)


class SchemaError(ValueError):
    """Input is invalid or outside the deliberately limited YAML schema."""


def _scalar(value: str, line: int) -> str | bool:
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"line {line}: double-quoted strings require JSON escapes") from exc
        if not isinstance(parsed, str):
            raise SchemaError(f"line {line}: expected a string")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise SchemaError(f"line {line}: unterminated single-quoted string")
        inner = value[1:-1]
        if "'" in inner.replace("''", ""):
            raise SchemaError(f"line {line}: single quotes must be doubled")
        return inner.replace("''", "'")
    value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
    if value in {"true", "false"}:
        return value == "true"
    if not value or value[0] in "[{}]&*!|>@`" or re.search(r":\s", value):
        raise SchemaError(f"line {line}: unsupported YAML scalar; quote the string")
    if value in {"null", "Null", "NULL", "~"} or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value):
        raise SchemaError(f"line {line}: expected string or boolean; quote numeric text")
    return value


def parse_mapping(text: str) -> dict:
    """Read the documented mapping/string/boolean subset, rejecting ambiguity."""
    result: dict = {}
    stack = [(-1, result)]
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index]
        index += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise SchemaError(f"line {index}: tabs are not supported for indentation")
        indent = len(raw) - len(raw.lstrip(" "))
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?", raw.strip())
        if not match:
            raise SchemaError(f"line {index}: expected a mapping entry")
        key, value = match.groups()
        while indent <= stack[-1][0]:
            stack.pop()
        parent_indent, parent = stack[-1]
        if indent != parent_indent + (1 if parent_indent == -1 else 2):
            raise SchemaError(f"line {index}: mappings require two-space indentation")
        if key in parent:
            raise SchemaError(f"line {index}: duplicate key {key!r}")
        if value is None or value.startswith("#"):
            parent[key] = {}
            stack.append((indent, parent[key]))
        elif value in {"|", "|-", "|+", ">", ">-", ">+"}:
            block: list[str] = []
            while index < len(lines):
                following = lines[index]
                following_indent = len(following) - len(following.lstrip(" "))
                if following.strip() and following_indent <= indent:
                    break
                if following.strip() and following_indent < indent + 2:
                    raise SchemaError(f"line {index + 1}: block string requires indentation")
                block.append(following[indent + 2 :] if following.strip() else "")
                index += 1
            separator = " " if value.startswith(">") else "\n"
            parent[key] = separator.join(block).rstrip() + ("" if value.endswith("-") else "\n")
        else:
            parent[key] = _scalar(value, index)
    return result


def _without_code(text: str) -> str:
    """Ignore fenced/indented code and inline code when locating Markdown links."""
    visible: list[str] = []
    fence: str | None = None
    fence_length = 0
    for line in text.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence and len(marker[1]) >= fence_length:
                fence = None
            continue
        if marker:
            fence, fence_length = marker[1][0], len(marker[1])
            continue
        if line.startswith("    ") or line.startswith("\t"):
            continue
        visible.append(line)
    return re.sub(r"(`+).*?\1", "", "\n".join(visible), flags=re.DOTALL)


def _destination(source: str) -> str:
    """Read a link target, leaving an optional title and closing delimiter behind."""
    source = source.lstrip()
    if source.startswith("<"):
        end = source.find(">")
        return source[: end + 1] if end >= 0 else source
    depth = 0
    escaped = False
    end = len(source)
    for index, char in enumerate(source):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
        elif char.isspace() or (char == ")" and depth == 0):
            end = index
            break
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
    return re.sub(r"\\([()\[\]<> ])", r"\1", source[:end])


def _destinations(text: str):
    visible = _without_code(text)
    for match in re.finditer(r"!?\[[^\]\n]*\]\(", visible):
        yield _destination(visible[match.end() :].split("\n", 1)[0])
    for match in re.finditer(r"^ {0,3}\[[^\]\n]+\]:[ \t]*(.*)$", visible, re.MULTILINE):
        yield _destination(match[1])


def _link_path(destination: str) -> str | None:
    if destination.startswith("<") and destination.endswith(">"):
        destination = destination[1:-1]
    # Templates document paths that will be chosen by a consuming project.
    if re.search(r"<[^>]+>|\{[^}]+\}", destination):
        return None
    try:
        parsed = urlsplit(destination)
    except ValueError:
        return destination
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    return unquote(parsed.path)


def validate(root: Path) -> list[str]:
    root = root.resolve()
    release_paths = {root / relative for relative in REQUIRED_FILES}
    errors: list[str] = []
    contents: dict[str, str] = {}
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.resolve().is_relative_to(root):
            errors.append(f"{relative}: required resource escapes the skill package")
            continue
        if not path.is_file():
            errors.append(f"{relative}: required resource is missing or is not a file")
            continue
        try:
            contents[relative] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{relative}: cannot read UTF-8 text: {exc}")

    if "SKILL.md" in contents:
        lines = contents["SKILL.md"].splitlines()
        try:
            if not lines or lines[0] != "---":
                raise SchemaError("must start with YAML frontmatter (---)")
            try:
                end = lines.index("---", 1)
            except ValueError as exc:
                raise SchemaError("frontmatter has no closing ---") from exc
            metadata = parse_mapping("\n".join(lines[1:end]))
            if metadata.get("name") != "code-design-planner":
                errors.append("SKILL.md: name must be code-design-planner")
            description = metadata.get("description")
            if not isinstance(description, str) or not description.strip():
                errors.append("SKILL.md: description must be a nonempty string")
            if not "\n".join(lines[end + 1 :]).strip():
                errors.append("SKILL.md: skill instructions are empty")
        except SchemaError as exc:
            errors.append(f"SKILL.md: {exc}")

    if "agents/openai.yaml" in contents:
        try:
            metadata = parse_mapping(contents["agents/openai.yaml"])
            interface = metadata.get("interface")
            if not isinstance(interface, dict):
                errors.append("agents/openai.yaml: interface must be a mapping")
            else:
                for key in ("display_name", "short_description", "default_prompt"):
                    if not isinstance(interface.get(key), str) or not interface[key].strip():
                        errors.append(f"agents/openai.yaml: interface.{key} must be a nonempty string")
            if "policy" in metadata:
                policy = metadata["policy"]
                if not isinstance(policy, dict):
                    errors.append("agents/openai.yaml: policy must be a mapping")
                elif "allow_implicit_invocation" in policy and not isinstance(policy["allow_implicit_invocation"], bool):
                    errors.append("agents/openai.yaml: policy.allow_implicit_invocation must be a boolean")
        except SchemaError as exc:
            errors.append(f"agents/openai.yaml: {exc}")

    markdown = {root / "SKILL.md"}
    for directory in ("references", "assets"):
        markdown.update((root / directory).rglob("*.md"))
    for path in sorted(markdown):
        relative = path.relative_to(root).as_posix()
        if not path.resolve().is_relative_to(root):
            if relative not in REQUIRED_FILES:
                errors.append(f"{relative}: Markdown resource escapes the skill package")
            continue
        if not path.is_file():
            continue
        try:
            content = contents.get(relative)
            if content is None:
                content = path.read_text(encoding="utf-8")
            for destination in _destinations(content):
                local = _link_path(destination)
                if local is None:
                    continue
                # Compare the installed path, not a symlink's resolved alias:
                # an unshipped alias cannot satisfy an installed Markdown link.
                target = Path(os.path.abspath(path.parent / local))
                if not target.resolve().is_relative_to(root):
                    errors.append(f"{relative}: local link escapes the skill package: {destination}")
                elif not target.exists():
                    errors.append(f"{relative}: local link target is missing: {destination}")
                elif target not in release_paths and not (
                    target.is_dir() and any(resource.is_relative_to(target) for resource in release_paths)
                ):
                    errors.append(f"{relative}: local link target is not in the release manifest: {destination}")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{relative}: cannot check Markdown links: {exc}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "skills" / "code-design-planner", help="Skill package root (default: repository skills/code-design-planner)")
    args = parser.parse_args(argv)
    errors = validate(args.root)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"Structural validation failed: {len(errors)} error(s).", file=sys.stderr)
        return 1
    print("Structural validation passed (restricted YAML schema and local Markdown links).")
    print("This does not prove workflow execution, design correctness, or implementation quality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
