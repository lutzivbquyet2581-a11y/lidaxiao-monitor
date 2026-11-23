"""Publish a small allowlist of text files to a verified private GitHub repo."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

TRANSCRIPT = re.compile(r"\d{4}-\d{2}-\d{2}/(?:bilibili-BV[A-Za-z0-9]{10}|douyin-\d+)\.md")
RESEARCH = re.compile(r"research/(\d{4}-\d{2}-\d{2})\.md")
FIELDS = ("id", "title", "url", "platform", "published", "duration", "status", "transcript")


def api(gh, endpoint, payload=None, method=None):
    args = [str(gh), "api", endpoint]
    if method:
        args.extend(["--method", method])
    if payload is not None:
        args.extend(["--input", "-"])
    result = subprocess.run(
        args, input=None if payload is None else json.dumps(payload, ensure_ascii=False),
        encoding="utf-8", capture_output=True, timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        message = re.search(r"HTTP \d{3}", result.stderr)
        raise RuntimeError(f"GitHub API {message[0] if message else '请求失败'}")
    return json.loads(result.stdout)


def status_doc(videos, failure, last_ok):
    now = datetime.now(timezone.utc)

    def public_fields(video):
        return None if video is None else {key: video[key] for key in FIELDS if key in video}

    ranked = sorted(videos.values(), key=lambda v: v.get("published") or 0, reverse=True)
    newest_dated = next((v for v in ranked if v.get("published")), None)
    newest_complete = next((v for v in ranked if v.get("transcript")), None)
    undated = [v for v in ranked if not v.get("published")]
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "last_successful_feed_check": last_ok,
        "bilibili_feed_error": failure or None,
        "douyin_feed_status": "not_configured",
        "latest_publication_confirmed": not failure and not undated and newest_dated is not None,
        "newest_dated_video": public_fields(newest_dated),
        "newest_completed_video": public_fields(newest_complete),
        "pending_videos": [public_fields(v) for v in ranked if not v.get("transcript")],
        "failed_videos": [public_fields(v) for v in ranked if not v.get("transcript") and v.get("attempts")],
        "freshness_note": "先核对发现时间和失败状态。最新已转写视频可能早于最新发布视频。"
    }


def export(root, index, status):
    files = {"docs/transcripts/index.md": index,
             "docs/status/latest.json": json.dumps(status, ensure_ascii=False, indent=2) + "\n"}
    for folder in root.iterdir():
        if not folder.is_dir() or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", folder.name):
            continue
        for source in folder.glob("*.md"):
            rel = source.relative_to(root).as_posix()
            if TRANSCRIPT.fullmatch(rel) and source.resolve().is_relative_to(root):
                files["docs/transcripts/" + rel] = source.read_text(encoding="utf-8")
    for source in (root / "research").glob("*.md"):
        rel = source.relative_to(root).as_posix()
        if RESEARCH.fullmatch(rel) and source.resolve().is_relative_to(root):
            files["docs/" + rel] = source.read_text(encoding="utf-8")
    recent = status["newest_completed_video"]
    if recent:
        rel = recent["transcript"]
        if not TRANSCRIPT.fullmatch(rel) or "docs/transcripts/" + rel not in files:
            raise RuntimeError("最新文字稿索引指向未导出的文件")
        files["docs/transcripts/latest.md"] = (
            "[先检查数据新鲜度与未完成视频](../status/latest.json)\n\n"
            f"[历史索引](index.md) · [当日研究报告](../research/{rel.split('/')[0]}.md)\n\n"
            + files["docs/transcripts/" + rel]
        )
    return files


def push(gh, repo, files):
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ValueError("私有仓库必须使用 owner/name 格式")
    prefix = f"repos/{repo}"
    metadata = api(gh, prefix)
    if metadata["full_name"].casefold() != repo.casefold() or not metadata["private"]:
        raise RuntimeError("全文同步目标必须是指定的私有仓库")
    ref = f"{prefix}/git/ref/heads/{metadata['default_branch']}"
    head = api(gh, ref)["object"]["sha"]
    base_tree = api(gh, f"{prefix}/git/commits/{head}")["tree"]["sha"]
    entries = [dict(path=path, mode="100644", type="blob", content=content)
               for path, content in files.items()]
    tree = api(gh, f"{prefix}/git/trees", {"base_tree": base_tree, "tree": entries})["sha"]
    if tree == base_tree:
        return head
    commit = api(gh, f"{prefix}/git/commits",
                 {"message": "Update private LiDaxiao archive", "tree": tree, "parents": [head]})["sha"]
    api(gh, ref.replace("/git/ref/", "/git/refs/"), {"sha": commit, "force": False}, method="PATCH")
    return commit
