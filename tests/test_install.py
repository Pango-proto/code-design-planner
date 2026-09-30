"""Exercise the actual CLI against isolated release, home, and project folders."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="planner-install-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repository = self.root / "release"
        self.release = self.repository / "skills" / installer.SKILL_NAME
        (self.repository / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts/install.py", self.repository / "scripts/install.py")
        for relative in installer.RELEASE_FILES:
            path = self.release / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"Release content: {relative}\n", encoding="utf-8")
        (self.repository / "private-notes.txt").write_text("Do not distribute.\n")
        (self.release / "private-notes.txt").write_text("Do not distribute.\n")
        self.home = self.root / "home"
        self.codex_home = self.home / ".codex"
        self.skill = self.home / ".agents/skills/code-design-planner"
        self.env = {**os.environ, "HOME": str(self.home), "CODEX_HOME": str(self.codex_home)}

    def run_cli(self, *args: str, success: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(self.repository / "scripts/install.py"), *map(str, args)],
            cwd=self.root, env=self.env, capture_output=True, text=True,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_default_shared_install_and_two_projects_have_no_skill_copies(self) -> None:
        self.run_cli("install")
        self.assertEqual(
            sorted(str(path.relative_to(self.skill)) for path in self.skill.rglob("*") if path.is_file()),
            sorted(installer.RELEASE_FILES),
        )
        self.assertFalse(self.codex_home.exists())
        for name in ("project-a", "project-b"):
            project = self.root / name
            self.run_cli("project", "--path", project)
            self.assertEqual([path.name for path in project.iterdir()], ["AGENTS.md"])
        self.assertEqual(len(list(self.home.rglob("code-design-planner/SKILL.md"))), 1)

    def test_repeat_is_idempotent_and_leaves_existing_file_mtime(self) -> None:
        self.run_cli("install", "--with-global-rules")
        paths = [*(self.skill / name for name in installer.RELEASE_FILES), self.codex_home / "AGENTS.md"]
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        result = self.run_cli("install", "--with-global-rules")
        self.assertIn("0 file(s) written", result.stdout)
        self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})
        project = self.root / "project"
        self.run_cli("project", "--path", project)
        self.assertIn("0 file(s) written", self.run_cli("project", "--path", project).stdout)

    def test_explicit_legacy_skill_directory(self) -> None:
        self.run_cli("install", "--skills-dir", self.codex_home / "skills")
        self.assertTrue((self.codex_home / "skills/code-design-planner/SKILL.md").is_file())
        self.assertFalse(self.skill.exists())

    def test_late_release_conflict_prevents_earlier_writes(self) -> None:
        conflict = self.skill / installer.RELEASE_FILES[-1]
        conflict.parent.mkdir(parents=True)
        conflict.write_text("User content")
        self.run_cli("install", success=False)
        self.assertEqual(conflict.read_text(), "User content")
        self.assertFalse((self.skill / "SKILL.md").exists())

    def test_update_replaces_only_known_files(self) -> None:
        self.run_cli("install")
        extra = self.skill / "my-notes.md"
        extra.write_text("Keep user file")
        (self.skill / "SKILL.md").write_text("Old release")
        self.run_cli("install", "--update")
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), (self.release / "SKILL.md").read_bytes())
        self.assertEqual(extra.read_text(), "Keep user file")

    def test_global_rules_preserve_existing_bytes_and_update_only_block(self) -> None:
        self.codex_home.mkdir(parents=True)
        rules = self.codex_home / "AGENTS.md"
        existing = "# 我的规则\r\nPreserve this.\r\n".encode()
        rules.write_bytes(existing)
        self.run_cli("install", "--with-global-rules")
        self.assertTrue(rules.read_bytes().startswith(existing))
        self.assertEqual(rules.read_text().count(installer.BEGIN), 1)
        with rules.open("ab") as stream:
            stream.write(b"\n# More user rules\n")
        (self.release / "assets/global-agents.md").write_text("New workflow\n")
        self.run_cli("install", "--with-global-rules", "--update")
        updated = rules.read_bytes()
        self.assertTrue(updated.startswith(existing))
        self.assertTrue(updated.endswith(b"\n# More user rules\n"))
        self.assertIn(b"New workflow", updated)
        self.assertEqual(updated.count(installer.BEGIN.encode()), 1)

    def test_malformed_global_rules_prevent_partial_install(self) -> None:
        self.codex_home.mkdir(parents=True)
        rules = self.codex_home / "AGENTS.md"
        for malformed in (installer.BEGIN, installer.END + "\n" + installer.BEGIN,
                          installer.BEGIN + installer.BEGIN + installer.END):
            with self.subTest(malformed=malformed):
                rules.write_text(malformed)
                self.run_cli("install", "--with-global-rules", "--update", success=False)
                self.assertFalse(self.skill.exists())
                self.assertEqual(rules.read_text(), malformed)

    def test_nonempty_global_override_prevents_partial_install(self) -> None:
        custom_home = self.root / "custom-codex"
        custom_home.mkdir()
        override = custom_home / "AGENTS.override.md"
        override.write_text("# Effective user instructions\n")
        rules = custom_home / "AGENTS.md"
        rules.write_text("# Existing fallback instructions\n")
        for option in ((), ("--update",), ("--dry-run",)):
            with self.subTest(option=option):
                result = self.run_cli(
                    "install", "--with-global-rules", "--codex-home", custom_home,
                    *option, success=False,
                )
                self.assertIn(str(override), result.stderr)
                self.assertIn("takes precedence", result.stderr)
                self.assertIn("preserve", result.stderr)
                self.assertIn("manually merge", result.stderr)
                self.assertFalse(self.skill.exists())
                self.assertEqual(override.read_text(), "# Effective user instructions\n")
                self.assertEqual(rules.read_text(), "# Existing fallback instructions\n")

    def test_empty_global_override_is_preserved_and_allows_rules(self) -> None:
        self.codex_home.mkdir(parents=True)
        override = self.codex_home / "AGENTS.override.md"
        for content in (b"", b" \t\r\n"):
            with self.subTest(content=content):
                override.write_bytes(content)
                self.run_cli("install", "--with-global-rules")
                self.assertEqual(override.read_bytes(), content)
                self.assertIn(installer.BEGIN, (self.codex_home / "AGENTS.md").read_text())

    def test_override_symlink_or_directory_prevents_partial_install(self) -> None:
        self.codex_home.mkdir(parents=True)
        override = self.codex_home / "AGENTS.override.md"
        outside = self.root / "outside.md"
        outside.write_bytes(b"")
        override.symlink_to(outside)
        self.run_cli("install", "--with-global-rules", "--update", success=False)
        self.assertTrue(override.is_symlink())
        self.assertEqual(outside.read_bytes(), b"")
        self.assertFalse(self.skill.exists())
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        override.unlink()
        override.mkdir()
        self.run_cli("install", "--with-global-rules", success=False)
        self.assertTrue(override.is_dir())
        self.assertFalse(self.skill.exists())
        self.assertFalse((self.codex_home / "AGENTS.md").exists())

    def test_skill_only_install_does_not_inspect_or_change_global_override(self) -> None:
        self.codex_home.mkdir(parents=True)
        override = self.codex_home / "AGENTS.override.md"
        override.write_text("# Effective user instructions\n")
        self.run_cli("install")
        self.assertTrue((self.skill / "SKILL.md").is_file())
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertEqual(override.read_text(), "# Effective user instructions\n")

    def test_different_managed_rules_require_update_before_skill_writes(self) -> None:
        self.codex_home.mkdir(parents=True)
        rules = self.codex_home / "AGENTS.md"
        rules.write_text(f"{installer.BEGIN}\nUser edited workflow\n{installer.END}\n")
        self.run_cli("install", "--with-global-rules", success=False)
        self.assertFalse(self.skill.exists())
        self.assertIn("User edited workflow", rules.read_text())

    def test_existing_project_knowledge_is_never_overwritten(self) -> None:
        project = self.root / "project"
        project.mkdir()
        agents = project / "AGENTS.md"
        agents.write_text("# Actual project knowledge\n")
        result = self.run_cli("project", "--path", project, success=False)
        self.assertIn("merge", result.stderr)
        self.assertEqual(agents.read_text(), "# Actual project knowledge\n")
        self.assertEqual([path.name for path in project.iterdir()], ["AGENTS.md"])

    def test_dry_run_creates_no_directories_or_files(self) -> None:
        result = self.run_cli("install", "--with-global-rules", "--dry-run")
        self.assertIn("Would write", result.stdout)
        self.assertFalse(self.home.exists())
        project = self.root / "not-created"
        self.run_cli("project", "--path", project, "--dry-run")
        self.assertFalse(project.exists())

    def test_directory_and_file_symlinks_refused_even_with_update(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        target = outside / "keep.md"
        target.write_text("Keep outside data")
        self.skill.parent.mkdir(parents=True)
        self.skill.symlink_to(outside, target_is_directory=True)
        self.run_cli("install", "--update", success=False)
        self.assertEqual([path.name for path in outside.iterdir()], ["keep.md"])
        self.skill.unlink()
        self.skill.mkdir()
        (self.skill / "SKILL.md").symlink_to(target)
        self.run_cli("install", "--update", success=False)
        self.assertEqual(target.read_text(), "Keep outside data")
        self.assertFalse((self.skill / "agents").exists())

    def test_symlink_ancestor_and_project_symlink_are_refused(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        self.run_cli("install", "--skills-dir", alias / "skills", success=False)
        self.run_cli("project", "--path", alias / "project", success=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_global_symlink_prevents_partial_install(self) -> None:
        self.codex_home.mkdir(parents=True)
        outside = self.root / "outside.md"
        outside.write_text("Keep")
        (self.codex_home / "AGENTS.md").symlink_to(outside)
        self.run_cli("install", "--with-global-rules", "--update", success=False)
        self.assertFalse(self.skill.exists())
        self.assertEqual(outside.read_text(), "Keep")

    def test_wrong_type_and_cross_destination_collisions_prevent_writes(self) -> None:
        self.skill.mkdir(parents=True)
        (self.skill / "references").write_text("File blocks directory")
        self.run_cli("install", "--update", success=False)
        self.assertFalse((self.skill / "SKILL.md").exists())
        (self.skill / "references").unlink()
        self.run_cli("install", "--with-global-rules", "--codex-home", self.skill / "SKILL.md", success=False)
        self.assertEqual(list(self.skill.iterdir()), [])

    def test_missing_or_symlink_source_prevents_install(self) -> None:
        source = self.release / "assets/global-agents.md"
        source.unlink()
        self.run_cli("install", success=False)
        self.assertFalse(self.home.exists())
        source.symlink_to(self.release / "SKILL.md")
        self.run_cli("install", success=False)
        self.assertFalse(self.home.exists())


if __name__ == "__main__":
    unittest.main()
