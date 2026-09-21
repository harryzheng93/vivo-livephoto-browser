#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

from email.parser import BytesParser
from email.policy import default
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import socket
import socketserver
import subprocess
import time
from livephoto_store import persist_verified_item

HOST = "0.0.0.0"
PORT = 8000
MAX_UPLOAD_BYTES = 250 * 1024 * 1024
SAVE_ROOT = os.path.abspath("livephoto_uploads")

LIVE_PHOTO_ID_RE = re.compile(
    br'com\.android\.camera\.livephoto(?:\\?\")?\s*[:=]\s*(?:\\?\")?([0-9a-f]{28})',
    re.IGNORECASE,
)


def find_live_photo_id(data):
    """Extract vivo's 28-character Live Photo ID from a JPG or MP4 byte string."""
    normalized = data.replace(b'\\"', b'"')
    match = LIVE_PHOTO_ID_RE.search(normalized)
    return match.group(1).decode("ascii").lower() if match else None


def verify_pair(image_bytes, video_bytes, submitted_id):
    image_id = find_live_photo_id(image_bytes)
    video_id = find_live_photo_id(video_bytes)
    marker = b"vivoMediaExtInfo" in video_bytes
    submitted = (submitted_id or "").strip().lower()

    ids_match = bool(image_id and video_id and image_id == video_id)
    submitted_id_match = bool(ids_match and submitted and submitted == image_id)

    return {
        "success": bool(ids_match and submitted_id_match and marker),
        "ids_match": ids_match,
        "submitted_id_match": submitted_id_match,
        "video_has_vivo_media_ext_info": marker,
        "image_live_photo_id": image_id,
        "video_live_photo_id": video_id,
        "submitted_live_photo_id": submitted or None,
        "image_size": len(image_bytes),
        "video_size": len(video_bytes),
        "image_sha256": sha256(image_bytes).hexdigest(),
        "video_sha256": sha256(video_bytes).hexdigest(),
    }


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ValueError("unexpected EOF while reading request body")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_chunked_body(stream, max_bytes=MAX_UPLOAD_BYTES):
    """Decode an HTTP/1.1 Transfer-Encoding: chunked body from a binary stream."""
    body = bytearray()

    while True:
        size_line = stream.readline()
        if not size_line:
            raise ValueError("unexpected EOF before chunk size")
        if len(size_line) > 4096:
            raise ValueError("chunk-size line too long")

        size_token = size_line.strip().split(b";", 1)[0]
        try:
            chunk_size = int(size_token, 16)
        except ValueError:
            raise ValueError("invalid chunk size")

        if chunk_size < 0:
            raise ValueError("invalid negative chunk size")

        if chunk_size == 0:
            # Consume optional trailer headers through the terminating blank line.
            while True:
                trailer = stream.readline()
                if trailer in (b"\r\n", b"\n", b""):
                    break
            return bytes(body)

        if len(body) + chunk_size > max_bytes:
            raise ValueError("upload exceeds %d bytes" % max_bytes)

        body.extend(_read_exact(stream, chunk_size))
        ending = _read_exact(stream, 2)
        if ending != b"\r\n":
            raise ValueError("chunk is not terminated by CRLF")


def _safe_filename(name, fallback):
    base = os.path.basename(name or fallback)
    base = re.sub(r"[^A-Za-z0-9._() -]", "_", base)
    return base or fallback


def _parse_multipart(content_type, body):
    raw = (
        ("Content-Type: %s\r\nMIME-Version: 1.0\r\n\r\n" % content_type).encode("ascii")
        + body
    )
    message = BytesParser(policy=default).parsebytes(raw)
    if not message.is_multipart():
        raise ValueError("request is not multipart/form-data")

    fields = {}
    files = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="Content-Disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is None:
            fields[name] = payload.decode("utf-8", "replace")
        else:
            files[name] = {
                "filename": filename,
                "content_type": part.get_content_type(),
                "data": payload,
            }
    return fields, files


