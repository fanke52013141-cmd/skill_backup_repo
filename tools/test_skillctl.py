"""Skill/Prompt 命名、安装、发布和失败回退回归；所有写入均在临时目录。"""
import argparse
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import skillctl


class VersionTests(unittest.TestCase):
    def test_integer_sequence(self):
        for old, new in [("1.0", "2.0"), ("2.0", "3.0"), ("9.0", "10.0")]:
            self.assertEqual(skillctl.bump_version(old), new)

    def test_migrate_legacy_versions(self):
        self.assertEqual(skillctl.bump_version("2.0.0"), "3.0")
        self.assertEqual(skillctl.bump_version("1.5.8"), "2.0")

    def test_invalid_versions_are_rejected(self):
        for value in ["", "draft", "2.1", "0.0", "-1.0", "2.0.0.1", "v2.0"]:
            with self.subTest(value=value), self.assertRaises(SystemExit):
                skillctl.bump_version(value)

    def test_versioned_package_name(self):
        self.assertEqual(skillctl.asset_name("示例技能", "2.0"), "示例技能-2.0")
        self.assertEqual(skillctl.asset_name("示例技能", "10.0"), "示例技能-10.0")

    def test_unsafe_ids_are_rejected(self):
        for value in ["../x", "a/b", "a\\b", ".hidden", ""]:
            with self.subTest(value=value), self.assertRaises(SystemExit):
                skillctl.asset_name(value, "1.0")


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="assetctl-test-", dir=skillctl.REPO.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skills = self.root / "skills"
        self.prompts = self.root / "prompts"
        self.target = self.root / "installed"
        self.skills.mkdir()
        self.prompts.mkdir()
        self.target.mkdir()
        self.manifest = self.root / "manifest.json"
        self.write_manifest({"schema": 2, "repository": self.repository(), "skills": [], "prompts": []})
        self.scope = patch.multiple(
            skillctl,
            REPO=self.root,
            SKILLS_DIR=self.skills,
            PROMPTS_DIR=self.prompts,
            MANIFEST=self.manifest,
            TARGET=self.target,
            STATE_FILE=self.target / ".skillctl.json",
            BACKUP_DIR=self.root / "backups",
        )
        self.scope.start()
        self.addCleanup(self.scope.stop)
        self.preflight = patch.object(skillctl, "preflight_git").start()
        self.commit = patch.object(skillctl, "commit_and_push").start()
        self.addCleanup(patch.stopall)

    def repository(self, kind="skill", package="示例技能-2.0"):
        return {
            "url": "https://example.test/owner/repo.git",
            "branch": "main",
            "path": f"{kind}s/{package}",
        }

    def write_manifest(self, data):
        self.manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def use_kind(self, kind):
        skillctl.STATE_FILE = self.target / f".{kind}ctl.json"
        skillctl.BACKUP_DIR = self.root / f"{kind}-backups"

    def meta(self, asset_id, version, kind):
        package = skillctl.asset_name(asset_id, version)
        return {
            "id": asset_id,
            "name": package,
            "version": version,
            "entry": skillctl.entry_filename(kind),
            "summary": "示例用途",
            "repository": self.repository(kind, package),
        }

    def register(self, asset_id="示例技能", version="2.0", kind="skill", with_local=True):
        self.use_kind(kind)
        package = skillctl.asset_name(asset_id, version)
        repo_path = skillctl.asset_root(kind) / package
        repo_path.mkdir(parents=True)
        meta = self.meta(asset_id, version, kind)
        skillctl.write_asset_meta(repo_path, meta, kind)
        entry = repo_path / skillctl.entry_filename(kind)
        entry.write_text(
            f"---\nname: {package}\ndescription: 示例\n---\n原始内容\n", encoding="utf-8"
        )
        if kind == "skill":
            (repo_path / "agents").mkdir()
            (repo_path / "agents" / "openai.yaml").write_text(
                f'interface:\n  display_name: "{package}"\n  default_prompt: "请使用 ${package}"\n',
                encoding="utf-8",
            )
        data = skillctl.load_manifest()
        data[skillctl.collection(kind)].append({**meta, "directory": package})
        self.write_manifest(data)
        if not with_local:
            return repo_path, None
        local = self.target / package
        shutil.copytree(repo_path, local)
        skillctl.save_state({
            "schema": 2,
            "installed": {asset_id: {
                "id": asset_id,
                "name": package,
                "directory": package,
                "version": version,
                "repository": meta["repository"],
                "hash": skillctl.digest(skillctl.file_map(local)),
            }},
        })
        return repo_path, local

    def publish(self, asset_id="示例技能", kind="skill", note="补充规则与示例", push=True):
        with contextlib.redirect_stdout(io.StringIO()):
            skillctl.cmd_publish(argparse.Namespace(
                name=asset_id, note=note, bump="next", push=push
            ), kind)

    def test_install_uses_versioned_local_name_and_records_github(self):
        self.register(with_local=False)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(skillctl.do_install("示例技能"))
        local = self.target / "示例技能-2.0"
        self.assertTrue((local / "SKILL.md").exists())
        state = skillctl.load_state()["installed"]["示例技能"]
        self.assertEqual(state["directory"], "示例技能-2.0")
        self.assertEqual(state["repository"]["url"], "https://example.test/owner/repo.git")

    def test_legacy_install_without_directory_upgrades_cleanly(self):
        self.register(version="2.0", with_local=False)
        legacy = self.target / "示例技能"
        legacy.mkdir()
        (legacy / "SKILL.md").write_text(
            "---\nname: 示例技能\ndescription: 旧版\n---\n旧内容\n", encoding="utf-8"
        )
        skillctl.write_asset_meta(legacy, {"name": "示例技能", "version": "1.0"})
        skillctl.save_state({
            "schema": 1,
            "installed": {"示例技能": {
                "version": "1.0",
                "hash": skillctl.digest(skillctl.file_map(legacy)),
            }},
        })
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(skillctl.do_install("示例技能"))
        self.assertFalse(legacy.exists())
        self.assertTrue((self.target / "示例技能-2.0" / "SKILL.md").exists())
        state = skillctl.load_state()["installed"]["示例技能"]
        self.assertEqual(state["directory"], "示例技能-2.0")
        self.assertEqual(state["version"], "2.0")

    def test_skill_publish_updates_agent_repo_manifest_ui_and_changelog(self):
        old_repo, old_local = self.register(version="2.0")
        self.publish(note="补充状态说明", push=True)
        new_repo = self.skills / "示例技能-3.0"
        new_local = self.target / "示例技能-3.0"
        self.assertFalse(old_repo.exists())
        self.assertFalse(old_local.exists())
        self.assertTrue((new_repo / "SKILL.md").exists())
        self.assertTrue((new_local / "SKILL.md").exists())
        meta = skillctl.read_asset_meta(new_local)
        self.assertEqual(meta["id"], "示例技能")
        self.assertEqual(meta["name"], "示例技能-3.0")
        self.assertEqual(meta["version"], "3.0")
        self.assertEqual(meta["repository"]["path"], "skills/示例技能-3.0")
        self.assertIn("name: 示例技能-3.0", (new_local / "SKILL.md").read_text(encoding="utf-8"))
        ui = (new_local / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "示例技能-3.0"', ui)
        self.assertIn("$示例技能-3.0", ui)
        state = skillctl.load_state()["installed"]["示例技能"]
        self.assertEqual(state["version"], "3.0")
        entry = skillctl.manifest_entry("示例技能", "skill")
        self.assertEqual(entry["name"], "示例技能-3.0")
        self.assertIn("补充状态说明", (self.root / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.assertTrue(self.preflight.call_args[0][1])
        self.assertTrue(self.commit.call_args[0][5])

    def test_publish_updates_readme_and_classification_links(self):
        self.register(version="2.0")
        (self.root / "README.md").write_text(
            "| Skill ID | 版本 | 用途 |\n| 示例技能 | 2.0 | 示例 |\n", encoding="utf-8"
        )
        (self.root / "分类索引.md").write_text(
            "[示例技能](skills/示例技能-2.0/SKILL.md)\n", encoding="utf-8"
        )
        self.publish()
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        index = (self.root / "分类索引.md").read_text(encoding="utf-8")
        self.assertIn("| 示例技能 | 3.0 |", readme)
        self.assertIn("skills/示例技能-3.0/SKILL.md", index)
        self.assertNotIn("示例技能-2.0", index)
        paths = self.commit.call_args[0][0]
        self.assertIn("skills/示例技能-3.0", paths)
        self.assertIn("skills/示例技能-2.0", paths)
        self.assertIn("分类索引.md", paths)

    def test_consecutive_publish_increments_integer(self):
        self.register(version="2.0")
        self.publish()
        self.publish(note="第二次更新")
        self.assertTrue((self.target / "示例技能-4.0").exists())
        self.assertTrue((self.skills / "示例技能-4.0").exists())
        self.assertFalse((self.target / "示例技能-3.0").exists())

    def test_no_push_is_explicitly_passed_to_git_layer(self):
        self.register(version="2.0")
        self.publish(push=False)
        self.assertFalse(self.preflight.call_args[0][1])
        self.assertFalse(self.commit.call_args[0][5])
        self.assertTrue((self.target / "示例技能-3.0").exists())

    def test_push_failure_keeps_agent_on_old_version(self):
        old_repo, old_local = self.register(version="2.0")
        self.commit.side_effect = SystemExit("模拟推送失败")
        with self.assertRaises(SystemExit):
            self.publish()
        self.assertTrue(old_local.exists())
        self.assertFalse((self.target / "示例技能-3.0").exists())
        self.assertTrue((self.skills / "示例技能-3.0").exists())
        self.assertFalse(old_repo.exists())
        state = skillctl.load_state()["installed"]["示例技能"]
        self.assertEqual(state["version"], "2.0")

    def test_local_repo_version_mismatch_stops_before_git(self):
        _, local = self.register(version="2.0")
        meta = skillctl.read_asset_meta(local)
        meta["version"] = "1.0"
        skillctl.write_asset_meta(local, meta)
        with self.assertRaises(SystemExit):
            self.publish()
        self.preflight.assert_not_called()
        self.commit.assert_not_called()

    def test_prompt_uses_same_version_and_github_sync_system(self):
        self.register(asset_id="示例提示", version="1.0", kind="prompt")
        self.publish(asset_id="示例提示", kind="prompt", note="优化提示词约束")
        package = self.prompts / "示例提示-2.0"
        meta = skillctl.read_asset_meta(package, "prompt")
        self.assertEqual(meta["name"], "示例提示-2.0")
        self.assertEqual(meta["repository"]["path"], "prompts/示例提示-2.0")
        self.assertTrue((self.target / "示例提示-2.0" / "PROMPT.md").exists())
        self.assertIsNotNone(skillctl.manifest_entry("示例提示", "prompt"))

    def test_new_prompt_starts_at_one(self):
        self.use_kind("prompt")
        local = self.target / "新提示"
        local.mkdir()
        (local / "PROMPT.md").write_text("请完成示例任务\n", encoding="utf-8")
        skillctl.write_asset_meta(local, {"version": "0.0"}, "prompt")
        self.publish(asset_id="新提示", kind="prompt")
        self.assertEqual(skillctl.read_asset_meta(self.target / "新提示-1.0", "prompt")["version"], "1.0")
        self.assertTrue((self.prompts / "新提示-1.0" / "PROMPT.md").exists())

    def test_empty_note_stops_before_changes(self):
        old_repo, old_local = self.register(version="2.0")
        with self.assertRaises(SystemExit):
            self.publish(note="  ")
        self.assertTrue(old_repo.exists())
        self.assertTrue(old_local.exists())
        self.commit.assert_not_called()

    def test_cli_requires_note(self):
        with patch("sys.argv", ["skillctl", "publish", "示例技能"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                skillctl.main("skill")
        self.assertEqual(error.exception.code, 2)


@unittest.skipUnless(shutil.which("git"), "需要 Git")
class GitIntegrationTests(unittest.TestCase):
    def test_real_fetch_commit_push_and_agent_switch_with_bare_remote(self):
        with tempfile.TemporaryDirectory(prefix="assetctl-git-test-", dir=skillctl.REPO.parent) as temp:
            root = Path(temp)
            remote = root / "remote.git"
            work = root / "work"
            installed = root / "installed"

            def run(*args):
                return subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8")

            def git(cwd, *args):
                return run("git", "-C", str(cwd), *args)

            run("git", "init", "--bare", str(remote))
            run("git", "init", str(work))
            git(work, "config", "user.name", "Asset Test")
            git(work, "config", "user.email", "asset-test@example.invalid")
            git(work, "checkout", "-b", "main")
            (work / "skills").mkdir()
            (work / "prompts").mkdir()
            (work / "README.md").write_text("| Skill ID | 版本 | 用途 |\n| 示例技能 | 2.0 | 示例 |\n", encoding="utf-8")
            (work / "分类索引.md").write_text("[示例技能](skills/示例技能-2.0/SKILL.md)\n", encoding="utf-8")
            (work / "CHANGELOG.md").write_text("# 变更记录\n\n按时间倒序，最新在最上面。\n", encoding="utf-8")

            package = "示例技能-2.0"
            source = work / "skills" / package
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\nname: 示例技能-2.0\ndescription: 示例\n---\n旧内容\n", encoding="utf-8"
            )
            repository = {"url": str(remote), "branch": "main", "path": f"skills/{package}"}
            meta = {
                "id": "示例技能", "name": package, "version": "2.0",
                "entry": "SKILL.md", "summary": "示例", "repository": repository,
            }
            (source / "skill.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            manifest = {
                "schema": 2,
                "repository": {"url": str(remote), "branch": "main"},
                "skills": [{**meta, "directory": package}],
                "prompts": [],
            }
            (work / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            git(work, "add", "-A")
            git(work, "commit", "-m", "初始 2.0")
            git(work, "push", str(remote), "HEAD:refs/heads/main")

            local = installed / package
            shutil.copytree(source, local)
            with patch.multiple(
                skillctl,
                REPO=work,
                SKILLS_DIR=work / "skills",
                PROMPTS_DIR=work / "prompts",
                MANIFEST=work / "manifest.json",
                TARGET=installed,
                STATE_FILE=installed / ".skillctl.json",
                BACKUP_DIR=root / "backups",
            ):
                skillctl.save_state({"schema": 2, "installed": {"示例技能": {
                    "id": "示例技能", "name": package, "directory": package,
                    "version": "2.0", "repository": repository,
                    "hash": skillctl.digest(skillctl.file_map(local)),
                }}})
                (local / "SKILL.md").write_text(
                    "---\nname: 示例技能-2.0\ndescription: 示例\n---\n本地新修改\n", encoding="utf-8"
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    skillctl.cmd_publish(argparse.Namespace(
                        name="示例技能", note="真实本地 Git 推送测试", bump="next", push=True
                    ), "skill")
                self.assertTrue((installed / "示例技能-3.0" / "SKILL.md").exists())
                self.assertFalse(local.exists())
                self.assertEqual(skillctl.load_state()["installed"]["示例技能"]["version"], "3.0")

            remote_meta = json.loads(git(remote, "show", "main:skills/示例技能-3.0/skill.json").stdout)
            self.assertEqual(remote_meta["version"], "3.0")
            self.assertEqual(remote_meta["repository"]["path"], "skills/示例技能-3.0")
            log = git(remote, "log", "-1", "--pretty=%s", "main").stdout
            self.assertIn("真实本地 Git 推送测试", log)


if __name__ == "__main__":
    unittest.main()
