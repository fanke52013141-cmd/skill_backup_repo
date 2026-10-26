"""版本规则及发布集成回归；只写入临时目录，Git 提交使用 mock。"""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import skillctl


class VersionTests(unittest.TestCase):
    def test_integer_sequence(self):
        for old, new in [("1.0", "2.0"), ("2.0", "3.0"), ("9.0", "10.0")]:
            self.assertEqual(skillctl.bump_version(old), new)

    def test_migrate_legacy_versions(self):
        for old, new in [("2.0.0", "3.0"), ("1.5.8", "2.0")]:
            self.assertEqual(skillctl.bump_version(old), new)

    def test_legacy_bump_flags_have_same_result(self):
        for level in ["next", "patch", "minor", "major"]:
            self.assertEqual(skillctl.bump_version("2.0.0", level), "3.0")

    def test_invalid_versions_are_rejected(self):
        for value in ["", "draft", "2.1", "0.0", "-1.0", "2.0.0.1", "v2.0", "2.a.0"]:
            with self.subTest(value=value), self.assertRaises(SystemExit):
                skillctl.bump_version(value)

    def test_installed_version_comparison(self):
        self.assertGreater(skillctl.parse_version("3.0"), skillctl.parse_version("2.0.0"))
        self.assertEqual(skillctl.parse_version("3.0"), skillctl.parse_version("3.0.0"))
        self.assertGreater(skillctl.parse_version("10.0"), skillctl.parse_version("9.0"))


class PublishTests(unittest.TestCase):
    def setUp(self):
        # All files remain inside the task's working checkout until automatic cleanup.
        self.temp = tempfile.TemporaryDirectory(prefix="skillctl-test-", dir=skillctl.REPO.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skills = self.root / "skills"
        self.target = self.root / "installed"
        self.skills.mkdir()
        self.target.mkdir()
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text('{"schema":1,"skills":[]}', encoding="utf-8")
        self.scope = patch.multiple(skillctl, REPO=self.root, SKILLS_DIR=self.skills,
                                    MANIFEST=self.manifest, TARGET=self.target)
        self.scope.start()
        self.addCleanup(self.scope.stop)
        self.commit = patch.object(skillctl, "git_commit").start()
        self.addCleanup(patch.stopall)

    def source(self):
        path = self.target / "示例技能"
        path.mkdir()
        (path / "SKILL.md").write_text("---\nname: 示例技能\ndescription: 示例\n---\n新内容\n", encoding="utf-8")
        (path / "skill.json").write_text('{"version":"7.2.1"}', encoding="utf-8")

    def publish(self, note="保留现有能力，补充说明", bump="next"):
        with contextlib.redirect_stdout(io.StringIO()):
            skillctl.cmd_publish(argparse.Namespace(name="示例技能", note=note, bump=bump))

    def test_new_skill_starts_at_one(self):
        self.source()
        self.publish()
        meta = skillctl.read_skill_meta(self.skills / "示例技能")
        self.assertEqual(meta["version"], "1.0")
        self.assertEqual(json.loads(self.manifest.read_text(encoding="utf-8"))["skills"], [meta])
        self.assertIn("新增 → 1.0（整数递增）", (self.root / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.commit.assert_called_once_with("示例技能", "1.0", "保留现有能力，补充说明")

    def test_existing_legacy_skill_and_consecutive_publish(self):
        self.source()
        path = self.skills / "示例技能"
        path.mkdir()
        skillctl.write_skill_meta(path, {"version": "2.0.0"})
        self.publish(bump="minor")
        self.assertEqual(skillctl.read_skill_meta(path)["version"], "3.0")
        self.publish(note="再次更新")
        self.assertEqual(skillctl.read_skill_meta(path)["version"], "4.0")
        log = (self.root / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertLess(log.index("3.0 → 4.0"), log.index("2.0.0 → 3.0"))

    def test_empty_note_stops_before_write(self):
        self.source()
        with self.assertRaises(SystemExit):
            self.publish(note="  ")
        self.assertFalse((self.skills / "示例技能").exists())
        self.commit.assert_not_called()

    def test_invalid_old_version_stops_before_copy(self):
        self.source()
        path = self.skills / "示例技能"
        path.mkdir()
        skillctl.write_skill_meta(path, {"version": "bad"})
        (path / "SKILL.md").write_text("保留原文", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.publish()
        self.assertEqual((path / "SKILL.md").read_text(encoding="utf-8"), "保留原文")
        self.commit.assert_not_called()

    def test_cli_requires_note(self):
        with patch("sys.argv", ["skillctl", "publish", "示例技能"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                skillctl.main()
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