def _lan_ips():
    ips = []
    if os.name == "nt":
        try:
            output = subprocess.check_output(["ipconfig"], stderr=subprocess.STDOUT)
            text = output.decode("gbk", "ignore")
            for ip in re.findall(r"IPv4[^:\r\n]*:\s*([0-9.]+)", text):
                if ip != "127.0.0.1" and not ip.startswith("169.254.") and ip not in ips:
                    ips.append(ip)
        except Exception:
            pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip != "127.0.0.1" and not ip.startswith("169.254.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


class SafeThreadingHTTPServer(ThreadingHTTPServer):
    """Avoid Windows getfqdn() decoding issues seen on localized host names."""

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        host, port = self.socket.getsockname()[:2]
        self.server_name = host
        self.server_port = port


class Handler(BaseHTTPRequestHandler):
    server_version = "VivoLivePhotoUploadTest/1.0"
    save_root = SAVE_ROOT

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.address_string(), fmt % args))

    def _send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        transfer_encoding = self.headers.get("Transfer-Encoding", "").lower()
        if "chunked" in transfer_encoding:
            return read_chunked_body(self.rfile)

        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise ValueError("missing Content-Length or chunked Transfer-Encoding")
        length = int(content_length)
        if length < 0 or length > MAX_UPLOAD_BYTES:
            raise ValueError("invalid or oversized Content-Length")
        return _read_exact(self.rfile, length)

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._send_json(200, {"ok": True, "endpoint": "/api/live-photo"})
        else:
            self._send_json(404, {"success": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/api/live-photo":
            self._send_json(404, {"success": False, "error": "not found"})
            return

        try:
            content_type = self.headers.get("Content-Type", "")
            if not content_type.lower().startswith("multipart/form-data"):
                raise ValueError("Content-Type must be multipart/form-data")

            body = self._read_body()
            fields, files = _parse_multipart(content_type, body)

            if "image" not in files or "video" not in files:
                raise ValueError("multipart fields image and video are required")
            submitted_id = fields.get("livePhotoId", "")
            if not submitted_id:
                raise ValueError("multipart field livePhotoId is required")

            image = files["image"]
            video = files["video"]
            result = verify_pair(image["data"], video["data"], submitted_id)

            if result["success"]:
                item = persist_verified_item(self.save_root, image, video, result)
                request_dir = os.path.join(self.save_root, item["itemId"])
                image_name = item["imageFilename"]
                video_name = item["videoFilename"]
                result["itemId"] = item["itemId"]
            else:
                stamp = time.strftime("%Y%m%d_%H%M%S")
                request_dir = os.path.join(self.save_root, stamp + "_%d" % int((time.time() % 1) * 1000))
                os.makedirs(request_dir, exist_ok=True)
                image_name = _safe_filename(image["filename"], "image.jpg")
                video_name = _safe_filename(video["filename"], "video.mp4")
                with open(os.path.join(request_dir, image_name), "wb") as f:
                    f.write(image["data"])
                with open(os.path.join(request_dir, video_name), "wb") as f:
                    f.write(video["data"])

            result.update({
                "image_filename": image_name,
                "video_filename": video_name,
                "saved_directory": request_dir,
            })

            print("\n=== vivo Live Photo upload ===")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("==============================\n")

            self._send_json(200 if result["success"] else 422, result)
        except Exception as exc:
            self._send_json(400, {"success": False, "error": str(exc)})


def main():
    os.makedirs(SAVE_ROOT, exist_ok=True)
    print("vivo Live Photo upload test server")
    print("PC: http://127.0.0.1:%d" % PORT)
    ips = _lan_ips()
    if ips:
        print("Phone and PC on the same LAN; try:")
        for ip in ips:
            print("  http://%s:%d" % (ip, PORT))
    else:
        print("Run ipconfig/ifconfig and use this computer's LAN IPv4 address on the phone.")
    print("POST endpoint: /api/live-photo")
    print("Saved uploads: %s" % SAVE_ROOT)
    print("Press Ctrl+C to stop.")
    SafeThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
