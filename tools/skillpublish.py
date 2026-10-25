"""Publish one package through a clean detached worktree and retryable journal."""
from __future__ import annotations
import shutil
import tempfile
from pathlib import Path
import skillstore as store


def confirm_remote(repo, pending):
    store.remote_ref(repo)
    line = store.git(repo, "ls-remote", "origin", f"refs/tags/{pending['tag']}")
    if not line or line.split()[0] != pending["commit"]:
        return False
    return pending["commit"] in store.git(repo, "rev-list", "refs/remotes/origin/main").splitlines()


def finish(repo, target, pending, path):
    existing = store.git(repo, "rev-parse", "--verify", f"refs/tags/{pending['tag']}", check=False)
    if existing and existing != pending["commit"]:
        raise ValueError("发布标签冲突，禁止覆盖。保留 pending；先 cancel-pending 归档，再合并最新版差异。")
    if not confirm_remote(repo, pending):
        current = store.git(repo, "rev-parse", "refs/remotes/origin/main")
        if current != pending["base"]:
            latest = store.manifest(repo, current)
            candidates = [s for s in latest["skills"] if s["id"] == pending["meta"]["id"]]
            expected = pending["meta"]["version"] - 1
            if (not candidates and expected != 0) or (candidates and candidates[0]["version"] != expected):
                raise ValueError("同一 Skill 已有并发新版本。保留 pending 和本地修改；先 cancel-pending 归档，再合并最新版差异。")
            if candidates:
                old = store.find_skill(store.manifest(repo, pending["base"]), pending["meta"]["id"])
                if store.release(repo, old, expected, pending["base"])["content_sha256"] != store.release(repo, candidates[0], expected, current)["content_sha256"]:
                    raise ValueError("并发修改了发布基线，不能自动覆盖")
            _, files = store.source(repo, dict(pending["entry"], source_commit=pending["commit"]))
            pending = prepare(repo, target, pending["meta"], pending["entry"], files, current, path)
        try:
            store.git(repo, "push", "--atomic", "origin", f"{pending['commit']}:refs/heads/main", f"{pending['commit']}:refs/tags/{pending['tag']}")
        except ValueError as exc:
            if not confirm_remote(repo, pending):
                raise ValueError("本地已提交，GitHub 尚未确认。保留 pending；修复网络/认证后用相同发布命令重试。若 main 已分叉需先解决冲突。") from exc
        if not confirm_remote(repo, pending):
            raise ValueError("远端发布未确认，保留 pending，不增加版本")
    store.install(repo, target, pending["meta"], pending["entry"], force=True)
    path.unlink()
    store.git(repo, "update-ref", "-d", f"refs/skillctl/pending/{pending['meta']['id']}", pending["commit"])
    return {"result": "已上传 GitHub 并刷新安装状态", "name": pending["meta"]["name"], "version": pending["meta"]["version"], "commit": pending["commit"], "tag": pending["tag"]}


