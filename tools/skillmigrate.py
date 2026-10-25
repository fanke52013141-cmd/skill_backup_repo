"""One-time, history-preserving conversion from semver to integer releases."""
import json
import re

import skillstore as store


def migrate(repo):
    data = store.manifest(repo)
    if data.get("schema") == 2:
        store.verify(repo)
        return []
    mappings = []
    changes = {}
    identities = set()
    for item in data["skills"]:
        name = store.safe_name(item["name"])
        ident = store.safe_id(re.sub(r"[^a-z0-9]+", "-", item["slug"].lower()).strip("-"))
        if ident in identities:
            raise ValueError("迁移后 id 重复，请先核对 slug")
        identities.add(ident)
        commits = store.git(repo, "log", "--reverse", "--format=%H", "HEAD", "--", f"skills/{name}").splitlines()
        releases = []
        seen = set()
        for commit in commits:
            raw = store.git(repo, "show", f"{commit}:skills/{name}/skill.json", check=False)
            if not raw:
                continue
            meta = json.loads(raw)
            version = meta["version"]
            if releases and releases[-1]["legacy_version"] == version:
                # Keep the last snapshot within each uninterrupted legacy version.
                releases[-1]["source_commit"] = commit
                continue
            if version in seen:
                raise ValueError(f"{name} 的旧版本号重复使用，需要人工核对")
            seen.add(version)
            releases.append({"legacy_version": version, "source_commit": commit})
        if not releases:
            raise ValueError(f"{name} 找不到已提交的版本历史")
        for number, old in enumerate(releases, 1):
            commit = old["source_commit"]
            info = store.git(repo, "show", "-s", "--format=%cI%n%s", commit).splitlines()
            entry = dict(old, schema=2, id=ident, name=name, version=number,
                         updated_at=info[0], note=f"旧版 {old['legacy_version']} 映射；{info[1]}",
                         release_ref=f"skill/{ident}/v{number}",
                         content_sha256=store.fingerprint(store.snapshot(repo, commit, name)))
            path = repo / "releases" / ident / f"{number}.json"
            if path.exists():
                raise ValueError(f"迁移不能覆盖既有发布记录：{path}")
            changes[path] = entry
            mappings.append(entry)
        current = store.read_json(repo / "skills" / name / "skill.json")
        if store.fingerprint(store.package(repo / "skills" / name)) != mappings[-1]["content_sha256"]:
            raise ValueError(f"{name} 存在未提交的业务修改，停止迁移")
        current.update(id=ident, version=len(releases), legacy_version=current["version"],
                       updated_at=mappings[-1]["updated_at"])
        changes[repo / "skills" / name / "skill.json"] = current
    # Complete all historical/package checks before mutating any metadata.
    for path, value in changes.items():
        store.write_json(path, value)
    store.rebuild(repo)
    store.verify(repo)
    return mappings
