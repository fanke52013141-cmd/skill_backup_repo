#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skill 只读静态验收：结构、触发层、执行层、平台元数据与安全红线。

用法:
  python scripts/validate_skill.py <skill目录 或 SKILL.md 路径> [--strict] [--json]

退出码:
  0 = 无 E 级错误；strict 模式同时要求无 W 级告警
  1 = 校验未通过
  2 = 输入不存在或无法读取

仅读取本地文件，不联网，也不执行被检技能中的代码。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SECTION_RE = re.compile(r"^#{2,3}\s*(.+?)\s*$", re.M)
REQUIRED_SECTION_GROUPS = {
    "目标": ("目标",),
    "适用判断": ("适用判断",),
    "非目标": ("非目标",),
    "执行流程": ("执行流程", "核心构建工作流", "全局编排流程"),
    "示例": ("示例",),
    "验证": ("验证",),
}
EXCLUDE_WORDS = ("不处理", "不适用", "排除", "不含", "不负责", "不做", "Do NOT", "not for")
TRIGGER_WORDS = ("当用户", "时触发", "适用于", "用于", "当用户提出")
SAFE_WORDS = ("确认", "备份", "回滚", "dry-run", "dry run", "--dry", "回收站", "trash", "二次确认")
TEXT_SUFFIXES = (".md", ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml")

CRED_RE = (
    re.compile(r"(api[_-]?key|token|secret|password|passwd)\s*[:=]\s*[\"'][^\"']{8,}[\"']", re.I),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
)
DANGER_RE = (
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\bdel\s+/s\s+/q\b", re.I),
    re.compile(r"\bdrop\s+table\b", re.I),
    re.compile(r"\btruncate\b", re.I),
    re.compile(r"git\s+reset\s+--hard"),
    re.compile(r"git\s+checkout\s+--"),
    re.compile(r"shutil\.rmtree|os\.system\("),
)
PLACEHOLDER = re.compile(r"(xxx+|<[^>]+>|\{\{?[^}]+\}?\}|\byour[_-]?\w+|placeholder|示例|example)", re.I)
TTY_RE = (
    re.compile(r"^\s*(?:[A-Za-z_]\w*\s*=\s*)?input\s*\(", re.M),
    re.compile(r"\bread\s+-p\b"),
)


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []
        self.stats: dict[str, object] = {}

    def add(self, level: str, code: str, msg: str) -> None:
        self.items.append({"level": level, "code": code, "msg": msg})

    @property
    def errors(self) -> list[dict]:
        return [item for item in self.items if item["level"] == "E"]

    @property
    def warns(self) -> list[dict]:
        return [item for item in self.items if item["level"] == "W"]


def parse_frontmatter(text: str) -> tuple[dict, str, str, str | None]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "", "SKILL.md 顶部缺少起始 YAML Frontmatter 分隔符 '---'"
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            end = index
            break
    if end is None:
        return {}, text, "", "SKILL.md 缺少闭合 YAML Frontmatter 分隔符 '---'"

    raw_fm = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:])
    data: dict[str, str] = {}
    key = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")) and key:
            data[key] = (data.get(key, "") + " " + raw.strip()).strip()
            continue
        match = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", raw)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            data[key] = "" if value in (">", "|", ">-", "|-") else value.strip("\"'")
        else:
            key = None
    return data, body, raw_fm, None


def count_examples(body: str) -> int:
    return len(re.findall(r"^#{2,3}\s*示例\s*\d*", body, re.M))


def walk_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            if not any(part in {".git", "__pycache__", "node_modules"} for part in path.parts):
                yield path


def check_safety(report: Report, skill_dir: Path) -> None:
    for path in walk_text_files(skill_dir):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            report.add("W", "W030", f"无法读取 {path.name}: {exc}")
            continue
        short = path.relative_to(skill_dir).as_posix()
        for pattern in CRED_RE:
            for match in pattern.finditer(content):
                if PLACEHOLDER.search(match.group(0)):
                    continue
                report.add("E", "E020", f"{short}: 疑似硬编码凭据 -> {match.group(0)[:40]}")
                break
        for pattern in DANGER_RE:
            for match in pattern.finditer(content):
                context = content[max(0, match.start() - 220): match.end() + 220]
                if any(word in context for word in SAFE_WORDS):
                    continue
                report.add("E", "E021", f"{short}: 危险操作缺少确认/备份/dry-run/回滚说明 -> {match.group(0)[:40]}")
                break
        if re.search(r"(eval|exec)\s*\(\s*[^)]*(response|resp|result|content|data|output)", content, re.I):
            report.add("E", "E022", f"{short}: 疑似把外部返回内容交给 eval/exec 执行")
        if path.suffix.lower() in (".py", ".sh"):
            for pattern in TTY_RE:
                if pattern.search(content):
                    report.add("E", "E023", f"{short}: 脚本包含阻塞式交互输入，智能体环境可能永久等待")
                    break


