#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skillctl — 技能库版本管理与安装工具

仓库是唯一真相源，~/.workbuddy/skills 只是部署产物。
安装目录和展示名统一为技能名称V版本号，更新直接替换旧安装。

用法:
    python tools/skillctl.py list
    python tools/skillctl.py status
    python tools/skillctl.py install 报告可视化 [--force]
    python tools/skillctl.py update --all [--force]
    python tools/skillctl.py diff 报告可视化
    python tools/skillctl.py publish 报告可视化 --note "改了验收清单"
    python tools/skillctl.py verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unicodedata
from datetime import datetime
from difflib import unified_diff
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
MANIFEST = REPO / "manifest.json"

TARGET = Path.home() / ".workbuddy" / "skills"
STATE_FILE = TARGET / ".skillctl.json"


def set_target(raw: str) -> None:
    global TARGET, STATE_FILE
    TARGET = Path(raw).expanduser().resolve()
    STATE_FILE = TARGET / ".skillctl.json"

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
    with TemporaryDirectory(prefix=".skillctl-state-", dir=TARGET) as temp:
        pending = Path(temp) / STATE_FILE.name
        pending.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
        pending.replace(STATE_FILE)


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


def bump_version(version: str, level: str = "next") -> str:
    """每次发布整数部分加一；兼容读取旧三段版本，不继续生成它们。"""
    if level not in {"next", "patch", "minor", "major"}:
        raise ValueError(f"不支持的升版方式：{level}")
    if not re.fullmatch(r"[1-9]\d*\.(?:0|\d+\.\d+)", str(version)):
        raise SystemExit(f"无效版本「{version}」；当前格式为 N.0，旧版可为 N.x.y")
    return f"{int(str(version).split('.')[0]) + 1}.0"


# ---------- 安装动作 ----------

def installed_paths(name: str) -> list[Path]:
    pattern = re.compile(rf"{re.escape(name)}(?:\s*[vV](\d+(?:\.\d+)+))?")
    if not TARGET.is_dir():
        return []
    matches = [(path, pattern.fullmatch(path.name)) for path in TARGET.iterdir()
               if path.is_dir() and not path.is_symlink() and not getattr(path, "is_junction", lambda: False)()]
    return [path for path, match in sorted(
        ((path, match) for path, match in matches if match),
        key=lambda pair: parse_version(pair[1][1] or "0"), reverse=True)]


def replace_display_name(root: Path, old: str, new: str, display_name: str | None = None) -> None:
    for relative, replacement in {
        "SKILL.md": lambda text: re.sub(
            rf"(?m)^name:[ \t]*(?:{re.escape(old)}|\"{re.escape(old)}\"|'{re.escape(old)}')[ \t]*$",
            lambda _: f"name: {new}", text, count=1),
        "agents/openai.yaml": lambda text: re.sub(
            rf"\${re.escape(old)}(?![\w.-])", lambda _: f"${new}",
            re.sub(r'(?m)^([ \t]*display_name:[ \t]*).+$',
                   lambda match: match[1] + json.dumps(display_name or new, ensure_ascii=False),
                   text, count=1)),
    }.items():
        path = root / relative
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            updated = replacement(text)
            if updated != text:
                path.write_text(updated, encoding="utf-8", newline="\n")


def copy_into_repo_name(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".skillctl*", "*.local.*"))


