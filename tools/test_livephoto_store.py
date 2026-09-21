import json
import os
import tempfile
import unittest

from livephoto_store import persist_verified_item, list_items, load_item, media_path


LIVE_ID = "1789612876587fd1c83d00000000"
FIRST = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"


def verified():
    return {
        "success": True,
        "image_live_photo_id": LIVE_ID,
        "video_live_photo_id": LIVE_ID,
        "image_size": 5,
        "video_size": 6,
        "image_sha256": "a" * 64,
        "video_sha256": "b" * 64,
        "video_has_vivo_media_ext_info": True,
    }


class LivePhotoStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    def save(self, item_id=FIRST, created_at="2026-09-20T12:00:00Z", image_name="IMG_1.jpg"):
        return persist_verified_item(
            self.root,
            {"filename": image_name, "content_type": "image/jpeg", "data": b"image"},
            {"filename": "IMG_1.mp4", "content_type": "video/mp4", "data": b"video!"},
            verified(), item_id=item_id, created_at=created_at,
        )

    def test_persists_pair_and_manifest(self):
        item = self.save()
        with open(media_path(self.root, FIRST, "image"), "rb") as source:
            self.assertEqual(b"image", source.read())
        with open(media_path(self.root, FIRST, "video"), "rb") as source:
            self.assertEqual(b"video!", source.read())
        with open(os.path.join(self.root, FIRST, "manifest.json"), encoding="utf-8") as source:
            self.assertEqual(item, json.load(source))
        self.assertEqual(LIVE_ID, load_item(self.root, FIRST)["livePhotoId"])

    def test_lists_newest_first(self):
        self.save()
        self.save(SECOND, "2026-09-21T12:00:00Z")
        self.assertEqual([SECOND, FIRST], [item["itemId"] for item in list_items(self.root)])

    def test_rejects_invalid_ids(self):
        self.save()
        for item_id in ("../outside", "not-a-uuid"):
            with self.assertRaises(KeyError):
                load_item(self.root, item_id)

    def test_hostile_filename_stays_inside_item(self):
        item = self.save(image_name="../../<script>.jpg")
        self.assertNotIn("/", item["imageFilename"])
        self.assertNotIn("<", item["imageFilename"])
        self.assertTrue(os.path.commonpath((self.root, media_path(self.root, FIRST, "image"))) == self.root)

    def test_failed_pair_is_not_indexed(self):
        check = verified()
        check["success"] = False
        with self.assertRaises(ValueError):
            persist_verified_item(self.root, {"filename": "x.jpg", "data": b"image"},
                                  {"filename": "x.mp4", "data": b"video!"}, check)
        self.assertEqual([], list_items(self.root))


if __name__ == "__main__":
    unittest.main()
