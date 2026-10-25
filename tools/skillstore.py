"""Shared storage, canonical package hashing and managed installation helpers."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parent.parent
START = "<!-- skillctl-managed:start -->"
END = "<!-- skillctl-managed:end -->"
PROTOCOL = 1
TEXT = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".html", ".css", ".js", ".ts", ".svg", ".csv", ".toml", ".xml", ".sh", ".ps1"}
SKIP = {".git", "__pycache__", "node_modules", ".skillctl", ".skillctl_backup", "outputs", "work"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".skillctl-write-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def git(repo, *args, binary=False, check=True):
    result = subprocess.run(["git", "-C", str(repo), *map(str, args)], capture_output=True)
    if check and result.returncode:
        # Avoid printing authentication URLs or credential-bearing remote output.
        raise ValueError(f"Git {args[0]} 失败；检查网络、认证、分支和工作区（退出码 {result.returncode}）")
    if binary:
        return result.stdout
    return result.stdout.decode("utf-8", "replace").strip()


def safe_name(value):
    if not value or value in {".", ".."} or any(c in value for c in '/\\\x00:<>"|?*') or value.startswith("."):
        raise ValueError(f"无效技能名称：{value!r}")
    if value.rstrip(" .") != value:
        raise ValueError("技能名称不能以空格或点结尾")
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)]}:
        raise ValueError("技能名称为系统保留名")
    return value


def safe_id(value):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ValueError(f"无效 id：{value!r}，需英文小写、数字和连字符")
    return value


def valid_version(value):
    if type(value) is not int or value < 1:
        raise ValueError(f"版本必须为正整数：{value!r}")
    return value


def canonical(name, data):
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".zip", ".pdf"} or b"\0" in data:
        return data
    try:
        return data.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    except UnicodeDecodeError:
        if suffix in TEXT:
            raise ValueError(f"文本文件需使用 UTF-8：{name}")
        return data


def eligible(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("包文件路径越界")
    if any(p in SKIP for p in path.parts) or name == "skill.json" or path.suffix in {".pyc", ".pyo"}:
        return False
    if any(p.startswith(".") for p in path.parts) or path.suffix.lower() in {".pem", ".key", ".p12"} or ".local." in path.name:
        raise ValueError(f"包内存在需排除的私有/隐藏文件：{name}")
    for part in path.parts:
        safe_name(part)
    return True


def validate_payload(files):
    if "SKILL.md" not in files:
        raise ValueError("技能缺少 SKILL.md")
    text = files["SKILL.md"].decode("utf-8")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match or not re.search(r"^name:[ \t]*[^\s]", match[1], re.M) or not re.search(r"^description:[ \t]*[^\s]", match[1], re.M):
        raise ValueError("SKILL.md 需要有效 name 和 description frontmatter")
    if START in text or END in text:
        raise ValueError("业务包中残留管理标记")
    for name, data in files.items():
        if not eligible(name):
            raise ValueError(f"业务包含管理文件：{name}")
        if name.endswith(".json"):
            json.loads(data)
        if name.endswith(".py"):
            compile(data, name, "exec")


def fingerprint(files):
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def strip_managed(text, expected):
    block = expected.get("managed_block")
    if not block:
        if START in text or END in text:
            raise ValueError("管理段无安装记录，不能自动移除")
        return text
    if text.count(START) != 1 or text.count(END) != 1 or not text.endswith(block):
        raise ValueError("管理段被修改或不完整，请先恢复安装记录中的管理段")
    return text[:-len(block)]


def package(root, record=None):
    root = Path(root)
    if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
        raise ValueError("不允许符号链接技能目录")
    files = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError(f"不允许包内链接：{rel}")
        if not path.is_file() or not eligible(rel):
            continue
        data = canonical(rel, path.read_bytes())
        if rel == "SKILL.md":
            data = strip_managed(data.decode("utf-8"), record or {}).encode("utf-8")
        files[rel] = data
    validate_payload(files)
    return files


def snapshot(repo, commit, name):
    safe_name(name)
    prefix = f"skills/{name}/"
    archive = git(repo, "archive", "--format=tar", commit, "--", f"skills/{name}", binary=True)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream:
            if member.isdir():
                continue
            if not member.isfile() or not member.name.startswith(prefix):
                raise ValueError("历史包存在链接或越界文件")
            name_in_package = member.name[len(prefix):]
            if eligible(name_in_package):
                files[name_in_package] = canonical(name_in_package, stream.extractfile(member).read())
    validate_payload(files)
    return files


def manifest(repo, ref=None):
    return json.loads(git(repo, "show", f"{ref}:manifest.json")) if ref else read_json(repo / "manifest.json")


def find_skill(data, key):
    matches = [s for s in data["skills"] if key in {s["name"], s.get("id"), s.get("slug"), *s.get("aliases", [])}]
    if len(matches) != 1:
        raise ValueError(f"技能名称/id 不存在或有歧义：{key}")
    return matches[0]


def release(repo, skill, version, ref=None):
    path = f"releases/{safe_id(skill['id'])}/{valid_version(version)}.json"
    return json.loads(git(repo, "show", f"{ref}:{path}")) if ref else read_json(repo / path)


def source(repo, record):
    ref = record.get("source_commit") or record["release_ref"]
    commit = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    files = snapshot(repo, commit, record["name"])
    if fingerprint(files) != record["content_sha256"]:
        raise ValueError("发布包校验值不匹配，已停止安装")
    return commit, files


def remote_ref(repo, offline=False):
    if offline:
        return "HEAD"
    git(repo, "fetch", "origin", "refs/heads/main:refs/remotes/origin/main", "--tags")
    return "refs/remotes/origin/main"


def rebuild(repo):
    data = {"schema": 2, "updated_at": now(), "skills": []}
    for folder in sorted((repo / "skills").iterdir()):
        if folder.is_dir():
            meta = read_json(folder / "skill.json")
            meta["id"] = safe_id(meta["id"])
            valid_version(meta["version"])
            data["skills"].append(meta)
    write_json(repo / "manifest.json", data)


def verify(repo, previous=None):
    data = manifest(repo)
    if data.get("schema") != 2:
        raise ValueError("仓库需先迁移为 schema 2")
    seen_ids, seen_names = set(), set()
    expected_paths = set()
    for skill in data["skills"]:
        name, ident, version = safe_name(skill["name"]), safe_id(skill["id"]), valid_version(skill["version"])
        if ident in seen_ids or name in seen_names:
            raise ValueError("重复技能 id 或名称")
        seen_ids.add(ident)
        seen_names.add(name)
        if read_json(repo / "skills" / name / "skill.json") != skill:
            raise ValueError(f"索引与元数据不一致：{name}")
        files = package(repo / "skills" / name)
        current = release(repo, skill, version)
        if current["content_sha256"] != fingerprint(files):
            raise ValueError(f"技能有未发布变更：{name}")
        for number in range(1, version + 1):
            path = f"releases/{ident}/{number}.json"
            expected_paths.add(path)
            entry = read_json(repo / path)
            if entry["id"] != ident or entry["name"] != name or entry["version"] != number or not entry.get("note", "").strip():
                raise ValueError(f"无效发布记录：{path}")
            if not re.fullmatch(r"[0-9a-f]{64}", entry["content_sha256"]):
                raise ValueError(f"无效内容校验值：{path}")
            if datetime.fromisoformat(entry["updated_at"]).tzinfo is None:
                raise ValueError(f"更新时间缺少时区：{path}")
            if entry["release_ref"] != f"skill/{ident}/v{number}":
                raise ValueError(f"无效发布引用：{path}")
    actual = {p.relative_to(repo).as_posix() for p in (repo / "releases").glob("*/*.json")}
    if actual != expected_paths or {p.name for p in (repo / "skills").iterdir() if p.is_dir()} != seen_names:
        raise ValueError("发现未索引的技能或发布记录")
    if previous:
        old_paths = git(repo, "ls-tree", "-r", "--name-only", previous, "--", "releases").splitlines()
        for path in old_paths:
            old = git(repo, "show", f"{previous}:{path}", binary=True)
            if not (repo / path).exists() or (repo / path).read_bytes() != old:
                raise ValueError(f"历史发布记录不可修改或删除：{path}")
        old = manifest(repo, previous)
        for skill in old["skills"]:
            latest = find_skill(data, skill.get("id", skill["name"]))
            if old.get("schema") == 2 and latest["version"] < skill["version"]:
                raise ValueError("版本不可倒退")
    return len(data["skills"])


def state_path(target):
    return target / ".skillctl.json"


def state(target):
    path = state_path(target)
    return read_json(path) if path.exists() else {"schema": 2, "installed": {}}


def write_files(root, files):
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def install(repo, target, skill, entry, pinned=False, force=False):
    target = target.resolve()
    name = safe_name(skill["name"])
    dest = target / name
    if target.is_relative_to(repo) or repo.is_relative_to(dest):
        raise ValueError("安装目录不能覆盖仓库")
    data = state(target)
    old = data["installed"].get(name)
    if old and type(old.get("version")) is int and old["version"] > entry["version"] and not pinned:
        raise ValueError("禁止隐式降级；如需旧版请明确指定 --version")
    if dest.exists():
        if dest.is_symlink() or (hasattr(dest, "is_junction") and dest.is_junction()):
            raise ValueError("安装目标不能是链接")
        try:
            changed = not old or fingerprint(package(dest, old)) != old.get("content_sha256")
        except (ValueError, KeyError):
            changed = True
        if changed and not force:
            raise ValueError(f"{name} 本地有改动或无可用基线；先发布或备份，不能直接覆盖")
    commit, files = source(repo, entry)
    # Keep historical dependencies, origin and maturity with historical business content.
    historical = json.loads(git(repo, "show", f"{commit}:skills/{name}/skill.json"))
    meta = dict(historical, id=skill["id"], name=name, version=entry["version"], updated_at=entry["updated_at"])
    if type(historical["version"]) is not int:
        meta["legacy_version"] = historical["version"]
    body = files["SKILL.md"].decode("utf-8")
    template = (repo / "policy" / "managed-skill.md").read_text(encoding="utf-8")
    block = "\n\n" + START + "\n" + template.rstrip() + "\n" + END + "\n"
    record = {"id": skill["id"], "version": entry["version"], "source_commit": commit,
              "content_sha256": fingerprint(files), "pinned": pinned, "protocol_version": PROTOCOL,
              "managed_block": block, "installed_at": now(), "repository": str(repo.resolve()),
              "origin": git(repo, "remote", "get-url", "origin", check=False)}
    target.mkdir(parents=True, exist_ok=True)
    # Keep previous content outside the skill discovery directory, including unmodified installs.
    with tempfile.TemporaryDirectory(prefix="skillctl-install-", dir=target.parent) as temp:
        stage = Path(temp) / name
        stage.mkdir()
        write_files(stage, files)
        (stage / "SKILL.md").write_text(body + block, encoding="utf-8", newline="\n")
        write_json(stage / "skill.json", meta)
        write_json(stage / ".skillctl" / "installation.json", record)
        maintenance = "# 维护入口\n\n本包为受管安装。使用安装记录中 repository 指向的仓库管理器，先读取本机 sync 配置。\n\n" + \
            f"```text\npython tools/skillctl.py --target {json.dumps(str(target), ensure_ascii=False)} publish {json.dumps(name, ensure_ascii=False)} --note \"本次实际修改摘要\"\n```\n\n" + \
            "在记录的 repository 目录执行。只同步 Skill 的维护变更，不上传任务输入或业务产物。\n" + \
            "若仓库路径失效，先重新 clone 同一来源仓库并核实 origin，再用 --adopt 接管。不要执行未知目录中的脚本。\n"
        (stage / ".skillctl" / "maintenance.md").write_text(maintenance, encoding="utf-8", newline="\n")
        backup = None
        if dest.exists():
            parent = target.parent / ".skillctl_backup"
            parent.mkdir(exist_ok=True)
            backup = parent / (name + "-" + datetime.now().strftime("%Y%m%d%H%M%S%f"))
            dest.rename(backup)
        try:
            stage.rename(dest)
            data["schema"] = 2
            data["installed"][name] = record
            write_json(state_path(target), data)
        except Exception:
            if dest.exists():
                shutil.rmtree(dest)
            if backup:
                backup.rename(dest)
            raise
    return record


@contextmanager
def operation_lock(path):
    """An OS lock releases on process exit; no stale PID lock recovery is needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("另一个管理操作正在进行，请稍后重试") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