def do_install(name: str, quiet: bool = False) -> None:
    src = repo_skill(name)
    version = read_skill_meta(src)["version"]
    label = f"{name}V{version}"
    target = TARGET / label
    state = load_state()
    old_paths = installed_paths(name)
    if target.exists() and target not in old_paths:
        raise SystemExit(f"安装路径已被占用：{target}")
    TARGET.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".skillctl-", dir=TARGET) as temp:
        staging = Path(temp)
        prepared = staging / "new"
        shutil.copytree(src, prepared)
        replace_display_name(prepared, name, label)
        moved = []
        try:
            for index, path in enumerate(old_paths):
                displaced = staging / str(index)
                path.rename(displaced)
                moved.append((path, displaced))
                state["installed"].pop(path.name, None)
            prepared.rename(target)
            state["installed"][name] = {
                "version": version,
                "directory": label,
                "hash": digest(file_map(target)),
                "installed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            save_state(state)
        except BaseException:
            if not prepared.exists():
                target.rename(prepared)
            for path, displaced in reversed(moved):
                displaced.rename(path)
            raise
    if not quiet:
        ok(f"已安装「{label}」→ {target}")


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
        paths = installed_paths(name)
        record = state["installed"].get(name)
        if not paths:
            rows.append((name, s["version"], "—", "未安装", ""))
            continue
        local_v = record["version"] if record else "?"
        target = paths[0]
        local_hash = digest(file_map(target))
        if not record:
            status = "本地有目录，无安装记录"
        elif local_hash != record["hash"]:
            status = "本地有改动"
        elif parse_version(s["version"]) > parse_version(record["version"]):
            status = "可更新"
        elif str(local_v) == s["version"] and len(paths) == 1 and target.name == f'{name}V{s["version"]}':
            status = "已是最新"
        else:
            status = "可更新"
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
    do_install(args.name)


def cmd_update(args) -> None:
    targets = [s["name"] for s in load_manifest()["skills"]] if args.all else [args.name]
    for name in targets:
        src = repo_skill(name)
        paths = installed_paths(name)
        if not paths:
            say(f"  [跳过] 「{name}」本地未安装")
            continue
        version = read_skill_meta(src)["version"]
        if len(paths) == 1 and paths[0].name == f"{name}V{version}" and not args.force:
            say(f"  [最新] 「{name}V{version}」")
            continue
        do_install(name)


def cmd_diff(args) -> None:
    name = args.name
    src = repo_skill(name)
    paths = installed_paths(name)
    if not paths:
        raise SystemExit(f"本地未安装「{name}」，无需对比")
    target = paths[0]
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
    note = args.note.strip()
    if not note:
        raise SystemExit("发布必须填写非空 --note，说明变更内容与原因")
    if args.bump != "next":
        warn("--bump patch/minor/major 仅兼容旧命令；统一按 N.0 → (N+1).0 升版")
    paths = installed_paths(name)
    if not paths:
        raise SystemExit(f"本地没有安装「{name}」，无从发布")
    dst = SKILLS_DIR / name
    is_new = not dst.exists()

    if is_new:
        new_version = "1.0"
        old_version = "新增"
    else:
        old_version = read_skill_meta(dst).get("version", "")
        new_version = bump_version(old_version, args.bump)

    target = paths[0]
    interface = dst / "agents/openai.yaml"
    display_name = None
    if interface.is_file():
        match = re.search(r'(?m)^\s*display_name:\s*"([^"]+)"', interface.read_text(encoding="utf-8"))
        if match:
            display_name = match[1]
    copy_into_repo_name(target, dst)
    if target.name != name:
        replace_display_name(dst, target.name, name, display_name)

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
    append_changelog(name, old_version, new_version, note, "整数递增")
    git_commit(name, new_version, note)


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
    p.add_argument("--force", action="store_true", help="兼容旧命令，安装始终替换旧版")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("update", help="更新已安装的技能")
    p.add_argument("name", nargs="?", default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true", help="重新安装当前版本")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("diff", help="对比本地与仓库内容")
    p.add_argument("name")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("publish", help="把本地改动回写仓库并升版本")
    p.add_argument("name")
    p.add_argument("--bump", choices=["next", "patch", "minor", "major"], default="next",
                   help="统一整数递增；patch/minor/major 仅作为旧命令兼容别名")
    p.add_argument("--note", required=True, help="必填：本次修改内容与原因")
    p.set_defaults(func=cmd_publish)

    sub.add_parser("verify", help="校验仓库结构一致性").set_defaults(func=cmd_verify)

    args = parser.parse_args()
    set_target(args.target)
    if args.cmd == "update" and not args.all and not args.name:
        parser.error("update 需要指定技能名，或使用 --all")
    args.func(args)


if __name__ == "__main__":
    main()
