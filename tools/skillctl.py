#!/usr/bin/env python3
"""Integer-versioned Skill installation and publishing; Python 3.10+, Git, stdlib only."""
from __future__ import annotations
import argparse
import json
import os
import sys
import hashlib
from contextlib import ExitStack
from difflib import unified_diff
from pathlib import Path
import skillstore as store


def inventory(args):
    ref = store.remote_ref(store.REPO, args.offline)
    data = store.manifest(store.REPO, ref)
    if data.get("schema") != 2:
        raise ValueError("远端尚未升级；测试本地迁移请使用 --offline")
    return ref, data


def cmd_list(args):
    ref, data = inventory(args)
    return {"source": "本地 HEAD（离线）" if args.offline else "origin/main", "commit": store.git(store.REPO, "rev-parse", ref), "skills": data["skills"]}


def cmd_history(args):
    ref, data = inventory(args)
    values = []
    for skill in data["skills"] if args.all else [store.find_skill(data, args.name)]:
        value = {"name": skill["name"], "releases": [store.release(store.REPO, skill, v, ref) for v in range(1, skill["version"] + 1)]}
        if args.revisions:
            value["revisions"] = store.git(store.REPO, "log", "--format=%H %cI %s", ref, "--", f"skills/{skill['name']}").splitlines()
        values.append(value)
    return values if args.all else values[0]


def cmd_install(args):
    ref, data = inventory(args)
    skill = store.find_skill(data, args.name)
    version = args.version or skill["version"]
    if version > skill["version"]:
        raise ValueError("指定版本尚未发布")
    record = store.install(store.REPO, args.target, skill, store.release(store.REPO, skill, version, ref), pinned=args.version is not None, force=args.force)
    return {"name": skill["name"], "version": record["version"], "pinned": record["pinned"], "source": "离线 HEAD" if args.offline else "origin/main", "target": str(args.target / skill["name"])}


def cmd_status(args):
    _, data = inventory(args)
    local = store.state(args.target)["installed"]
    rows = []
    for skill in data["skills"]:
        name, status = skill["name"], "未安装"
        record = local.get(name)
        if (args.target / name).exists():
            if not record or "content_sha256" not in record:
                status = "无可用安装基线"
            else:
                try:
                    changed = store.fingerprint(store.package(args.target / name, record)) != record["content_sha256"]
                    status = "本地有改动" if changed else "版本已锁定" if record.get("pinned") else "副本旧于安装版" if record["version"] > skill["version"] else "可更新" if record["version"] < skill["version"] else "已是最新"
                except ValueError as exc:
                    status = f"安装异常：{exc}"
        rows.append({"name": name, "latest": skill["version"], "installed": record.get("version") if record else None,
                     "status": status, "maturity": skill.get("status", "未记录"), "dependencies": skill.get("dependencies", [])})
    return {"source": "离线 HEAD" if args.offline else "origin/main", "skills": rows,
            "pending_publish": sorted(p.stem for p in (store.REPO / ".skillctl-local" / "pending").glob("*.json"))}


def cmd_update(args):
    ref, data = inventory(args)
    local = store.state(args.target)["installed"]
    rows, errors = [], []
    for skill in data["skills"] if args.all else [store.find_skill(data, args.name)]:
        name = skill["name"]
        record = local.get(name)
        if not record:
            rows.append({"name": name, "result": "未安装，跳过"})
            continue
        if record.get("pinned") and not args.unpin:
            rows.append({"name": name, "result": "版本已锁定，跳过"})
            continue
        try:
            if "content_sha256" not in record:
                raise ValueError("旧安装记录需先 install 接管")
            if record["version"] > skill["version"]:
                raise ValueError("当前副本旧于安装版，不能隐式降级；请在线同步")
            if record["version"] == skill["version"] and not args.unpin:
                if store.fingerprint(store.package(args.target / name, record)) != record["content_sha256"]:
                    raise ValueError("本地有未发布修改")
                rows.append({"name": name, "result": "已是最新"})
                continue
            store.install(store.REPO, args.target, skill, store.release(store.REPO, skill, skill["version"], ref), force=args.force)
            rows.append({"name": name, "version": skill["version"], "result": "已更新"})
        except ValueError as exc:
            errors.append({"name": name, "error": str(exc)})
    print(json.dumps({"results": rows, "errors": errors}, ensure_ascii=False, indent=2))
    if errors:
        raise ValueError("部分技能更新失败，未覆盖其本地改动")


def cmd_diff(args):
    ref, data = inventory(args)
    skill = store.find_skill(data, args.name)
    record = store.state(args.target)["installed"].get(skill["name"])
    if not record or "content_sha256" not in record:
        raise ValueError("缺少受管安装记录")
    local = store.package(args.target / skill["name"], record)
    _, remote = store.source(store.REPO, store.release(store.REPO, skill, skill["version"], ref))
    changes = []
    for name in sorted(local.keys() | remote.keys()):
        if local.get(name) == remote.get(name):
            continue
        row = {"file": name, "status": "新增于远端" if name not in local else "远端已删除" if name not in remote else "内容不同"}
        try:
            row["diff"] = "\n".join(unified_diff(local.get(name, b"").decode("utf-8").splitlines(), remote.get(name, b"").decode("utf-8").splitlines(), fromfile=f"local/{name}", tofile=f"remote/{name}", lineterm=""))
        except UnicodeDecodeError:
            row["diff"] = "二进制文件不同"
        changes.append(row)
    return changes


