#!/usr/bin/env python3
"""校验本次五个视频Skill。开发依赖：PyYAML、jsonschema；不调用生成服务。"""
from pathlib import Path
import argparse
import json
import re
import sys
import yaml
from jsonschema import Draft202012Validator

NAMES = ['视频视觉开发总监', '视频镜头提示词', '场景视觉设计', '角色视觉设计', '分镜板提示词']


def count_text(text):
    text = re.sub(r'https?://[^\s)]+', '', text)
    return {
        'han': len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]', text)),
        'editorial': len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]|[A-Za-z]+(?:[-_][A-Za-z]+)*|[0-9]+(?:[.:][0-9]+)*', text)),
        'non_whitespace': len(re.sub(r'\s', '', text)),
    }


def check_repo(repo):
    problems, rows = [], []
    manifest = json.loads((repo / 'manifest.json').read_text(encoding='utf-8'))
    index = {item['name']: item for item in manifest['skills']}
    for name in NAMES:
        folder = repo / 'skills' / name
        meta = json.loads((folder / 'skill.json').read_text(encoding='utf-8'))
        text = (folder / 'SKILL.md').read_text(encoding='utf-8')
        match = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
        if not match:
            problems.append(f'{name}: 无有效frontmatter')
            continue
        front = yaml.safe_load(match.group(1))
        if front.get('name') != name or not isinstance(front.get('description'), str):
            problems.append(f'{name}: frontmatter名称或描述无效')
        if not re.fullmatch(r'[\u4e00-\u9fff]+', name):
            problems.append(f'{name}: 本次要求中文名称')
        if meta != index.get(name):
            problems.append(f'{name}: manifest与skill.json不一致')
        if 'version' in front or (front.get('metadata') or {}).get('version'):
            problems.append(f'{name}: 版本不应重复写在frontmatter')
        ui = yaml.safe_load((folder / 'agents/openai.yaml').read_text(encoding='utf-8'))
        if ui['interface']['display_name'] != name or f'${name}' not in ui['interface']['default_prompt']:
            problems.append(f'{name}: UI元数据不一致')
        markdowns = sorted(folder.rglob('*.md'))
        totals = {'han': 0, 'editorial': 0, 'non_whitespace': 0}
        for file in markdowns:
            body = file.read_text(encoding='utf-8')
            for metric, value in count_text(body).items():
                totals[metric] += value
            # Only local Markdown links, not citations, anchors or template placeholders.
            for target in re.findall(r'\[[^\]\n]+\]\(([^)]+)\)', body):
                if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                    continue
                resolved = (file.parent / target.split('#', 1)[0]).resolve()
                if not resolved.is_relative_to(folder.resolve()) or not resolved.exists():
                    problems.append(f'{file.relative_to(repo)}: 无效或越界引用 {target}')
            fence = None
            for line in body.splitlines():
                token = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
                if token:
                    marker, suffix = token.groups()
                    if fence is None:
                        fence = marker
                    elif marker[0] == fence[0] and len(marker) >= len(fence) and not suffix.strip():
                        fence = None
            if fence:
                problems.append(f'{file.relative_to(repo)}: 代码块未闭合')
        if not 10000 <= totals['editorial'] <= 15000:
            problems.append(f'{name}: 完整知识包字数越界 {totals["editorial"]}')
        if totals['han'] < 10000:
            problems.append(f'{name}: 纯汉字少于一万 {totals["han"]}')
        rows.append({'name': name, **totals, 'markdown_files': len(markdowns), 'status': meta['status']})

    schema_path = repo / 'skills/分镜板提示词/references/镜头组.schema.json'
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    shot = {'shot_id': 'S1', 'framing': '中近景', 'camera_move': '固定',
            'action_desc': '人物右手停在钥匙旁', 'assets': {'characters': ['甲_工作服'],
            'scenes': ['钟表铺'], 'key_props': [{'name': '铜钥匙', 'is_key_item': True}]}}
    valid = {'video_id': 'V1', 'scene_id': 'SC1', 'shots': [shot]}
    if list(validator.iter_errors(valid)):
        problems.append('Schema误拒绝合法的中近景与无时长输入')
    invalids = [dict(valid, shots=[]), dict(valid, duration_seconds=-1), dict(valid, aspect_ratio='1:0'),
                dict(valid, shots=[dict(shot, assets={'key_props': [{'name': '钥匙', 'is_key_item': 'true'}]})])]
    for number, invalid in enumerate(invalids, 1):
        if not list(validator.iter_errors(invalid)):
            problems.append(f'Schema未拒绝无效用例{number}')
    return {'scope': '结构、引用、字数、元数据和Schema；不代表完整行为质量门禁',
            'passed': not problems, 'full_quality_gate_passed': False, 'release_status': 'draft',
            'count_policy': 'Markdown完整知识包；汉字每字计1，英文单词与数字串各计1；URL不计。排除JSON、YAML、原文存档、仓库说明和验证报告。',
            'skills': rows, 'schema_cases': {'valid': 1, 'invalid': len(invalids)},
            'problems': problems, 'behavior': {'author_tabletop': 'recorded', 'independent_forward': 'pending', 'image_video_generation': 'pending'},
            'compatibility': '中文名称按用户与仓库约定校验；通用quick_validate的英文字母命名限制不作为本次硬门禁。'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = check_repo(args.repo.resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8', newline='\n')
    print(rendered)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
