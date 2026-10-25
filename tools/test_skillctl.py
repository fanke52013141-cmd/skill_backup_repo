"""Behavioral integration tests against isolated local bare remotes (no GitHub writes)."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import skillmigrate
import skillpublish
import skillstore as store

ROOT = Path(__file__).resolve().parent.parent
NAME = "测试技能"
IDENT = "test-skill"


def commit(repo, message):
    store.git(repo, "add", ".")
    store.git(repo, "-c", "user.name=Skillctl Tests", "-c", "user.email=tests@example.invalid", "commit", "-m", message)
    return store.git(repo, "rev-parse", "HEAD")


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="skillctl-tests-")
        cls.root = Path(cls.temp.name).resolve()
        cls.seed = cls.root / "seed"
        cls.seed.mkdir()
        store.git(cls.seed, "init", "--initial-branch=main")
        shutil.copytree(ROOT / "tools", cls.seed / "tools", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "policy", cls.seed / "policy")
        shutil.copy(ROOT / ".gitignore", cls.seed)
        shutil.copy(ROOT / ".gitattributes", cls.seed)
        skills = []
        for name, ident in ((NAME, IDENT), ("sample-skill", "sample-skill")):
            folder = cls.seed / "skills" / name
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: 测试说明\n---\n\n# 内容\n\n初版\n", encoding="utf-8")
            (folder / "references").mkdir()
            (folder / "references" / "rule.md").write_text("初版规则\n", encoding="utf-8")
            meta = {"name": name, "slug": ident, "version": "1.0.0", "summary": "测试用途", "origin": "upstream", "license": "MIT"}
            store.write_json(folder / "skill.json", meta)
            (folder / "LICENSE").write_text("MIT test license", encoding="utf-8")
            skills.append(meta)
        store.write_json(cls.seed / "manifest.json", {"schema": 1, "skills": skills})
        cls.old = commit(cls.seed, "两个初版")
        folder = cls.seed / "skills" / NAME
        (folder / "references" / "rule.md").write_text("第二版规则\n", encoding="utf-8")
        meta = store.read_json(folder / "skill.json")
        meta["version"] = "2.0.0"
        store.write_json(folder / "skill.json", meta)
        skills[0] = meta
        store.write_json(cls.seed / "manifest.json", {"schema": 1, "skills": skills})
        cls.latest_legacy = commit(cls.seed, "中文第二版")
        cls.mapping = skillmigrate.migrate(cls.seed)
        for entry in cls.mapping:
            store.git(cls.seed, "tag", entry["release_ref"], entry["source_commit"])
        commit(cls.seed, "整数版本迁移")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=self.root)
        self.root_case = Path(self.temp.name).resolve()
        self.remote = self.root_case / "remote.git"
        subprocess.run(["git", "clone", "--bare", str(self.seed), str(self.remote)], check=True, capture_output=True)
        self.repo = self.root_case / "repo"
        subprocess.run(["git", "clone", str(self.remote), str(self.repo)], check=True, capture_output=True)
        self.target = self.root_case / "installed"
        store.write_json(self.repo / ".skillctl-local" / "config.json", {"auto_sync": True, "origin": str(self.remote)})

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, success=True, target=None):
        result = subprocess.run([sys.executable, str(self.repo / "tools" / "skillctl.py"), "--target", str(target or self.target), *args],
                                capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1"))
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else result.stderr

    def install(self, *extra, name=NAME, target=None):
        return self.cli("install", name, *extra, target=target)

    def edit(self, name=NAME, suffix="补充规则\n", target=None):
        path = (target or self.target) / name / "references" / "rule.md"
        path.write_text(path.read_text(encoding="utf-8") + suffix, encoding="utf-8")

    def args(self, **overrides):
        fields = dict(name=NAME, target=self.target, note="补充一致性规则", new=False, id=None, adopt=False)
        fields.update(overrides)
        return argparse.Namespace(**fields)

    def local_status(self):
        return next(s for s in self.cli("status")["skills"] if s["name"] == NAME)["status"]

    def test_migration_preserves_old_content_and_license(self):
        self.assertEqual([e["version"] for e in self.mapping if e["name"] == NAME], [1, 2])
        for entry in self.mapping:
            _, files = store.source(self.repo, entry)
            self.assertEqual(store.fingerprint(files), entry["content_sha256"])
            self.assertIn("LICENSE", files)
        self.assertEqual(skillmigrate.migrate(self.repo), [])

    def test_latest_install_injects_once_and_status_is_clean(self):
        self.assertEqual(self.install()["version"], 2)
        self.install()
        text = (self.target / NAME / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(text.count(store.START), 1)
        self.assertEqual(self.local_status(), "已是最新")
        self.assertTrue((self.target / NAME / ".skillctl" / "maintenance.md").exists())

    def test_historical_install_is_pinned_and_unpin_is_explicit(self):
        self.install("--version", "1")
        self.assertEqual((self.target / NAME / "references" / "rule.md").read_text(encoding="utf-8"), "初版规则\n")
        self.cli("update", "--all")
        self.assertEqual(store.state(self.target)["installed"][NAME]["version"], 1)
        self.cli("update", NAME, "--unpin")
        self.assertEqual(store.state(self.target)["installed"][NAME]["version"], 2)

    def test_english_install_keeps_upstream_license(self):
        self.install(name="sample-skill")
        self.assertTrue((self.target / "sample-skill" / "LICENSE").exists())
        self.assertEqual(store.read_json(self.target / "sample-skill" / "skill.json")["origin"], "upstream")

    def test_dirty_install_refused_and_force_backs_up(self):
        self.install()
        self.edit()
        self.install_attempt = self.cli("install", NAME, success=False)
        self.assertIn("本地有改动", self.install_attempt)
        self.cli("install", NAME, "--force")
        backups = list((self.root_case / ".skillctl_backup").glob(f"{NAME}-*/references/rule.md"))
        self.assertTrue(any("补充规则" in p.read_text(encoding="utf-8") for p in backups))

    def test_same_version_dirty_update_returns_failure(self):
        self.install()
        self.edit()
        self.cli("update", NAME, success=False)
        self.assertEqual(self.local_status(), "本地有改动")

    def test_diff_includes_references_and_deletions(self):
        self.install()
        self.edit()
        (self.target / NAME / "LICENSE").unlink()
        self.assertEqual({row["file"] for row in self.cli("diff", NAME)}, {"LICENSE", "references/rule.md"})

    def test_publish_no_change_does_not_create_version(self):
        self.install()
        result = self.cli("publish", NAME, "--note", "无需修改")
        self.assertIn("无业务变化", result["result"])
        self.assertEqual(store.find_skill(store.manifest(self.repo, "origin/main"), NAME)["version"], 2)

    def test_publish_isolates_unrelated_staged_files_and_refreshes_install(self):
        self.install()
        self.edit()
        extra = self.repo / "unrelated.txt"
        extra.write_text("用户其他任务", encoding="utf-8")
        store.git(self.repo, "add", "unrelated.txt")
        result = self.cli("publish", NAME, "--note", "补充规则")
        self.assertEqual(result["version"], 3)
        self.assertEqual(store.state(self.target)["installed"][NAME]["version"], 3)
        self.assertEqual(store.git(self.repo, "diff", "--cached", "--name-only"), "unrelated.txt")
        self.assertNotIn("unrelated.txt", store.git(self.repo, "ls-tree", "-r", "--name-only", "origin/main"))
        raw = store.git(self.repo, "show", f"origin/main:skills/{NAME}/SKILL.md")
        self.assertNotIn(store.START, raw)
        self.assertEqual(self.local_status(), "已是最新")

    def test_stale_install_cannot_overwrite_new_publication(self):
        old_target = self.root_case / "older-install"
        self.install(target=old_target)
        self.install()
        self.edit()
        self.cli("publish", NAME, "--note", "新版本")
        self.edit(target=old_target, suffix="过时内容\n")
        error = self.cli("publish", NAME, "--note", "旧安装", target=old_target, success=False)
        self.assertIn("基线过旧", error)

    def test_rejected_push_preserves_pending_and_retry_uses_same_version(self):
        self.install()
        self.edit()
        original = store.git
        def reject(repo, *args, **kwargs):
            if args and args[0] == "push":
                raise ValueError("simulated network failure")
            return original(repo, *args, **kwargs)
        with patch.object(store, "git", side_effect=reject):
            with self.assertRaises(ValueError):
                skillpublish.publish(self.repo, self.args())
        pending_file = self.repo / ".skillctl-local" / "pending" / f"{IDENT}.json"
        pending = store.read_json(pending_file)
        self.assertEqual(pending["meta"]["version"], 3)
        result = skillpublish.publish(self.repo, self.args())
        self.assertEqual(result["commit"], pending["commit"])
        self.assertEqual(result["version"], 3)
        self.assertFalse(pending_file.exists())

    def test_server_success_local_refresh_failure_can_recover(self):
        self.install()
        self.edit()
        with patch.object(store, "install", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                skillpublish.publish(self.repo, self.args())
        result = skillpublish.publish(self.repo, self.args())
        self.assertEqual(result["version"], 3)
        self.assertIn("无业务变化", skillpublish.publish(self.repo, self.args())["result"])

    def test_lost_push_response_is_confirmed_without_duplicate_version(self):
        self.install()
        self.edit()
        original = store.git
        def lost_response(repo, *args, **kwargs):
            result = original(repo, *args, **kwargs)
            if args and args[0] == "push":
                raise ValueError("connection lost after server accepted push")
            return result
        with patch.object(store, "git", side_effect=lost_response):
            self.assertEqual(skillpublish.publish(self.repo, self.args())["version"], 3)
        self.assertEqual(len(self.cli("history", NAME)["releases"]), 3)

    def test_unrelated_concurrent_publish_rebases_pending_without_losing_changes(self):
        self.install()
        self.install(name="sample-skill")
        self.edit()
        original = store.git
        def reject(repo, *args, **kwargs):
            if args and args[0] == "push":
                raise ValueError("offline")
            return original(repo, *args, **kwargs)
        with patch.object(store, "git", side_effect=reject):
            with self.assertRaises(ValueError):
                skillpublish.publish(self.repo, self.args())
        self.edit(name="sample-skill")
        self.cli("publish", "sample-skill", "--note", "另一个 Skill 更新")
        result = skillpublish.publish(self.repo, self.args())
        self.assertEqual(result["version"], 3)
        latest = store.manifest(self.repo, "origin/main")
        self.assertEqual(store.find_skill(latest, "sample-skill")["version"], 2)
        self.assertEqual(store.find_skill(latest, NAME)["version"], 3)

    def test_concurrent_same_skill_is_not_overwritten_and_pending_can_be_archived(self):
        self.install()
        self.edit()
        original = store.git
        def reject(repo, *args, **kwargs):
            if args and args[0] == "push":
                raise ValueError("offline")
            return original(repo, *args, **kwargs)
        with patch.object(store, "git", side_effect=reject):
            with self.assertRaises(ValueError):
                skillpublish.publish(self.repo, self.args())
        other = self.root_case / "other"
        subprocess.run(["git", "clone", str(self.remote), str(other)], check=True, capture_output=True)
        other_target = self.root_case / "other-target"
        skill = store.find_skill(store.manifest(other), NAME)
        store.install(other, other_target, skill, store.release(other, skill, 2))
        self.edit(target=other_target, suffix="另一设备的改动\n")
        store.write_json(other / ".skillctl-local" / "config.json", {"auto_sync": True, "origin": str(self.remote)})
        skillpublish.publish(other, self.args(target=other_target))
        with self.assertRaisesRegex(ValueError, "标签冲突"):
            skillpublish.publish(self.repo, self.args())
        archive = self.cli("cancel-pending", NAME)
        self.assertTrue(Path(archive["archive"]).exists())
        self.assertIn("补充规则", (self.target / NAME / "references" / "rule.md").read_text(encoding="utf-8"))
        self.assertEqual(store.find_skill(store.manifest(self.repo, "origin/main"), NAME)["version"], 3)

    def test_offline_old_head_cannot_silently_downgrade_after_publish(self):
        self.install()
        self.edit()
        self.cli("publish", NAME, "--note", "更新远端但不移动本地分支")
        self.cli("update", NAME, "--offline", success=False)
        self.cli("install", NAME, "--offline", success=False)
        self.assertEqual(store.state(self.target)["installed"][NAME]["version"], 3)

    def test_auto_sync_requires_local_opt_in_and_checks_origin(self):
        self.install()
        self.edit()
        self.cli("sync", "--disable")
        self.cli("publish", NAME, "--note", "测试", success=False)
        self.cli("sync", "--enable")
        store.git(self.repo, "remote", "set-url", "origin", str(self.seed))
        self.assertIn("origin", self.cli("publish", NAME, "--note", "测试", success=False))

    def test_new_skill_retry_after_server_success_does_not_fail_as_duplicate(self):
        name = "new-after-crash"
        folder = self.target / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: 新技能\n---\n正文\n", encoding="utf-8")
        store.write_json(folder / "skill.json", {"summary": "首次发布恢复"})
        args = self.args(name=name, new=True, id=name)
        with patch.object(store, "install", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                skillpublish.publish(self.repo, args)
        self.assertEqual(skillpublish.publish(self.repo, args)["version"], 1)

    def test_all_histories_and_lock_exclusion(self):
        self.assertEqual(len(self.cli("history", "--all")), 2)
        with store.operation_lock(self.repo / ".skillctl-local" / "operation.lock"):
            self.cli("sync", "--enable", success=False)

    def test_damaged_install_state_does_not_delete_previous_content(self):
        self.install()
        original = store.write_json
        before = (self.target / NAME / "SKILL.md").read_bytes()
        def fail_state(path, value):
            if Path(path).resolve() == store.state_path(self.target).resolve():
                raise OSError("disk error")
            return original(path, value)
        skill = store.find_skill(store.manifest(self.repo), NAME)
        with patch.object(store, "write_json", side_effect=fail_state):
            with self.assertRaises(OSError):
                store.install(self.repo, self.target, skill, store.release(self.repo, skill, 2))
        self.assertEqual((self.target / NAME / "SKILL.md").read_bytes(), before)

    def test_tampered_management_block_is_not_removed(self):
        self.install()
        path = self.target / NAME / "SKILL.md"
        path.write_text(path.read_text(encoding="utf-8").replace(store.END, "broken"), encoding="utf-8")
        self.assertIn("管理段", self.cli("publish", NAME, "--note", "测试", success=False))

    def test_history_and_invalid_versions(self):
        self.assertEqual(len(self.cli("history", NAME, "--revisions")["releases"]), 2)
        self.cli("install", NAME, "--version", "99", success=False)
        self.cli("install", NAME, "--version", "0", success=False)
        self.cli("install", "../escape", success=False)

    def test_immutable_history_guard(self):
        old = store.git(self.repo, "rev-parse", "HEAD")
        path = self.repo / "releases" / IDENT / "1.json"
        entry = store.read_json(path)
        entry["note"] = "篡改历史"
        store.write_json(path, entry)
        with self.assertRaisesRegex(ValueError, "不可修改"):
            store.verify(self.repo, old)

    def test_secrets_and_invalid_python_are_rejected(self):
        self.install()
        secret = self.target / NAME / ".env"
        secret.write_text("SECRET=not-a-real-secret", encoding="utf-8")
        self.cli("publish", NAME, "--note", "拒绝私有文件", success=False)
        secret.unlink()
        (self.target / NAME / "broken.py").write_text("def broken(:", encoding="utf-8")
        self.cli("publish", NAME, "--note", "拒绝错误脚本", success=False)

    def test_offline_is_explicit_and_corrupt_snapshot_refused(self):
        self.assertIn("离线", self.cli("list", "--offline")["source"])
        item = store.manifest(self.repo)["skills"][0]
        entry = store.release(self.repo, item, item["version"])
        entry["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "校验值"):
            store.install(self.repo, self.target, item, entry)

    def test_new_skill_can_publish_without_manual_management_injection(self):
        folder = self.target / "new-skill"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("---\nname: new-skill\ndescription: 新技能\n---\n\n正文\n", encoding="utf-8")
        store.write_json(folder / "skill.json", {"summary": "测试新增"})
        result = self.cli("publish", "new-skill", "--new", "--id", "new-skill", "--note", "首次收录")
        self.assertEqual(result["version"], 1)
        self.assertIn(store.START, (folder / "SKILL.md").read_text(encoding="utf-8"))

    def test_crlf_text_without_extension_keeps_hash_after_git_commit(self):
        self.install()
        (self.target / NAME / "LICENSE").write_bytes(b"MIT test license\r\nTest fixture addition\r\n")
        self.cli("publish", NAME, "--note", "Windows text normalization")
        skill = store.find_skill(store.manifest(self.repo, "origin/main"), NAME)
        _, files = store.source(self.repo, store.release(self.repo, skill, 3, "origin/main"))
        self.assertEqual(files["LICENSE"], b"MIT test license\nTest fixture addition\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
