#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skillctl — 技能库版本管理与安装工具

仓库是唯一真相源，~/.workbuddy/skills 只是部署产物。
安装器只搬不改：所有内容规范化都在入库时完成。

用法:
    python tools/skillctl.py list
    python tools/skillctl.py status
    python tools/skillctl.py install 报告可视化 [--force]
    python tools/skillctl.py update --all [--force]
    python tools/skillctl.py diff 报告可视化
    python tools/skillctl.py publish 报告可视化 --bump patch --note "改了验收清单"
    python tools/skillctl.py verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime
from difflib import unified_diff
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
MANIFEST = REPO / "manifest.json"

TARGET = Path.home() / ".workbuddy" / "skills"
STATE_FILE = TARGET / ".skillctl.json"
BACKUP_DIR = TARGET.parent / ".skillctl_backup"


def set_target(raw: str) -> None:
    global TARGET, STATE_FILE, BACKUP_DIR
    TARGET = Path(raw).expanduser().resolve()
    STATE_FILE = TARGET / ".skillctl.json"
    BACKUP_DIR = TARGET.parent / ".skillctl_backup"

EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".skillctl_backup"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".DS_Store"}


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


# ---------- 仓库读写 ----------

def load_manifest() -> dict:
    if not MANIFEST.exists():
        raise SystemExit("找不到 manifest.json，仓库尚未初始化")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def save_manifest(data: dict) -> None:
    data["updated"] = datetime.now().strftime("%Y-%m-%d")
    data["skills"] = sorted(data["skills"], key=lambda x: x["name"])
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")


def repo_skill(name: str) -> Path:
    path = SKILLS_DIR / name
    if not path.is_dir():
        avail = "、".join(s["name"] for s in load_manifest()["skills"])
        raise SystemExit(f"仓库里没有技能「{name}」。现有：{avail}")
    return path


def read_skill_meta(path: Path) -> dict:
    meta_file = path / "skill.json"
    if not meta_file.exists():
        raise SystemExit(f"{path.name} 缺少 skill.json，无法读取版本")
    return json.loads(meta_file.read_text(encoding="utf-8"))


def write_skill_meta(path: Path, meta: dict) -> None:
    (path / "skill.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")


# ---------- 状态与哈希 ----------

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"schema": 1, "installed": {}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")


def iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if p.suffix in EXCLUDE_SUFFIX or p.name in EXCLUDE_SUFFIX or ".local." in p.name:
            continue
        yield p, rel


def file_map(root: Path) -> dict:
    result = {}
    for p, rel in iter_files(root):
        result[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def digest(files: dict) -> str:
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode("utf-8"))
        h.update(files[name].encode("utf-8"))
    return h.hexdigest()[:16]


def parse_version(v: str) -> tuple:
    parts = []
    for chunk in str(v).split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def bump_version(version: str, level: str) -> str:
    major, minor, patch = parse_version(version)
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


# ---------- 安装动作 ----------

def backup_existing(path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"{path.name}-{stamp}"
    shutil.copytree(path, dest)
    return dest


def local_changed(name: str, state: dict) -> tuple:
    """返回 (是否被本地改动, 说明)。没有安装记录时视为外部安装。"""
    target = TARGET / name
    if not target.is_dir():
        return False, "未安装"
    record = state["installed"].get(name)
    if not record:
        return True, "本地已存在但无安装记录"
    now = digest(file_map(target))
    if now != record.get("hash"):
        return True, "安装后被改动过"
    return False, ""


def copy_into_repo_name(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".skillctl*", "*.local.*"))


def find_duplicates(name: str, src: Path) -> list:
    """找出本地其他目录里正文完全相同的技能（改名遗留的旧副本）。"""
    def body_hash(path: Path):
        f = path / "SKILL.md"
        if not f.exists():
            return None
        text = f.read_text(encoding="utf-8", errors="replace")
        parts = text.split("---", 2)
        body = parts[2] if len(parts) == 3 else text
        return hashlib.sha256(body.strip().encode("utf-8")).hexdigest()

    want = body_hash(src)
    if not want or not TARGET.exists():
        return []
    found = []
    for d in TARGET.iterdir():
        if d.is_dir() and d.name != name and not d.name.startswith("."):
            if body_hash(d) == want:
                found.append(d.name)
    return found


