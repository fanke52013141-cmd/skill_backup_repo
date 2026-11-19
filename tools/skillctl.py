#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skillctl / promptctl — Skill 与 Prompt 的版本、安装和 GitHub 同步工具。

稳定 id 标识同一个资产；name、仓库目录和本地安装目录统一为 id-N.0。
publish 默认提交并推送 GitHub，成功后才切换本地安装版本；--no-push 仅本地发布。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime
from difflib import unified_diff
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
PROMPTS_DIR = REPO / "prompts"
MANIFEST = REPO / "manifest.json"

TARGET = Path.home() / ".workbuddy" / "skills"
STATE_FILE = TARGET / ".skillctl.json"
BACKUP_DIR = TARGET.parent / ".skillctl_backup"

EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".skillctl_backup", ".promptctl_backup"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".DS_Store"}
DOC_FILES = ["README.md", "分类索引.md"]


# ---------- 基础配置 ----------

def collection(kind: str) -> str:
    if kind not in {"skill", "prompt"}:
        raise ValueError(f"未知资产类型：{kind}")
    return f"{kind}s"


def asset_root(kind: str) -> Path:
    return SKILLS_DIR if kind == "skill" else PROMPTS_DIR


def meta_filename(kind: str) -> str:
    return f"{kind}.json"


def entry_filename(kind: str) -> str:
    return "SKILL.md" if kind == "skill" else "PROMPT.md"


def set_target(raw: str, kind: str = "skill") -> None:
    global TARGET, STATE_FILE, BACKUP_DIR
    TARGET = Path(raw).expanduser().resolve()
    STATE_FILE = TARGET / f".{kind}ctl.json"
    BACKUP_DIR = TARGET.parent / f".{kind}ctl_backup"


def validate_id(asset_id: str) -> None:
    if not asset_id or asset_id in {".", ".."} or asset_id.startswith("."):
        raise SystemExit("资产 id 不能为空、以点开头或使用相对路径")
    if any(c in asset_id for c in "/\\\0"):
        raise SystemExit(f"资产 id 含非法路径字符：{asset_id}")


def asset_name(asset_id: str, version: str) -> str:
    validate_id(asset_id)
    if not re.fullmatch(r"[1-9]\d*\.0", str(version)):
        raise SystemExit(f"版本必须为 N.0：{version}")
    return f"{asset_id}-{version}"


def skill_dir_name(name: str, version: str) -> str:
    return asset_name(name, version)


def parse_version(value: str) -> tuple:
    parts = []
    for chunk in str(value).split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def bump_version(version: str, level: str = "next") -> str:
    if level not in {"next", "patch", "minor", "major"}:
        raise ValueError(f"不支持的升版方式：{level}")
    if not re.fullmatch(r"[1-9]\d*\.(?:0|\d+\.\d+)", str(version)):
        raise SystemExit(f"无效版本「{version}」；当前格式为 N.0，旧版可为 N.x.y")
    return f"{int(str(version).split('.')[0]) + 1}.0"


# ---------- 输出 ----------

def init_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def dwidth(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - dwidth(text))


def say(msg: str = "") -> None:
    print(msg)


def ok(msg: str) -> None:
    print(f"  [完成] {msg}")


def warn(msg: str) -> None:
    print(f"  [注意] {msg}")


def fail(msg: str) -> None:
    print(f"  [失败] {msg}")


# ---------- 元数据与仓库 ----------

def load_manifest() -> dict:
    if not MANIFEST.exists():
        raise SystemExit("找不到 manifest.json，仓库尚未初始化")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data.setdefault("schema", 2)
    data.setdefault("skills", [])
    data.setdefault("prompts", [])
    data.setdefault("repository", {})
    return data


