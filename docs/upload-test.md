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

## 5. Preview the indexed pair in a browser

After a successful upload, open the server base URL plus `/gallery`, for example:

```text
http://192.168.1.100:8000/gallery
```

Verify all of the following:

- The JPG is visible while idle.
- Pressing and holding the card plays the MP4; releasing returns to the JPG.
- The play/stop button works independently.
- The JPG and MP4 download links return the original files.

This is a browser Live Photo-style preview. It does not mean the browser natively recognizes vivo's format.

## 6. Download and restore on the vivo X200s

1. Keep the PC server running and the phone on the same LAN.
2. In the app, keep the same server address and tap **加载服务器 Live Photo**.
3. Select the uploaded item in the list.
4. Tap **下载并恢复到 vivo 相册**.
5. Wait for the diagnostic output to report `RESTORE_VALIDATED = TRUE`.

Before creating public media rows, the app verifies both SHA-256 values, both 28-character Live Photo IDs, and `vivoMediaExtInfo`. It then writes a same-basename JPG + MP4 pair under `DCIM/Camera/` using pending MediaStore rows, reopens both rows, and repeats the integrity and metadata checks before publishing. Any failure rolls back both rows and deletes the temporary downloads.

`RESTORE_VALIDATED = TRUE` means the public MediaStore copies preserve the expected bytes and vivo metadata. It is not a claim that vivo Gallery has recognized the pair as a dynamic photo.

## 7. Record the vivo Gallery observation

1. Tap **打开恢复后的照片** and choose vivo Gallery if Android shows an app chooser.
2. Inspect the restored image and record:

```text
dynamic-photo badge: YES / NO
press/hold dynamic playback: YES / NO
```

Also retain the app diagnostic block containing both restored filenames, both post-write IDs, `vivoMediaExtInfo: true`, and `RESTORE_VALIDATED = TRUE`.

A validated MediaStore restore that remains static in vivo Gallery is a valid experimental result. Record both observations as `NO`; that result triggers a separate investigation of vendor-private registration/index state. Do not write private vivo databases or delete the original photo as part of this feature.

## 8. Expected acceptance record

```text
Browser:
- /gallery loads: YES / NO
- JPG idle preview: YES / NO
- MP4 press/play preview: YES / NO
- original downloads verified: YES / NO

Android restore:
- RESTORE_VALIDATED = TRUE / FALSE
- paired basename under DCIM/Camera/: YES / NO

vivo Gallery observation:
- dynamic-photo badge: YES / NO
- press/hold dynamic playback: YES / NO
```

## Scope and security

This is a local diagnostic tool. The debug app permits cleartext HTTP to support a LAN-only test server. A production uploader should use HTTPS, authentication, server-side size limits, and production storage controls.
