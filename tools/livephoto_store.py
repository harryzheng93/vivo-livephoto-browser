"""Indexed storage for verified vivo JPG/MP4 pairs."""

from datetime import datetime, timezone
import json
import os
import re
import uuid


UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _item_dir(root, item_id):
    if not UUID_RE.fullmatch(item_id or ""):
        raise KeyError(item_id)
    directory = os.path.realpath(os.path.join(root, item_id))
    if os.path.commonpath((os.path.realpath(root), directory)) != os.path.realpath(root):
        raise KeyError(item_id)
    return directory


def _filename(value, fallback, suffix):
    name = (value or fallback).replace("\\", "/").rsplit("/", 1)[-1]
    stem = os.path.splitext(name)[0]
    stem = re.sub(r"[^A-Za-z0-9._() -]", "_", stem).strip(". ") or os.path.splitext(fallback)[0]
    return stem + suffix


def persist_verified_item(root, image, video, verification, item_id=None, created_at=None):
    if not verification.get("success"):
        raise ValueError("pair verification failed")
    item_id = item_id or str(uuid.uuid4())
    directory = _item_dir(root, item_id)
    if os.path.exists(directory):
        raise FileExistsError(directory)
    image_name = _filename(image.get("filename"), "image.jpg", ".jpg")
    video_name = _filename(video.get("filename"), "video.mp4", ".mp4")
    created_at = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {
        "schemaVersion": 1, "itemId": item_id, "createdAt": created_at,
        "livePhotoId": verification["image_live_photo_id"],
        "imageFilename": image_name, "videoFilename": video_name,
        "imageContentType": image.get("content_type", "image/jpeg"),
        "videoContentType": video.get("content_type", "video/mp4"),
        "imageSize": verification["image_size"], "videoSize": verification["video_size"],
        "imageSha256": verification["image_sha256"],
        "videoSha256": verification["video_sha256"],
        "videoHasVivoMediaExtInfo": verification["video_has_vivo_media_ext_info"],
    }
    os.makedirs(directory)
    try:
        for name, data in ((image_name, image["data"]), (video_name, video["data"])):
            with open(os.path.join(directory, name), "wb") as output:
                output.write(data)
        pending = os.path.join(directory, "manifest.json.tmp")
        with open(pending, "w", encoding="utf-8") as output:
            json.dump(manifest, output, ensure_ascii=False)
        os.replace(pending, os.path.join(directory, "manifest.json"))
    except Exception:
        for name in (image_name, video_name, "manifest.json.tmp"):
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                os.remove(path)
        os.rmdir(directory)
        raise
    return manifest


def load_item(root, item_id):
    directory = _item_dir(root, item_id)
    try:
        with open(os.path.join(directory, "manifest.json"), encoding="utf-8") as source:
            item = json.load(source)
        if item["itemId"] != item_id or item["schemaVersion"] != 1:
            raise KeyError(item_id)
        return item
    except (OSError, ValueError, TypeError, KeyError):
        raise KeyError(item_id)


def list_items(root):
    if not os.path.isdir(root):
        return []
    items = []
    for name in os.listdir(root):
        try:
            items.append(load_item(root, name))
        except KeyError:
            continue
    return sorted(items, key=lambda item: item["createdAt"], reverse=True)


def media_path(root, item_id, kind):
    if kind not in ("image", "video"):
        raise KeyError(kind)
    directory = _item_dir(root, item_id)
    item = load_item(root, item_id)
    path = os.path.realpath(os.path.join(directory, item[kind + "Filename"]))
    if os.path.commonpath((directory, path)) != directory or not os.path.isfile(path):
        raise KeyError(item_id)
    return path