def save_manifest(data: dict) -> None:
    data["schema"] = 2
    data["updated"] = datetime.now().strftime("%Y-%m-%d")
    for kind in ("skill", "prompt"):
        key = collection(kind)
        data.setdefault(key, [])
        data[key] = sorted(data[key], key=lambda x: x.get("id", x.get("name", "")))
    MANIFEST.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def entry_id(entry: dict) -> str:
    return entry.get("id") or entry.get("name", "")


def manifest_entry(asset_id: str, kind: str, data: dict | None = None) -> dict | None:
    data = data or load_manifest()
    return next((s for s in data[collection(kind)] if entry_id(s) == asset_id), None)


def repo_asset(asset_id: str, kind: str = "skill") -> Path:
    data = load_manifest()
    item = manifest_entry(asset_id, kind, data)
    if item:
        path = asset_root(kind) / item["directory"]
        if path.is_dir():
            return path
        raise SystemExit(f"{kind}「{asset_id}」的仓库目录不存在：{path.name}")
    avail = "、".join(entry_id(s) for s in data[collection(kind)])
    raise SystemExit(f"仓库里没有 {kind}「{asset_id}」。现有：{avail}")


def repo_skill(name: str) -> Path:
    return repo_asset(name, "skill")


def read_asset_meta(path: Path, kind: str = "skill") -> dict:
    meta_file = path / meta_filename(kind)
    if not meta_file.exists():
        raise SystemExit(f"{path.name} 缺少 {meta_filename(kind)}，无法读取版本")
    return json.loads(meta_file.read_text(encoding="utf-8"))


def write_asset_meta(path: Path, meta: dict, kind: str = "skill") -> None:
    (path / meta_filename(kind)).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def read_skill_meta(path: Path) -> dict:
    return read_asset_meta(path, "skill")


def write_skill_meta(path: Path, meta: dict) -> None:
    write_asset_meta(path, meta, "skill")


def repository_for(meta: dict, data: dict, kind: str, package_name: str) -> dict:
    result = dict(data.get("repository") or {})
    result.update(meta.get("repository") or {})
    result.setdefault("branch", "main")
    result["path"] = f"{collection(kind)}/{package_name}"
    if not result.get("url"):
        raise SystemExit("缺少 GitHub repository.url，无法建立同步关系")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", result["branch"]) or ".." in result["branch"]:
        raise SystemExit(f"仓库分支名无效：{result['branch']}")
    return result


# ---------- 状态、哈希与本地安装 ----------

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"schema": 2, "installed": {}}
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    state.setdefault("schema", 2)
    state.setdefault("installed", {})
    return state


def save_state(state: dict) -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.suffix in EXCLUDE_SUFFIX or path.name in EXCLUDE_SUFFIX or ".local." in path.name:
            continue
        yield path, rel


def file_map(root: Path) -> dict:
    return {rel.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path, rel in iter_files(root)}


def digest(files: dict) -> str:
    result = hashlib.sha256()
    for name in sorted(files):
        result.update(name.encode("utf-8"))
        result.update(files[name].encode("utf-8"))
    return result.hexdigest()[:16]


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".skillctl*", ".promptctl*", "*.local.*"),
    )


def find_local(asset_id: str, kind: str = "skill", state: dict | None = None) -> Path | None:
    state = state or load_state()
    record = state["installed"].get(asset_id)
    if record:
        directory = record.get("directory")
        if directory:
            candidate = TARGET / directory
            if candidate.is_dir():
                return candidate
    legacy = TARGET / asset_id
    if legacy.is_dir():
        return legacy
    matches = []
    if TARGET.exists():
        for path in TARGET.iterdir():
            if not path.is_dir() or path.name.startswith("."):
                continue
            try:
                meta = read_asset_meta(path, kind)
            except (SystemExit, json.JSONDecodeError):
                continue
            if entry_id(meta) == asset_id or meta.get("name") == asset_id:
                matches.append(path)
    if len(matches) > 1:
        names = "、".join(p.name for p in matches)
        raise SystemExit(f"本地存在多个「{asset_id}」副本：{names}；请先保留唯一版本")
    return matches[0] if matches else None