def check(path: Path) -> tuple[Report, int]:
    report = Report()
    if not path.exists():
        report.add("E", "E001", f"目标路径不存在: {path}")
        return report, 2

    if path.is_dir():
        skill_dir = path.resolve()
        entries = {entry.name: entry for entry in skill_dir.iterdir()}
        if any(name.lower() == "readme.md" for name in entries):
            report.add("E", "E002", "技能目录内不得放置 README.md；请移至仓库外层或 references/")
        skill_md = entries.get("SKILL.md")
        if skill_md is None:
            wrong_case = [name for name in entries if name.lower() == "skill.md"]
            suffix = f"；发现大小写错误: {wrong_case[0]}" if wrong_case else ""
            report.add("E", "E003", f"技能根目录缺少精确大写的 SKILL.md{suffix}")
            return report, 2
    else:
        skill_md = path.resolve()
        skill_dir = skill_md.parent
        if skill_md.name != "SKILL.md":
            report.add("E", "E003", "主文件必须精确命名为大写 SKILL.md")

    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        report.add("E", "E001", f"读取 SKILL.md 失败: {exc}")
        return report, 2

    fm, body, raw_fm, fm_error = parse_frontmatter(text)
    if fm_error:
        report.add("E", "E004", fm_error)
        return report, 1

    name = fm.get("name", "").strip()
    description = fm.get("description", "").strip()
    if not name:
        report.add("E", "E005", "Frontmatter 缺少 name")
    else:
        if len(name) > 64:
            report.add("E", "E005", f"name 长度 {len(name)} 超过 64 字符")
        if name.startswith("-") or name.endswith("-") or "--" in name:
            report.add("E", "E005", "name 不能以连字符开头/结尾或包含连续连字符")
        if " " in name or "_" in name:
            report.add("E", "E005", "name 不得包含空格或下划线")
        if any(char.isupper() for char in name if char.isascii()):
            report.add("E", "E005", "name 中的 ASCII 英文字母必须小写")
        if "claude" in name.lower() or "anthropic" in name.lower():
            report.add("E", "E005", "name 不得包含保留词 claude 或 anthropic")
        if "<" in name or ">" in name:
            report.add("E", "E005", "name 不得包含 XML 尖括号")
        if name != skill_dir.name:
            report.add("E", "E006", f"name({name}) 与目录名({skill_dir.name}) 不一致")

    if not description:
        report.add("E", "E007", "Frontmatter 缺少 description")
    else:
        length = len(description)
        report.stats["description_length"] = length
        if length > 1024:
            report.add("E", "E007", f"description 长度 {length} 超过 1024 字符")
        elif length < 40:
            report.add("W", "W007", f"description 过短({length}字)，建议 60~300 字")
        elif length > 400:
            report.add("W", "W007", f"description 过长({length}字)，建议 60~300 字")
        if "<" in description or ">" in description:
            report.add("E", "E007", "description 不得包含 XML 尖括号")
        if not any(word in description for word in EXCLUDE_WORDS):
            report.add("W", "W008", "description 缺少明确排除范围")
        if not any(word in description for word in TRIGGER_WORDS):
            report.add("W", "W009", "description 缺少触发意图")

    compatibility = fm.get("compatibility", "")
    if len(compatibility) > 500:
        report.add("E", "E008", "compatibility 字段不得超过 500 字符")
    if fm.get("agent_created", "").lower() != "true":
        report.add("W", "W010", "智能体创建的技能建议在 Frontmatter 标记 agent_created: true")

    sections = [section.strip() for section in SECTION_RE.findall(body)]
    for label, aliases in REQUIRED_SECTION_GROUPS.items():
        if not any(alias in section for section in sections for alias in aliases):
            report.add("E", "E010", f"缺少必需章节: {label}")

    example_count = count_examples(body)
    report.stats["示例数"] = example_count
    if example_count < 3:
        report.add("W", "W011", f"示例数量 {example_count}，建议至少覆盖典型/边界/失败三类")

    body_lines = body.splitlines()
    report.stats["正文行数"] = len(body_lines)
    if not body.strip():
        report.add("E", "E012", "SKILL.md 正文为空")
    if len(body_lines) > 500:
        report.add("E", "E012", f"正文 {len(body_lines)} 行超过 500 行上限")
    if "—" in text or "–" in text:
        report.add("W", "W013", "包含长破折号；这是风格建议，不应作为跨平台语义错误")

    steps = re.findall(r"^###\s*Step\s*\d+", body, re.M | re.I)
    report.stats["Step 数"] = len(steps)
    if len(steps) >= 3 and "检查点" not in body:
        report.add("W", "W014", "有 3 个以上 Step 但未出现检查点")
    long_para = max((len(p) for p in re.split(r"\n\s*\n", body) if not p.lstrip().startswith(("|", "```", "#"))), default=0)
    if long_para > 700:
        report.add("W", "W015", f"存在 {long_para} 字连续段落，建议外置背景资料")

    for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", body):
        if link.startswith(("http://", "https://", "#")):
            continue
        clean_link = link.split("#")[0].strip()
        if clean_link and not (skill_dir / clean_link).resolve().exists():
            report.add("E", "E016", f"SKILL.md 引用了不存在的相对路径: {clean_link}")

    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref_file in refs_dir.rglob("*.md"):
            ref_text = ref_file.read_text(encoding="utf-8", errors="ignore")
            if len(ref_text.splitlines()) > 100 and "## 目录" not in ref_text and "## Contents" not in ref_text:
                report.add("W", "W017", f"references/{ref_file.name} 超过 100 行，建议顶部添加目录")

    for directory in ("scripts", "references", "evaluation", "assets"):
        declared = directory in body
        exists = (skill_dir / directory).is_dir()
        if declared and not exists:
            report.add("W", "W018", f"正文引用了 {directory}/ 但目录不存在")
        if exists and not declared:
            report.add("W", "W018", f"存在 {directory}/ 但正文未提及，可能不会被加载")

    meta_path = skill_dir / "skill.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("name") != name:
                report.add("E", "E019", "skill.json 的 name 与 SKILL.md 不一致")
            if not meta.get("version"):
                report.add("E", "E019", "WorkBuddy skill.json 缺少 version")
            else:
                report.stats["version"] = meta["version"]
            if re.search(r"^\s*version\s*:", raw_fm, re.M):
                report.add("W", "W019", "检测到 Frontmatter 版本号；WorkBuddy 仓库应仅以 skill.json 为版本真源")
        except (OSError, json.JSONDecodeError) as exc:
            report.add("E", "E019", f"skill.json 无法解析: {exc}")

    evaluation_dir = skill_dir / "evaluation"
    if evaluation_dir.is_dir():
        for case_file in evaluation_dir.glob("*.json"):
            try:
                json.loads(case_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                report.add("E", "E024", f"evaluation/{case_file.name} 不是有效 JSON: {exc}")

    check_safety(report, skill_dir)
    report.stats["章节"] = len(sections)
    return report, 0


def main() -> int:
    parser = argparse.ArgumentParser(description="只读校验 Skill 的结构、触发层、执行层、平台元数据与安全红线")
    parser.add_argument("skill_path", help="待校验的技能目录或 SKILL.md 路径")
    parser.add_argument("--strict", action="store_true", help="W 级告警也视为校验失败")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = parser.parse_args()

    report, fatal = check(Path(args.skill_path).expanduser())
    valid = fatal == 0 and not report.errors and not (args.strict and report.warns)
    if args.json:
        print(json.dumps({"valid": valid, "items": report.items, "stats": report.stats}, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("Skill 静态验收报告")
        print("=" * 60)
        for key, value in report.stats.items():
            print(f"  {key}: {value}")
        print("-" * 60)
        if not report.items:
            print("  PASS  全部检查通过")
        for item in report.items:
            print(f"  [{item['level']}] {item['code']}  {item['msg']}")
        print("-" * 60)
        print(f"  E(必须修) {len(report.errors)}  |  W(建议修) {len(report.warns)}")
        print(f"  RESULT {'PASS' if valid else 'FAIL'}")

    if fatal == 2:
        return 2
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