def do_install(name: str, force: bool = False, quiet: bool = False) -> bool:
    src = repo_skill(name)
    meta = read_skill_meta(src)
    target = TARGET / name
    state = load_state()

    if target.exists():
        changed, reason = local_changed(name, state)
        if changed and not force:
            fail(f"「{name}」{reason}，已停止，未做任何修改")
            say(f"         先备份或确认丢弃，再加 --force 重跑")
            return False
        if changed:
            dest = backup_existing(target)
            warn(f"已备份旧版本到 {dest}")
        shutil.rmtree(target)

    TARGET.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target)

    state["installed"][name] = {
        "version": meta["version"],
        "hash": digest(file_map(target)),
        "installed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_state(state)
    if not quiet:
        ok(f"已安装「{name}」v{meta['version']} → {target}")
        dups = find_duplicates(name, src)
        if dups:
            warn(f"发现疑似重复的旧技能：{'、'.join(dups)}")
            say(f"         确认是同一份内容后，可删除：{TARGET / dups[0]}")
    return True


# ---------- 命令 ----------

def cmd_list(args) -> None:
    data = load_manifest()
    state = load_state()
    say()
    say(pad("技能名", 22) + pad("版本", 10) + pad("本地", 8) + "一句话用途")
    say("-" * 96)
    for s in data["skills"]:
        local = state["installed"].get(s["name"], {}).get("version", "—")
        say(pad(s["name"], 22) + pad("v" + s["version"], 10) + pad(local, 8) + s["summary"])
    say()
    say(f"共 {len(data['skills'])} 个技能 · 仓库 {SKILLS_DIR}")


def cmd_status(args) -> None:
    data = load_manifest()
    state = load_state()
    rows = []
    for s in data["skills"]:
        name = s["name"]
        target = TARGET / name
        record = state["installed"].get(name)
        if not target.exists():
            rows.append((name, s["version"], "—", "未安装", ""))
            continue
        local_v = record["version"] if record else "?"
        local_hash = digest(file_map(target))
        repo_hash = digest(file_map(SKILLS_DIR / name))
        if not record:
            status = "本地有目录，无安装记录"
        elif local_hash != record["hash"]:
            status = "本地有改动"
        elif parse_version(s["version"]) > parse_version(record["version"]):
            status = "可更新"
        elif local_hash == repo_hash:
            status = "已是最新"
        else:
            status = "内容不一致"
        rows.append((name, s["version"], local_v, status, ""))
    say()
    say(pad("技能名", 22) + pad("仓库", 9) + pad("本地", 9) + "状态")
    say("-" * 80)
    for name, rv, lv, st, _ in rows:
        mark = "" if st in ("已是最新",) else "  ←"
        say(pad(name, 22) + pad("v" + rv, 9) + pad(lv if lv == "—" else "v" + lv, 9) + st + mark)
    say()
    pending = [r[0] for r in rows if r[3] in ("可更新", "未安装")]
    if pending:
        say(f"待处理：{'、'.join(pending)}")
    else:
        say("本地与仓库一致，无需处理")


def cmd_install(args) -> None:
    if not do_install(args.name, force=args.force):
        sys.exit(1)


def cmd_update(args) -> None:
    data = load_manifest()
    state = load_state()
    targets = [s["name"] for s in data["skills"]] if args.all else [args.name]
    changed = skipped = 0
    for name in targets:
        if not name:
            continue
        record = state["installed"].get(name)
        if not record:
            say(f"  [跳过] 「{name}」本地未安装")
            continue
        repo_meta = read_skill_meta(SKILLS_DIR / name)
        if parse_version(repo_meta["version"]) <= parse_version(record["version"]):
            say(f"  [最新] 「{name}」v{record['version']}")
            continue
        say(f"  [更新] 「{name}」v{record['version']} → v{repo_meta['version']}")
        if do_install(name, force=args.force, quiet=True):
            changed += 1
        else:
            skipped += 1
    say()
    if changed:
        say(f"更新完成，共处理 {changed} 个技能")
    if skipped:
        say(f"有 {skipped} 个技能因本地改动被拦下，逐个确认后用 --force 重跑")
    if not changed and not skipped:
        say("没有需要更新的技能")


def cmd_diff(args) -> None:
    name = args.name
    src = repo_skill(name)
    target = TARGET / name
    if not target.exists():
        raise SystemExit(f"本地未安装「{name}」，无需对比")
    repo_lines = (src / "SKILL.md").read_text(encoding="utf-8").splitlines()
    local_lines = (target / "SKILL.md").read_text(encoding="utf-8").splitlines()
    diff = list(unified_diff(local_lines, repo_lines,
                             fromfile=f"本地/{name}/SKILL.md",
                             tofile=f"仓库/{name}/SKILL.md", lineterm=""))
    if not diff:
        say(f"「{name}」的 SKILL.md 与仓库完全一致")
        return
    say()
    for line in diff[:400]:
        say(line)
    if len(diff) > 400:
        say(f"... 还有 {len(diff) - 400} 行差异未显示")


def append_changelog(name: str, old_v: str, new_v: str, note: str, level: str) -> None:
    path = REPO / "CHANGELOG.md"
    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"- **{today}** `{name}` {old_v} → {new_v}（{level}）" + (f"：{note}" if note else "")
    if not path.exists():
        path.write_text("# 变更记录\n\n按时间倒序，最新在最上面。\n\n", encoding="utf-8")
    lines = path.read_text(encoding="utf-8").splitlines()
    insert_at = len(lines)
    for i, line in enumerate(lines):
        if i > 3 and line.startswith("- **"):
            insert_at = i
            break
    lines.insert(insert_at, entry)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def cmd_publish(args) -> None:
    name = args.name
    target = TARGET / name
    if not target.is_dir():
        raise SystemExit(f"本地没有安装「{name}」，无从发布")
    dst = SKILLS_DIR / name
    is_new = not dst.exists()

    if is_new:
        local_meta = json.loads((target / "skill.json").read_text(encoding="utf-8")) \
            if (target / "skill.json").exists() else {}
        new_version = local_meta.get("version", "1.0.0")
        old_version = "新增"
    else:
        old_version = read_skill_meta(dst).get("version", "0.0.0")
        new_version = bump_version(old_version, args.bump)

    copy_into_repo_name(target, dst)

    meta = json.loads((dst / "skill.json").read_text(encoding="utf-8")) \
        if (dst / "skill.json").exists() else {}
    meta.update({
        "name": name,
        "version": new_version,
        "entry": "SKILL.md",
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "origin": meta.get("origin", "self"),
    })
    meta.setdefault("slug", name)
    meta.setdefault("summary", "")
    write_skill_meta(dst, meta)

    data = load_manifest()
    data["skills"] = [s for s in data["skills"] if s["name"] != name] + [meta]
    save_manifest(data)

    if is_new:
        ok(f"已收录新技能「{name}」v{new_version}")
    else:
        ok(f"已回写「{name}」v{old_version} → v{new_version}")
    append_changelog(name, old_version, new_version, args.note, args.bump)
    git_commit(name, new_version, args.note)


def git_commit(name: str, version: str, note: str) -> None:
    def run(*a):
        return subprocess.run(["git", "-C", str(REPO), *a],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run("rev-parse", "--git-dir").returncode != 0:
        warn("不是 git 仓库，跳过提交")
        return
    run("add", "-A")
    msg = f"发布 {name} v{version}" + (f"：{note}" if note else "")
    r = run("commit", "-m", msg)
    if r.returncode == 0:
        ok(f"已提交：{msg}")
    else:
        warn(f"提交未成功：{(r.stdout or r.stderr).strip()[:200]}")


def cmd_verify(args) -> None:
    data = load_manifest()
    problems = 0
    names = [s["name"] for s in data["skills"]]
    for s in data["skills"]:
        d = SKILLS_DIR / s["name"]
        if not d.is_dir():
            fail(f"manifest 记录了「{s['name']}」但目录不存在")
            problems += 1
            continue
        skill_md = d / "SKILL.md"
        meta_file = d / "skill.json"
        if not skill_md.exists():
            fail(f"「{s['name']}」缺少 SKILL.md")
            problems += 1
        if not meta_file.exists():
            fail(f"「{s['name']}」缺少 skill.json")
            problems += 1
            continue
        meta = read_skill_meta(d)
        if meta.get("version") != s.get("version"):
            fail(f"「{s['name']}」版本不一致：skill.json={meta.get('version')} manifest={s.get('version')}")
            problems += 1
        text = skill_md.read_text(encoding="utf-8")
        if not text.startswith("---"):
            fail(f"「{s['name']}」SKILL.md 缺少 frontmatter")
            problems += 1
        elif f"name: {s['name']}" not in text.split("---")[1]:
            fail(f"「{s['name']}」frontmatter 的 name 与目录名不一致")
            problems += 1
    for d in SKILLS_DIR.iterdir():
        if d.is_dir() and d.name not in names:
            warn(f"目录「{d.name}」未登记在 manifest.json")
    say()
    say("校验通过，仓库结构一致" if problems == 0 else f"发现 {problems} 个问题")
    if problems:
        sys.exit(1)


def main() -> None:
    init_stdout()
    parser = argparse.ArgumentParser(prog="skillctl", description="技能库版本管理与安装工具")
    parser.add_argument("--target", default=str(TARGET),
                        help="技能安装目录，默认 ~/.workbuddy/skills")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出仓库里的技能").set_defaults(func=cmd_list)
    sub.add_parser("status", help="对比本地安装与仓库版本").set_defaults(func=cmd_status)

    p = sub.add_parser("install", help="安装技能到本地")
    p.add_argument("name")
    p.add_argument("--force", action="store_true", help="本地有改动时强制覆盖（会先备份）")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("update", help="更新已安装的技能")
    p.add_argument("name", nargs="?", default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("diff", help="对比本地与仓库内容")
    p.add_argument("name")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("publish", help="把本地改动回写仓库并升版本")
    p.add_argument("name")
    p.add_argument("--bump", choices=["patch", "minor", "major"], default="patch")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_publish)

    sub.add_parser("verify", help="校验仓库结构一致性").set_defaults(func=cmd_verify)

    args = parser.parse_args()
    set_target(args.target)
    if args.cmd == "update" and not args.all and not args.name:
        parser.error("update 需要指定技能名，或使用 --all")
    args.func(args)


if __name__ == "__main__":
    main()