def backup_existing(path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"{path.name}-{stamp}"
    shutil.copytree(path, dest)
    return dest


def do_install(asset_id: str, force: bool = False, quiet: bool = False, kind: str = "skill") -> bool:
    src = repo_asset(asset_id, kind)
    meta = read_asset_meta(src, kind)
    target = TARGET / meta["name"]
    state = load_state()
    existing = find_local(asset_id, kind, state)
    old_target = None

    if existing:
        record = state["installed"].get(asset_id)
        changed = not record or digest(file_map(existing)) != record.get("hash")
        if changed and not force:
            fail(f"「{asset_id}」本地已存在或被修改，已停止；确认后使用 --force")
            return False
        if changed:
            dest = backup_existing(existing)
            warn(f"已备份被修改的本地版本到 {dest}")
        if existing == target:
            shutil.rmtree(existing)
        else:
            old_target = existing

    if target.exists():
        fail(f"目标目录已存在且不属于当前资产：{target}")
        return False
    TARGET.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target)
    if old_target and old_target.exists():
        shutil.rmtree(old_target)

    state["installed"][asset_id] = {
        "id": asset_id,
        "name": meta["name"],
        "directory": target.name,
        "version": meta["version"],
        "repository": meta.get("repository", {}),
        "hash": digest(file_map(target)),
        "installed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_state(state)
    if not quiet:
        ok(f"已安装「{meta['name']}」→ {target}")
    return True


# ---------- Git 操作 ----------

def run_git(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        raise SystemExit("未找到 git，无法执行版本发布")


def git_checked(*args: str) -> subprocess.CompletedProcess:
    result = run_git(*args)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[:500]
        raise SystemExit(f"Git 命令执行失败：git {' '.join(args)}\n{detail}")
    return result


def preflight_git(repository: dict, push: bool) -> None:
    if run_git("rev-parse", "--git-dir").returncode != 0:
        if push:
            raise SystemExit("当前目录不是 Git 仓库，无法推送 GitHub；可使用 --no-push 仅本地发布")
        return
    staged = run_git("diff", "--cached", "--quiet")
    if staged.returncode == 1:
        raise SystemExit("仓库已有暂存修改，为避免混入本次发布，请先提交或取消暂存")
    if staged.returncode != 0:
        raise SystemExit("无法检查 Git 暂存区")
    if not push:
        return
    branch = repository["branch"]
    git_checked("fetch", repository["url"], branch)
    behind = run_git("merge-base", "--is-ancestor", "FETCH_HEAD", "HEAD")
    if behind.returncode != 0:
        raise SystemExit("GitHub 存在本地尚未包含的新提交；先同步仓库，再执行发布，避免覆盖线上版本")


def commit_and_push(paths: list[str], asset_id: str, version: str, note: str,
                    repository: dict, push: bool, kind: str) -> None:
    if run_git("rev-parse", "--git-dir").returncode != 0:
        warn("不是 Git 仓库，已跳过提交与推送")
        return
    git_checked("add", "-A", "--", *paths)
    message = f"发布 {kind} {asset_id} v{version}：{note}"
    git_checked("commit", "-m", message)
    ok(f"已提交：{message}")
    if push:
        branch = repository["branch"]
        result = run_git("push", repository["url"], f"HEAD:refs/heads/{branch}")
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[:500]
            raise SystemExit(
                f"GitHub 推送失败，本地 Agent 仍保持旧版本；仓库已生成新提交。\n{detail}\n"
                "解决网络、权限或冲突后，可继续推送该提交。"
            )
        ok(f"已推送 GitHub {repository['url']} 的 {branch} 分支")


# ---------- 查询与更新命令 ----------

def cmd_list(args, kind: str = "skill") -> None:
    data = load_manifest()
    state = load_state()
    entries = data[collection(kind)]
    say()
    say(pad("ID", 26) + pad("版本", 8) + pad("本地", 10) + "一句话用途")
    say("-" * 100)
    for item in entries:
        asset_id = entry_id(item)
        local = state["installed"].get(asset_id, {}).get("version", "—")
        say(pad(asset_id, 26) + pad("v" + item["version"], 8) + pad(local, 10) + item.get("summary", ""))
    say()
    say(f"共 {len(entries)} 个 {kind} · 仓库 {asset_root(kind)}")


def cmd_status(args, kind: str = "skill") -> None:
    data = load_manifest()
    state = load_state()
    rows = []
    for item in data[collection(kind)]:
        asset_id = entry_id(item)
        target = find_local(asset_id, kind, state)
        record = state["installed"].get(asset_id)
        if not target:
            rows.append((asset_id, item["version"], "—", "未安装"))
            continue
        local_meta = read_asset_meta(target, kind)
        local_v = local_meta.get("version", "?")
        local_hash = digest(file_map(target))
        repo_hash = digest(file_map(repo_asset(asset_id, kind)))
        if not record:
            status = "本地有目录，无安装记录"
        elif local_hash != record.get("hash"):
            status = "本地有改动"
        elif parse_version(item["version"]) > parse_version(local_v):
            status = "可更新"
        elif local_hash == repo_hash:
            status = "已是最新"
        else:
            status = "内容不一致"
        rows.append((asset_id, item["version"], local_v, status))
    say()
    say(pad("ID", 26) + pad("仓库", 9) + pad("本地", 9) + "状态")
    say("-" * 80)
    for asset_id, remote_v, local_v, status in rows:
        say(pad(asset_id, 26) + pad("v" + remote_v, 9) + pad("v" + local_v, 9) + status)
    say()


def cmd_install(args, kind: str = "skill") -> None:
    if not do_install(args.name, force=args.force, kind=kind):
        sys.exit(1)


def cmd_update(args, kind: str = "skill") -> None:
    data = load_manifest()
    state = load_state()
    targets = [entry_id(s) for s in data[collection(kind)]] if args.all else [args.name]
    changed = skipped = 0
    for asset_id in targets:
        if not asset_id:
            continue
        local = find_local(asset_id, kind, state)
        if not local:
            say(f"  [跳过]「{asset_id}」本地未安装")
            continue
        local_v = read_asset_meta(local, kind)["version"]
        repo_meta = read_asset_meta(repo_asset(asset_id, kind), kind)
        if parse_version(repo_meta["version"]) <= parse_version(local_v):
            say(f"  [最新]「{asset_id}」v{local_v}")
            continue
        say(f"  [更新]「{asset_id}」v{local_v} → v{repo_meta['version']}")
        if do_install(asset_id, force=args.force, quiet=True, kind=kind):
            changed += 1
        else:
            skipped += 1
    say(f"更新完成：{changed}；跳过：{skipped}")


def cmd_diff(args, kind: str = "skill") -> None:
    asset_id = args.name
    src = repo_asset(asset_id, kind)
    target = find_local(asset_id, kind)
    if not target:
        raise SystemExit(f"本地未安装「{asset_id}」，无需对比")
    entry = entry_filename(kind)
    repo_lines = (src / entry).read_text(encoding="utf-8").splitlines()
    local_lines = (target / entry).read_text(encoding="utf-8").splitlines()
    diff = list(unified_diff(
        local_lines, repo_lines, fromfile=f"本地/{target.name}/{entry}",
        tofile=f"仓库/{src.name}/{entry}", lineterm=""
    ))
    if not diff:
        say(f"「{asset_id}」的 {entry} 与仓库完全一致")
        return
    for line in diff[:400]:
        say(line)
    if len(diff) > 400:
        say(f"... 还有 {len(diff) - 400} 行差异未显示")


# ---------- 发布 ----------

def append_changelog(asset_id: str, old_v: str, new_v: str, note: str, kind: str) -> None:
    path = REPO / "CHANGELOG.md"
    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"- **{today}** [{kind}] `{asset_id}` {old_v} → {new_v}（整数递增）：{note}"
    if not path.exists():
        path.write_text("# 变更记录\n\n按时间倒序，最新在最上面。\n\n", encoding="utf-8")
    lines = path.read_text(encoding="utf-8").splitlines()
    insert_at = len(lines)
    for index, line in enumerate(lines):
        if index > 1 and line.startswith("- **"):
            insert_at = index
            break
    lines.insert(insert_at, entry)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def update_frontmatter(path: Path, new_name: str) -> None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---", text, re.S)
    if not match:
        return
    front = match.group(1)
    updated, count = re.subn(r"(?m)^name:\s*.*$", f"name: {new_name}", front, count=1)
    if count:
        path.write_text(text[:match.start(1)] + updated + text[match.end(1):], encoding="utf-8", newline="\n")


def update_ui_metadata(path: Path, new_name: str, old_names: set[str]) -> None:
    ui = path / "agents" / "openai.yaml"
    if not ui.exists():
        return
    lines = []
    for line in ui.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\s*display_name:", line):
            indent = line[:len(line) - len(line.lstrip())]
            line = f'{indent}display_name: {json.dumps(new_name, ensure_ascii=False)}'
        elif re.match(r"^\s*default_prompt:", line):
            for old in sorted(old_names, key=len, reverse=True):
                if old:
                    line = line.replace(f"${old}", f"${new_name}")
        lines.append(line)
    ui.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def prepare_asset(local: Path, staging: Path, asset_id: str, new_version: str,
                  kind: str, repository: dict, existing: dict | None) -> dict:
    copy_tree(local, staging)
    local_meta = read_asset_meta(staging, kind) if (staging / meta_filename(kind)).exists() else {}
    meta = dict(existing or {})
    meta.update(local_meta)
    new_name = asset_name(asset_id, new_version)
    old_names = {asset_id, local_meta.get("name", ""), (existing or {}).get("name", "")}
    meta.update({
        "id": asset_id,
        "name": new_name,
        "version": new_version,
        "entry": entry_filename(kind),
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "repository": repository,
    })
    if kind == "skill":
        meta.setdefault("slug", asset_id)
        meta.setdefault("origin", "self")
    meta.setdefault("summary", "")
    write_asset_meta(staging, meta, kind)
    entry = staging / entry_filename(kind)
    if not entry.exists():
        raise SystemExit(f"本地资产缺少 {entry_filename(kind)}：{local}")
    update_frontmatter(entry, new_name)
    if kind == "skill":
        update_ui_metadata(staging, new_name, old_names)
    return meta


def update_documentation(asset_id: str, old_package: str, new_package: str, new_version: str) -> None:
    for filename in DOC_FILES:
        path = REPO / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if old_package:
            text = text.replace(old_package, new_package)
        pattern = rf"(?m)^(\|\s*{re.escape(asset_id)}\s*\|)\s*[^|\n]+?\s*(\|)"
        text = re.sub(pattern, rf"\1 {new_version} \2", text)
        path.write_text(text, encoding="utf-8", newline="\n")


def cmd_publish(args, kind: str = "skill") -> None:
    asset_id = args.name
    validate_id(asset_id)
    note = args.note.strip()
    if not note:
        raise SystemExit("发布必须填写非空 --note，说明变更内容与原因")
    if args.bump != "next":
        warn("--bump 仅兼容旧命令；统一按 N.0 → (N+1).0 升版")

    data = load_manifest()
    state = load_state()
    local = find_local(asset_id, kind, state)
    if not local:
        raise SystemExit(f"本地没有安装 {kind}「{asset_id}」，无从发布")
    local_meta = read_asset_meta(local, kind)
    existing = manifest_entry(asset_id, kind, data)
    old_dst = repo_asset(asset_id, kind) if existing else None

    if existing:
        old_version = existing["version"]
        if local_meta.get("version") != old_version:
            raise SystemExit(
                f"本地版本 {local_meta.get('version')} 与仓库版本 {old_version} 不一致；"
                "请先 update 或 diff，避免覆盖其他版本"
            )
        new_version = bump_version(old_version, args.bump)
    else:
        old_version = "新增"
        new_version = "1.0"

    new_package = asset_name(asset_id, new_version)
    repository = repository_for(local_meta, data, kind, new_package)
    dst = asset_root(kind) / new_package
    new_target = TARGET / new_package
    if dst.exists() and dst != old_dst:
        raise SystemExit(f"目标仓库目录已存在：{dst}")
    if new_target.exists() and new_target != local:
        raise SystemExit(f"目标本地目录已存在：{new_target}")
    preflight_git(repository, args.push)

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{kind}ctl-publish-", dir=TARGET.parent) as temp:
        staging = Path(temp) / new_package
        meta = prepare_asset(local, staging, asset_id, new_version, kind, repository, existing)
        copy_tree(staging, dst)
        if old_dst and old_dst != dst:
            shutil.rmtree(old_dst)

        indexed = dict(meta)
        indexed["directory"] = dst.name
        data[collection(kind)] = [s for s in data[collection(kind)] if entry_id(s) != asset_id] + [indexed]
        save_manifest(data)
        old_package = (existing or {}).get("directory", "")
        update_documentation(asset_id, old_package, new_package, new_version)
        append_changelog(asset_id, old_version, new_version, note, kind)

        paths = [f"{collection(kind)}/{dst.name}", "manifest.json", "CHANGELOG.md", *DOC_FILES]
        if old_dst:
            paths.append(f"{collection(kind)}/{old_dst.name}")
        commit_and_push(paths, asset_id, new_version, note, repository, args.push, kind)

        try:
            shutil.copytree(staging, new_target)
            if local != new_target and local.exists():
                shutil.rmtree(local)
            state["installed"][asset_id] = {
                "id": asset_id,
                "name": new_package,
                "directory": new_target.name,
                "version": new_version,
                "repository": repository,
                "hash": digest(file_map(new_target)),
                "installed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            save_state(state)
        except Exception as error:
            raise SystemExit(f"仓库发布已执行，但本地安装切换失败：{error}；请检查 {new_target}")

    ok(f"本地 {kind} 已升级：{local.name} → {new_target.name}")
    ok(f"仓库 {kind} 已升级：{collection(kind)}/{new_package}")
    if args.push:
        ok(f"本地与 GitHub 均已同步到 {new_version}；备注：{note}")
    else:
        warn(f"本地与本地仓库已升级到 {new_version}；--no-push 未更新 GitHub")


# ---------- 校验 ----------

def cmd_verify(args, kind: str = "skill") -> None:
    data = load_manifest()
    problems = 0
    expected_dirs = set()
    root = asset_root(kind)
    for item in data[collection(kind)]:
        asset_id = entry_id(item)
        version = item.get("version", "")
        try:
            expected_name = asset_name(asset_id, version)
        except SystemExit:
            fail(f"「{asset_id}」ID 或版本无效：{version}")
            problems += 1
            continue
        expected_dirs.add(expected_name)
        if item.get("name") != expected_name or item.get("directory") != expected_name:
            fail(f"「{asset_id}」name/directory 必须为 {expected_name}")
            problems += 1
        repo_info = item.get("repository") or {}
        if not repo_info.get("url") or repo_info.get("path") != f"{collection(kind)}/{expected_name}":
            fail(f"「{asset_id}」GitHub repository 元数据不完整或路径失效")
            problems += 1
        path = root / expected_name
        if not path.is_dir():
            fail(f"目录不存在：{path}")
            problems += 1
            continue
        entry = path / entry_filename(kind)
        if not entry.exists():
            fail(f"「{asset_id}」缺少 {entry_filename(kind)}")
            problems += 1
        try:
            meta = read_asset_meta(path, kind)
        except SystemExit as error:
            fail(str(error))
            problems += 1
            continue
        indexed_meta = {k: v for k, v in item.items() if k != "directory"}
        if meta != indexed_meta:
            fail(f"「{asset_id}」{meta_filename(kind)} 与 manifest 不一致")
            problems += 1
        if entry.exists():
            text = entry.read_text(encoding="utf-8")
            match = re.match(r"\A---\s*\n(.*?)\n---", text, re.S)
            if kind == "skill" and not match:
                fail(f"「{asset_id}」SKILL.md 缺少 frontmatter")
                problems += 1
            elif match and not re.search(rf"(?m)^name:\s*{re.escape(expected_name)}\s*$", match.group(1)):
                fail(f"「{asset_id}」frontmatter name 必须为 {expected_name}")
                problems += 1
        if kind == "skill":
            ui = path / "agents" / "openai.yaml"
            if ui.exists():
                ui_text = ui.read_text(encoding="utf-8")
                if f'display_name: "{expected_name}"' not in ui_text or f"${expected_name}" not in ui_text:
                    fail(f"「{asset_id}」UI display_name/default_prompt 未使用 {expected_name}")
                    problems += 1
    if root.exists():
        for path in root.iterdir():
            if path.is_dir() and path.name not in expected_dirs:
                fail(f"目录「{path.name}」未登记或不符合 名称-N.0 规则")
                problems += 1
    say()
    say(f"{kind} 校验通过，仓库结构一致" if problems == 0 else f"{kind} 发现 {problems} 个问题")
    if problems:
        sys.exit(1)


# ---------- CLI ----------

def main(kind: str = "skill") -> None:
    init_stdout()
    default_target = Path.home() / ".workbuddy" / collection(kind)
    parser = argparse.ArgumentParser(prog=f"{kind}ctl", description=f"{kind} 版本管理与 GitHub 同步工具")
    parser.add_argument("--target", default=str(default_target), help=f"本地 {kind} 安装目录")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出仓库资产").set_defaults(func=cmd_list)
    sub.add_parser("status", help="对比本地与仓库版本").set_defaults(func=cmd_status)

    command = sub.add_parser("install", help="安装到版本化本地目录")
    command.add_argument("name")
    command.add_argument("--force", action="store_true", help="覆盖本地修改并先备份")
    command.set_defaults(func=cmd_install)

    command = sub.add_parser("update", help="更新已安装资产")
    command.add_argument("name", nargs="?", default=None)
    command.add_argument("--all", action="store_true")
    command.add_argument("--force", action="store_true")
    command.set_defaults(func=cmd_update)

    command = sub.add_parser("diff", help="对比本地与仓库正文")
    command.add_argument("name")
    command.set_defaults(func=cmd_diff)

    command = sub.add_parser("publish", help="升版、填写备注、提交并默认推送 GitHub")
    command.add_argument("name")
    command.add_argument("--bump", choices=["next", "patch", "minor", "major"], default="next")
    command.add_argument("--note", required=True, help="必填：变更内容与原因")
    command.add_argument("--no-push", dest="push", action="store_false", default=True,
                         help="仅更新本地安装与本地 Git 仓库，不推送 GitHub")
    command.set_defaults(func=cmd_publish)

    sub.add_parser("verify", help="校验名称、版本、元数据与目录").set_defaults(func=cmd_verify)

    args = parser.parse_args()
    set_target(args.target, kind)
    if args.cmd == "update" and not args.all and not args.name:
        parser.error("update 需要指定资产 ID，或使用 --all")
    args.func(args, kind)


if __name__ == "__main__":
    main("skill")
