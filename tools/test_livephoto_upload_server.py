import io
import json
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from livephoto_upload_server import Handler, SafeThreadingHTTPServer, find_live_photo_id, read_chunked_body, verify_pair
from livephoto_store import persist_verified_item


LIVE_ID = "1789612876587fd1c83d00000000"


class LivePhotoUploadServerTest(unittest.TestCase):
    def test_finds_vivo_live_photo_id(self):
        data = (
            b'prefix {"com.android.camera.livephoto":"'
            + LIVE_ID.encode("ascii")
            + b'"} suffix'
        )
        self.assertEqual(LIVE_ID, find_live_photo_id(data))

    def test_verifies_original_jpg_and_mp4_pair(self):
        image = b"JPEG\xff\xd9" + (
            b'{"com.android.camera.livephoto":"' + LIVE_ID.encode("ascii") + b'"}'
        )
        video = (
            b"\x00\x00\x00\x18ftypisom"
            b"vivoMediaExtInfo"
            b'{"com.android.camera.livephoto":"' + LIVE_ID.encode("ascii") + b'"}'
        )

        result = verify_pair(image, video, LIVE_ID)

        self.assertTrue(result["success"])
        self.assertTrue(result["ids_match"])
        self.assertTrue(result["submitted_id_match"])
        self.assertTrue(result["video_has_vivo_media_ext_info"])
        self.assertEqual(LIVE_ID, result["image_live_photo_id"])
        self.assertEqual(LIVE_ID, result["video_live_photo_id"])
        self.assertEqual(len(image), result["image_size"])
        self.assertEqual(len(video), result["video_size"])
        self.assertEqual(64, len(result["image_sha256"]))
        self.assertEqual(64, len(result["video_sha256"]))

    def test_rejects_mismatched_submitted_id(self):
        image = b'com.android.camera.livephoto":"' + LIVE_ID.encode("ascii") + b'"'
        video = (
            b"vivoMediaExtInfo com.android.camera.livephoto\":\""
            + LIVE_ID.encode("ascii")
            + b'"'
        )
        result = verify_pair(image, video, "1789612876587fd1c83d00000001")
        self.assertFalse(result["success"])
        self.assertFalse(result["submitted_id_match"])

    def test_reads_http_chunked_body(self):
        raw = (
            b"4\r\nWiki\r\n"
            b"5\r\npedia\r\n"
            b"E\r\n in\r\n\r\nchunks.\r\n"
            b"0\r\nX-Debug: yes\r\n\r\n"
        )
        self.assertEqual(b"Wikipedia in\r\n\r\nchunks.", read_chunked_body(io.BytesIO(raw)))


if __name__ == "__main__":
    unittest.main()


class LivePhotoReadApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        class TestHandler(Handler):
            save_root = self.temp.name
            def log_message(self, fmt, *args):
                pass
        self.server = SafeThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = "http://127.0.0.1:%d" % self.server.server_port
        self.item_id = "11111111-1111-4111-8111-111111111111"
        self.image = b"JPEG-original-123"
        self.video = b"MP4-original-456"
        persist_verified_item(self.temp.name,
            {"filename": "IMG_1.jpg", "content_type": "image/jpeg", "data": self.image},
            {"filename": "IMG_1.mp4", "content_type": "video/mp4", "data": self.video},
            {"success": True, "image_live_photo_id": LIVE_ID,
             "image_size": len(self.image), "video_size": len(self.video),
             "image_sha256": "a" * 64, "video_sha256": "b" * 64,
             "video_has_vivo_media_ext_info": True}, item_id=self.item_id)

    def get(self, path):
        with urlopen(self.base + path) as response:
            return response.status, response.headers, response.read()

    def test_list_metadata_and_raw_media(self):
        _, _, body = self.get("/api/live-photos")
        items = json.loads(body)["items"]
        self.assertEqual([self.item_id], [item["itemId"] for item in items])
        path = "/api/live-photo/" + self.item_id
        _, _, body = self.get(path)
        item = json.loads(body)
        self.assertEqual(path, item["metadataUrl"])
        self.assertEqual(path + "/image", item["imageUrl"])
        self.assertEqual(path + "/video", item["videoUrl"])
        self.assertEqual("/gallery", item["galleryUrl"])
        self.assertEqual(self.image, self.get(path + "/image")[2])
        self.assertEqual(self.video, self.get(path + "/video")[2])

    def test_rejects_invalid_item_path(self):
        for path in ("/api/live-photo/not-a-uuid", "/api/live-photo/../outside/image"):
            with self.assertRaises(HTTPError) as failure:
                self.get(path)
            self.assertEqual(404, failure.exception.code)

    def test_gallery_uses_safe_dom_text_and_pointer_preview(self):
        _, headers, body = self.get("/gallery")
        html = body.decode("utf-8")
        self.assertIn("text/html", headers["Content-Type"])
        for word in ("pointerdown", "pointerup", "textContent"):
            self.assertIn(word, html)
        self.assertNotIn("innerHTML", html)
        self.assertNotIn(self.image.decode("ascii"), html)
