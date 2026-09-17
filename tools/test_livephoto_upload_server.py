import io
import unittest

from livephoto_upload_server import find_live_photo_id, read_chunked_body, verify_pair


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
