"""Exercise validation with temporary skill packages, not repository wording."""

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("skill_validate", Path(__file__).resolve().parents[1] / "scripts" / "validate.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)
INSTALL_SPEC = importlib.util.spec_from_file_location("skill_installer_for_validation", Path(__file__).resolve().parents[1] / "scripts" / "install.py")
installer = importlib.util.module_from_spec(INSTALL_SPEC)
INSTALL_SPEC.loader.exec_module(installer)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "package"
        self.root.mkdir()
        for relative in validator.REQUIRED_FILES:
            self.write(relative, "# Package resource\n")
        self.write("SKILL.md", "---\nname: code-design-planner\ndescription: 规划及评审功能开发。\n---\n# Skill\n[Planner](references/planner.md)\n")
        self.write("agents/openai.yaml", 'interface:\n  display_name: "Code Design Planner"\n  short_description: "Plan and review code changes"\n  default_prompt: "Use $code-design-planner to plan this change."\npolicy:\n  allow_implicit_invocation: true\n')

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_valid_package_and_cli_success(self):
        self.assertEqual(validator.validate(self.root), [])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(validator.main(["--root", str(self.root)]), 0)
        self.assertIn("does not prove", output.getvalue())

    def test_each_required_resource_is_checked(self):
        for relative in validator.REQUIRED_FILES:
            with self.subTest(relative=relative):
                path = self.root / relative
                content = path.read_text(encoding="utf-8")
                path.unlink()
                self.assertTrue(any(relative in error and "required resource" in error for error in validator.validate(self.root)))
                self.write(relative, content)

    def test_frontmatter_fields_and_delimiters(self):
        cases = (
            ("# no metadata", "frontmatter"),
            ("---\nname: code-design-planner\n", "closing"),
            ("---\nname: another-skill\ndescription: Description\n---\nBody", "name must"),
            ("---\nname: code-design-planner\ndescription: false\n---\nBody", "description must"),
            ("---\nname: code-design-planner\ndescription: Description\n---\n", "instructions are empty"),
            ("---\nname: code-design-planner\nname: code-design-planner\ndescription: Description\n---\nBody", "duplicate key"),
        )
        for content, fragment in cases:
            with self.subTest(fragment=fragment):
                self.write("SKILL.md", content)
                self.assertTrue(any(fragment in error for error in validator.validate(self.root)))

    def test_folded_description_and_quoted_strings(self):
        self.write("SKILL.md", "---\nname: 'code-design-planner'\ndescription: >-\n  Analyze requirements\n  and review implementation.\n---\n# Skill\n")
        self.assertEqual(validator.validate(self.root), [])
        self.assertEqual(validator.parse_mapping("value: 'it''s a string'"), {"value": "it's a string"})

    def test_agents_required_metadata_and_policy_types(self):
        self.write("agents/openai.yaml", 'interface:\n  display_name: Name\n  short_description: false\npolicy:\n  allow_implicit_invocation: "true"\n')
        errors = validator.validate(self.root)
        for fragment in ("short_description", "default_prompt", "allow_implicit_invocation"):
            self.assertTrue(any(fragment in error for error in errors), errors)

    def test_bad_yaml_is_reported_not_accepted_as_full_yaml(self):
        for content in ("interface: &anchor", "interface:\n   display_name: Bad indent", "interface:\n  - a sequence", 'interface: "unterminated', "interface:\n  display_name: Name\n  display_name: Duplicate"):
            with self.subTest(content=content):
                self.write("agents/openai.yaml", content)
                self.assertTrue(any("agents/openai.yaml" in error for error in validator.validate(self.root)))

    def test_local_links_and_reference_definitions_resolve_from_source(self):
        self.write("references/planner.md", '[Review](reviewer.md#check)\n[Template](../assets/design-template.md "Design")\n[Home][home]\n[home]: ../SKILL.md\n[Encoded](../assets/%64esign-template.md?version=1)\n')
        self.assertEqual(validator.validate(self.root), [])

    def test_existing_link_target_must_be_in_release_manifest(self):
        self.write("assets/example.md", "# Unshipped resource\n")
        skill = self.root / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n[Example](assets/example.md)\n", encoding="utf-8")
        self.assertTrue(any("not in the release manifest: assets/example.md" in error for error in validator.validate(self.root)))

    def test_directory_link_requires_released_descendant(self):
        self.write("references/planner.md", "[Templates](../assets/)\n[Package](../)\n")
        self.assertEqual(validator.validate(self.root), [])
        (self.root / "assets" / "unshipped").mkdir()
        self.write("references/planner.md", "[Empty directory](../assets/unshipped/)\n")
        self.assertTrue(any("not in the release manifest" in error for error in validator.validate(self.root)))

    def test_unreleased_symlink_alias_is_not_treated_as_shipped_target(self):
        (self.root / "assets" / "alias.md").symlink_to("design-template.md")
        self.write("references/planner.md", "[Alias](../assets/alias.md)\n")
        self.assertTrue(any("not in the release manifest" in error for error in validator.validate(self.root)))

    def test_validator_and_installer_use_the_same_release_manifest(self):
        self.assertEqual(set(validator.REQUIRED_FILES), set(installer.RELEASE_FILES))

    def test_real_source_and_installed_release_both_validate(self):
        source = Path(__file__).resolve().parents[1] / "skills" / "code-design-planner"
        self.assertEqual(validator.validate(source), [])
        skills = Path(self.temporary.name) / "installed-skills"
        codex_home = Path(self.temporary.name) / "codex-home"
        project = Path(self.temporary.name) / "project"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(validator.main([]), 0)
            self.assertEqual(installer.main(["install", "--skills-dir", str(skills), "--with-global-rules", "--codex-home", str(codex_home)]), 0)
            self.assertEqual(installer.main(["project", "--path", str(project)]), 0)
        self.assertEqual(validator.validate(skills / installer.SKILL_NAME), [])
        self.assertIn((source / "assets/global-agents.md").read_text(encoding="utf-8").strip(), (codex_home / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual((project / "AGENTS.md").read_bytes(), (source / "assets/project-agents.md").read_bytes())

    def test_missing_relative_link_is_detected(self):
        self.write("references/planner.md", "[Missing](missing.md)\n[other]: ../assets/missing.md\n")
        errors = validator.validate(self.root)
        self.assertEqual(sum("local link target is missing" in error for error in errors), 2)

    def test_link_cannot_escape_package_even_if_target_exists(self):
        (self.root.parent / "outside.md").write_text("Outside", encoding="utf-8")
        self.write("references/planner.md", "[Escape](../../outside.md)\n")
        self.assertTrue(any("escapes" in error for error in validator.validate(self.root)))

    def test_symlink_escape_is_detected(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("Outside", encoding="utf-8")
        (self.root / "assets" / "escape.md").symlink_to(outside)
        self.write("references/planner.md", "[Escape](../assets/escape.md)\n")
        errors = validator.validate(self.root)
        self.assertTrue(any("local link escapes" in error for error in errors))
        self.assertTrue(any("Markdown resource escapes" in error for error in errors))

    def test_required_resource_cannot_be_external_symlink(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("Outside", encoding="utf-8")
        resource = self.root / "assets" / "design-template.md"
        resource.unlink()
        resource.symlink_to(outside)
        self.assertTrue(any("required resource escapes" in error for error in validator.validate(self.root)))

    def test_examples_placeholders_remote_and_anchor_links_are_ignored(self):
        self.write("assets/design-template.md", """# Template

[Design](docs/designs/<slug>.md)
[Another](docs/designs/{feature}.md)
[Remote](https://example.com/missing.md)
[Mail](mailto:someone@example.com)
[Heading](#heading)
`[Code](missing.md)`
```markdown
[Example](missing.md)
```
~~~markdown
[Example](missing.md)
~~~
    [Indented code](missing.md)
""")
        self.assertEqual(validator.validate(self.root), [])

    def test_angle_wrapped_real_destination_is_still_checked(self):
        for destination in ("<missing.md>", '<missing.md> "A title"'):
            with self.subTest(destination=destination):
                self.write("references/planner.md", f"[Real]({destination})\n")
                self.assertTrue(any("local link target is missing" in error for error in validator.validate(self.root)))

    def test_unreleased_destinations_with_parentheses_are_reported(self):
        self.write("assets/design(v2).md", "# Template")
        self.write("references/planner.md", "[Real](../assets/design(v2).md)\n[Escaped](../assets/design\\(v2\\).md)\n")
        errors = validator.validate(self.root)
        self.assertEqual(sum("not in the release manifest" in error for error in errors), 2)
        self.assertFalse(any("target is missing" in error for error in errors))

    def test_invalid_utf8_is_reported(self):
        (self.root / "references" / "planner.md").write_bytes(b"\xff\xfe")
        self.assertTrue(any("UTF-8" in error for error in validator.validate(self.root)))

    def test_cli_returns_failure_with_diagnostic(self):
        (self.root / "SKILL.md").unlink()
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(validator.main(["--root", str(self.root)]), 1)
        self.assertIn("SKILL.md", output.getvalue())


if __name__ == "__main__":
    unittest.main()