def cmd_verify(args):
    count = store.verify(store.REPO, args.base)
    releases = 0
    if args.deep:
        for path in (store.REPO / "releases").glob("*/*.json"):
            store.source(store.REPO, store.read_json(path))
            releases += 1
    return {"result": "校验通过", "skills": count, "historical_packages_checked": releases}


def cmd_migrate(args):
    from skillmigrate import migrate
    mappings = migrate(store.REPO)
    for path in (store.REPO / "releases").glob("*/*.json"):
        entry = store.read_json(path)
        if not entry.get("source_commit"):
            continue
        tag = entry["release_ref"]
        existing = store.git(store.REPO, "rev-parse", "--verify", f"refs/tags/{tag}", check=False)
        if existing and existing != entry["source_commit"]:
            raise ValueError(f"迁移标签冲突：{tag}")
        if not existing:
            store.git(store.REPO, "tag", tag, entry["source_commit"])
    return {"result": "迁移和本地标签完成，尚未提交或推送", "releases": mappings}


def cmd_sync(args):
    path = store.REPO / ".skillctl-local" / "config.json"
    current = store.read_json(path) if path.exists() else {"auto_sync": False}
    if args.enable:
        current = {"auto_sync": True, "origin": store.git(store.REPO, "remote", "get-url", "origin"), "enabled_at": store.now()}
        store.write_json(path, current)
    elif args.disable:
        current["auto_sync"] = False
        store.write_json(path, current)
    return {"auto_sync": current.get("auto_sync", False), "scope": "当前 clone，本机配置，不随包分发"}


def cmd_cancel_pending(args):
    for path in (store.REPO / ".skillctl-local" / "pending").glob("*.json"):
        pending = store.read_json(path)
        if args.name not in {pending["meta"]["name"], pending["meta"]["id"]}:
            continue
        ident, commit = pending["meta"]["id"], pending["commit"]
        archive = store.REPO / ".skillctl-local" / "archive" / f"{ident}-{commit}.json"
        store.write_json(archive, pending)
        store.git(store.REPO, "update-ref", f"refs/skillctl/archive/{ident}/{commit}", commit)
        path.unlink()
        store.git(store.REPO, "update-ref", "-d", f"refs/skillctl/pending/{ident}", commit)
        return {"result": "待同步发布已归档，本地文件和远端版本未改动", "archive": str(archive), "commit": commit}
    raise ValueError("未找到对应待同步发布")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Skill 整数版本、历史安装与同步管理")
    parser.add_argument("--target", type=Path, default=Path(os.environ.get("SKILLCTL_TARGET", str(Path.home() / ".workbuddy" / "skills"))))
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("list", "status", "history", "install", "update", "diff", "verify", "migrate", "publish", "sync", "cancel-pending"):
        p = sub.add_parser(command)
        p.add_argument("--json", action="store_true", help="结构化 JSON 输出（默认也为 JSON）")
        if command in {"list", "status", "history", "install", "update", "diff"}:
            p.add_argument("--offline", action="store_true", help="仅使用本地 HEAD，不声称为远端最新")
        if command in {"install", "diff", "publish", "cancel-pending"}:
            p.add_argument("name")
        if command == "history":
            group = p.add_mutually_exclusive_group(required=True)
            group.add_argument("name", nargs="?")
            group.add_argument("--all", action="store_true")
            p.add_argument("--revisions", action="store_true")
        if command == "install":
            p.add_argument("--version", type=int)
            p.add_argument("--force", action="store_true", help="覆盖前自动备份")
        if command == "update":
            group = p.add_mutually_exclusive_group(required=True)
            group.add_argument("name", nargs="?")
            group.add_argument("--all", action="store_true")
            p.add_argument("--force", action="store_true")
            p.add_argument("--unpin", action="store_true", help="明确解除版本锁定并更新")
        if command == "verify":
            p.add_argument("--base", help="检查既有发布记录未被改写")
            p.add_argument("--deep", action="store_true", help="逐版校验历史业务快照")
        if command == "publish":
            p.add_argument("--note", required=True)
            p.add_argument("--new", action="store_true", help="明确新增技能，需本地 skill.json")
            p.add_argument("--id", help="新技能稳定英文 id")
            p.add_argument("--adopt", action="store_true", help="同一可信来源的新 clone 接管已有安装")
        if command == "sync":
            group = p.add_mutually_exclusive_group()
            group.add_argument("--enable", action="store_true", help="所有者启用当前 clone 的自动回传")
            group.add_argument("--disable", action="store_true")
    args = parser.parse_args(argv)
    args.target = args.target.expanduser().resolve()
    if getattr(args, "version", None) is not None and args.version < 1:
        parser.error("--version 必须为正整数")
    try:
        with ExitStack() as locks:
            if args.command in {"install", "update", "publish", "migrate", "sync", "cancel-pending"}:
                locks.enter_context(store.operation_lock(store.REPO / ".skillctl-local" / "operation.lock"))
            if args.command in {"install", "update", "publish"}:
                key = hashlib.sha256(str(args.target).encode()).hexdigest()[:16]
                locks.enter_context(store.operation_lock(args.target.parent / f".skillctl-target-{key}.lock"))
            if args.command == "publish":
                from skillpublish import publish
                value = publish(store.REPO, args)
            else:
                value = globals()["cmd_" + args.command.replace("-", "_")](args)
        if value is not None:
            print(json.dumps(value, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, SyntaxError) as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
