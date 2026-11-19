#!/usr/bin/env python3
"""Lightweight static checks for a generated standalone HTML using this skill."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

REQUIRED_TOKENS = [
    "--ink-navy", "--amber", "--paper", "--paper-dark", "--ink-soft", "--border"
]


def check(path: Path) -> list[tuple[bool, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    low = text.lower()
    results: list[tuple[bool, str]] = []

    results.append(("<html" in low and "</html>" in low, "完整 HTML 文档"))
    results.append((any(x in low for x in ["class=\"sidebar", "class='sidebar", "<aside"]), "存在左侧导航/aside"))
    results.append((all(tok in text for tok in REQUIRED_TOKENS), "核心 CSS Variables 齐全"))
    results.append(("@media" in text and ("900px" in text or "56.25rem" in text), "存在约 900px 响应式断点"))
    results.append(("prefers-reduced-motion" in text, "支持 reduced motion"))
    results.append(("overflow-x" in text, "存在横向溢出处理"))
    results.append(("scroll-behavior" in text or "scrollintoview" in low, "存在平滑/锚点滚动逻辑"))

    # Detect obviously heavy neon styling that conflicts with this skill.
    neon_hits = len(re.findall(r"#(?:00ffff|00e5ff|ff00ff|39ff14)\b", low))
    results.append((neon_hits == 0, "未发现典型霓虹主色"))

    # Avoid inline secrets in static artifacts.
    secret_patterns = [r"sk-[a-zA-Z0-9_-]{20,}", r"api[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]"]
    has_secret = any(re.search(p, text, re.I) for p in secret_patterns)
    results.append((not has_secret, "未发现疑似硬编码密钥"))

    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html", type=Path)
    args = ap.parse_args()
    if not args.html.exists():
        print(f"FAIL  文件不存在: {args.html}")
        return 2

    results = check(args.html)
    width = max(len(label) for _, label in results)
    failed = 0
    for ok, label in results:
        print(f"{'PASS' if ok else 'FAIL'}  {label:<{width}}")
        failed += 0 if ok else 1
    print(f"\n{len(results)-failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
