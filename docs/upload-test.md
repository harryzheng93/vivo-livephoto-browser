# vivo Live Photo end-to-end upload test

This diagnostic flow uploads the original paired vivo JPG + MP4 without re-encoding either file.

## 1. Start the PC verification server

Use Python 3.7+ from the repository root:

```bash
python tools/livephoto_upload_server.py
```

The server uses only the Python standard library. On Windows, allow the Python process through the firewall on **Private networks** if prompted.

It prints one or more LAN addresses, for example:

```text
http://192.168.1.100:8000
```

Use an address reachable by the phone on the same LAN.

## 2. Install the current debug APK

Open GitHub **Actions → Android CI**, open the latest successful run for `feature/vivo-livephoto-demo`, download the `vivo-livephoto-test-apk` artifact, unzip it, and install `app-debug.apk`.

## 3. Pair and upload on the vivo phone

1. Grant full photo and video access.
2. Enter the PC base URL such as `http://192.168.1.100:8000` in **测试服务器地址**. The app adds `/api/live-photo` automatically.
3. Tap **选择 Live Photo** and choose an original vivo dynamic photo.
4. Confirm the diagnostic output reports `MATCH = TRUE` and `vivoMediaExtInfo: true`.
5. Tap **上传完整 Live Photo**.

The client sends a streaming `multipart/form-data` request containing:

- `image`: original JPG
- `video`: matched original MP4
- `livePhotoId`: the ID already verified to match both files

The Android client uses HTTP chunked transfer encoding so it does not need to assemble the full video request in memory.

## 4. Expected server result

The server decodes chunked HTTP bodies, saves both original media files under `livephoto_uploads/`, computes SHA-256, parses both vivo Live Photo IDs again, and returns JSON similar to:

```json
{
  "success": true,
  "ids_match": true,
  "submitted_id_match": true,
  "video_has_vivo_media_ext_info": true,
  "image_live_photo_id": "...",
  "video_live_photo_id": "...",
  "image_sha256": "...",
  "video_sha256": "..."
}
```

`success: true` means the complete chain is verified: MediaStore pairing on the phone, unmodified JPG/MP4 multipart transfer, and server-side ID re-validation.

## Scope and security

This is a local diagnostic tool. The debug app permits cleartext HTTP to support a LAN-only test server. A production uploader should use HTTPS, authentication, server-side size limits, and production storage controls.