def publish(repo, args):
    if not args.note.strip():
        raise ValueError("更新摘要不能为空")
    config_path = repo / ".skillctl-local" / "config.json"
    config = store.read_json(config_path) if config_path.exists() else {}
    if not config.get("auto_sync"):
        raise ValueError("当前 clone 尚未启用回传；仓库所有者可运行 sync --enable")
    origin = store.git(repo, "remote", "get-url", "origin")
    if config.get("origin") != origin:
        raise ValueError("origin 与启用回传时不一致，需核对后重新启用")
    ref = store.remote_ref(repo)
    data = store.manifest(repo, ref)
    if data.get("schema") != 2:
        raise ValueError("远端需先完成整数版本迁移")
    # Resolve retries before --new checks: the server may already have published it.
    for pending_path in (repo / ".skillctl-local" / "pending").glob("*.json"):
        pending = store.read_json(pending_path)
        if args.name not in {pending["meta"]["name"], pending["meta"]["id"], pending["meta"].get("slug")}:
            continue
        if Path(pending["target"]) != args.target:
            raise ValueError("此 Skill 有其他安装目录的待同步发布")
        local_record = store.state(args.target)["installed"].get(pending["meta"]["name"])
        files = store.package(args.target / pending["meta"]["name"], local_record)
        if pending["content_sha256"] != store.fingerprint(files):
            raise ValueError("待发布内容已变化；请从保留的 pending 提交恢复内容后重试")
        return finish(repo, args.target, pending, pending_path)
    if args.new:
        name, ident = store.safe_name(args.name), store.safe_id(args.id or "")
        if any({name, ident} & {s["name"], s["id"], s.get("slug"), *s.get("aliases", [])} for s in data["skills"]):
            raise ValueError("新增技能名称或 id 已存在")
        meta = store.read_json(args.target / name / "skill.json")
        if not str(meta.get("summary", "")).strip():
            raise ValueError("新技能 skill.json 需要 summary")
        meta.update(id=ident, name=name, version=0)
        record = None
    else:
        meta = store.find_skill(data, args.name)
        name, ident = meta["name"], meta["id"]
        record = store.state(args.target)["installed"].get(name)
        if not record or "content_sha256" not in record:
            raise ValueError("缺少受管安装基线，请先安装或使用 --new 新增")
        if Path(record["repository"]).resolve() != repo.resolve() and not args.adopt:
            raise ValueError("安装归属不同 clone；核对来源后使用 --adopt")
        if record.get("origin") != origin:
            raise ValueError("安装来源与当前仓库 origin 不一致，不能自动回传")
    files = store.package(args.target / name, record)
    content_hash = store.fingerprint(files)
    path = repo / ".skillctl-local" / "pending" / f"{ident}.json"
    if path.exists():
        pending = store.read_json(path)
        if pending["content_sha256"] != content_hash or Path(pending["target"]) != args.target:
            raise ValueError("仍有未完成发布；先恢复待发布内容并完成同步，不能覆盖 pending")
        return finish(repo, args.target, pending, path)
    if record:
        if record.get("pinned"):
            raise ValueError("历史安装已锁定；先备份修改，再解除锁定并解决与最新版的差异")
        if record["version"] != meta["version"]:
            raise ValueError("安装基线过旧，先解决与远端最新版的差异，不能覆盖")
        baseline = store.release(repo, meta, meta["version"], ref)
        if record["content_sha256"] != baseline["content_sha256"]:
            raise ValueError("安装基线与远端发布记录不一致")
        if content_hash == baseline["content_sha256"]:
            return {"result": "无业务变化，未增加版本", "version": meta["version"]}
    version = meta["version"] + 1
    tag = f"skill/{ident}/v{version}"
    if store.git(repo, "rev-parse", "--verify", f"refs/tags/{tag}", check=False):
        raise ValueError("版本标签已存在；先核对远端或待同步状态，不能覆盖")
    updated = store.now()
    meta = dict(meta, version=version, updated_at=updated)
    meta.pop("legacy_version", None)
    meta.pop("updated", None)
    meta.setdefault("origin", "self")
    meta["entry"] = "SKILL.md"
    entry = {"schema": 2, "id": ident, "name": name, "version": version, "updated_at": updated, "note": args.note.strip(), "release_ref": tag, "content_sha256": content_hash}
    pending = prepare(repo, args.target, meta, entry, files, store.git(repo, "rev-parse", ref), path)
    return finish(repo, args.target, pending, path)


def prepare(repo, target, meta, entry, files, base, path):
    name, ident, version = meta["name"], meta["id"], meta["version"]
    with tempfile.TemporaryDirectory(prefix="skillctl-publish-") as temp:
        checkout = Path(temp) / "checkout"
        store.git(repo, "worktree", "add", "--detach", str(checkout), base)
        try:
            folder = checkout / "skills" / name
            if folder.exists():
                if not folder.resolve().is_relative_to(checkout.resolve() / "skills"):
                    raise ValueError("发布路径越界")
                shutil.rmtree(folder)
            folder.mkdir(parents=True)
            store.write_files(folder, files)
            store.write_json(folder / "skill.json", meta)
            store.write_json(checkout / "releases" / ident / f"{version}.json", entry)
            store.rebuild(checkout)
            changelog = checkout / "CHANGELOG.md"
            lines = (changelog.read_text(encoding="utf-8") if changelog.exists() else "# 变更记录\n").splitlines()
            lines[1:1] = ["", f"- **{entry['updated_at']}** `{name}` → {version}：{entry['note']}", ""]
            changelog.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
            store.verify(checkout, base)
            store.git(checkout, "add", "--", f"skills/{name}", f"releases/{ident}/{version}.json", "manifest.json", "CHANGELOG.md")
            store.git(checkout, "-c", "user.name=" + (store.git(repo, "config", "user.name", check=False) or "Skillctl"), "-c", "user.email=" + (store.git(repo, "config", "user.email", check=False) or "skillctl@localhost"), "commit", "-m", f"发布 {name} v{version}：{entry['note']}")
            commit = store.git(checkout, "rev-parse", "HEAD")
            pending = {"schema": 1, "commit": commit, "base": base, "tag": entry["release_ref"], "meta": meta, "entry": entry, "content_sha256": entry["content_sha256"], "target": str(target)}
            store.write_json(path, pending)
            store.git(repo, "update-ref", f"refs/skillctl/pending/{ident}", commit)
        finally:
            store.git(repo, "worktree", "remove", "--force", str(checkout))
    return pending
