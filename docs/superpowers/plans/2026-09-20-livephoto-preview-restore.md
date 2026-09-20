# vivo Live Photo Preview and Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the proven vivo X200s upload diagnostic so a stored JPG+MP4 pair can be previewed in a browser, downloaded by the Android app, byte-validated, restored through MediaStore, and then checked in vivo Gallery for dynamic-photo recognition.

**Architecture:** Keep the existing Python standard-library LAN server and Kotlin Android app. The server gains indexed manifests, read APIs, and a Live Photo-style gallery; the Android app gains a small JSON/HTTP client, download verification, a pure restore coordinator, an Android MediaStore gateway, and minimal UI controls. Media bytes are never re-encoded, and final vivo Gallery recognition remains a human-observed acceptance test.

**Tech Stack:** Python 3.7+ standard library, Android/Kotlin, MediaStore, `HttpURLConnection`, `org.json`, JUnit 4, Gradle 8.9, JDK 17, compile/target SDK 35.

**Spec:** `docs/superpowers/specs/2026-09-20-livephoto-preview-restore-design.md`

## Global Constraints

- Restore-from-server is supported only on Android API 29+.
- Restored media goes to `DCIM/Camera/` with `IS_PENDING`.
- JPG and MP4 share one basename; any collision suffixes both with the same `_restored_N`.
- Media bytes are unchanged; no transcoding or metadata rewriting.
- Before MediaStore insertion require both manifest SHA-256 values, matching 28-char vivo IDs, and `vivoMediaExtInfo` in MP4.
- Re-open both MediaStore rows and validate again before publishing.
- On restore failure delete every MediaStore row created by that attempt and delete temporary files.
- Only new successful uploads are indexed; legacy upload directories are not migrated.
- Cleartext HTTP remains LAN-only diagnostic behavior.
- Never auto-delete the user's original photo.
- Scope remains the verified vivo X200s dual-file JPG+MP4 format.

## Review Focus

- Server input can be either `http://host:8000` or `http://host:8000/api/live-photo`; derived list/gallery/item URLs must use one correct base URL. Task 3 tests both.
- Hostile filenames such as `../../<script>.jpg` must not escape storage or become executable HTML. Tasks 1–2 test containment and DOM `textContent`.
- HTTP 200 with truncated/modified bytes must fail before MediaStore insertion. Task 4 tests hash/metadata mismatch.
- A collision in only one media collection must suffix both output names together. Task 4 tests asymmetric collision.
- Failure on the second write/publish must remove both created rows, including an already-published first row. Task 5 tests rollback.

---

### Task 1: Indexed server storage

**Files:**
- Create: `tools/livephoto_store.py`
- Create: `tools/test_livephoto_store.py`
- Modify: `tools/livephoto_upload_server.py`

**Interfaces:**
- Produces `persist_verified_item(root, image, video, verification, item_id=None, created_at=None) -> dict`
- Produces `list_items(root) -> list[dict]`, `load_item(root, item_id) -> dict`, `media_path(root, item_id, kind) -> str`
- Manifest keys: `schemaVersion`, `itemId`, `createdAt`, `livePhotoId`, filenames, content types, sizes, SHA-256 values, `videoHasVivoMediaExtInfo`.

- [ ] **Step 1: Write failing storage tests**

Create `tools/test_livephoto_store.py` with `TemporaryDirectory`. Use:

```python
LIVE_ID = "1789612876587fd1c83d00000000"

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
```

Tests must assert:
1. exact JPG/MP4 bytes and `manifest.json` are written,
2. newest `createdAt` lists first,
3. `../outside` and malformed UUIDs raise `KeyError`,
4. `../../<script>.jpg` cannot escape the item directory,
5. `verification["success"] == False` raises and creates no manifest.

Representative creation:

```python
manifest = persist_verified_item(
    root,
    {"filename": "IMG_1.jpg", "content_type": "image/jpeg", "data": b"image"},
    {"filename": "IMG_1.mp4", "content_type": "video/mp4", "data": b"video!"},
    verified(),
    item_id="11111111-1111-4111-8111-111111111111",
    created_at="2026-09-20T12:00:00Z",
)
```

- [ ] **Step 2: Verify RED**

Run `python3 -m unittest tools/test_livephoto_store.py -v`

Expected: FAIL with missing `livephoto_store`.

- [ ] **Step 3: Implement storage**

`livephoto_store.py` uses only stdlib:
- UUID regex validation before path joining,
- basename sanitization,
- media writes first,
- `manifest.json.tmp` then `os.replace`,
- UTC ISO `Z` timestamps,
- `list_items` ignores directories without valid manifests,
- `media_path` uses `realpath` containment.

In the POST handler, call `persist_verified_item` only when existing `verify_pair` returns `success=True`. Failed pairs stay unindexed.

- [ ] **Step 4: Verify GREEN**

Run `python3 -m unittest discover -s tools -p 'test_*.py' -v`

Expected: all Python tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/livephoto_store.py tools/test_livephoto_store.py tools/livephoto_upload_server.py
git commit -m "feat: index verified Live Photo uploads"
```

### Task 2: Read APIs and browser preview

**Files:**
- Modify: `tools/livephoto_upload_server.py`
- Modify: `tools/test_livephoto_upload_server.py`

**Interfaces:**
- `GET /api/live-photos`
- `GET /api/live-photo/{itemId}`
- `GET /api/live-photo/{itemId}/image`
- `GET /api/live-photo/{itemId}/video`
- `GET /gallery`
- URL fields: `metadataUrl`, `imageUrl`, `videoUrl`, `galleryUrl`.

- [ ] **Step 1: Write failing route tests**

Add a temporary `SafeThreadingHTTPServer(("127.0.0.1", 0), TestHandler)` where `TestHandler.save_root` points at a temp directory.

Seed one indexed item and assert:
- list endpoint returns it,
- metadata endpoint returns relative canonical URLs,
- image/video endpoints return exact bytes,
- invalid/path-traversal item returns 404,
- `/gallery` contains `pointerdown`, `pointerup`, `textContent`,
- `/gallery` does not contain `innerHTML` or raw media bytes.

- [ ] **Step 2: Verify RED**

Run `python3 -m unittest tools.test_livephoto_upload_server.LivePhotoReadApiTest -v`

Expected: FAIL because routes and handler-specific storage root do not exist.

- [ ] **Step 3: Implement routes**

In `livephoto_upload_server.py`:
- set `Handler.save_root = SAVE_ROOT`,
- use `urlsplit(self.path)` for path/query parsing,
- decorate manifests with relative URLs,
- use `media_path` for raw bytes,
- add `Content-Disposition: attachment` only for `?download=1`,
- catch `KeyError` as 404,
- extend successful POST response with `itemId` and all URL fields.

- [ ] **Step 4: Implement static gallery**

Return static HTML/JS that fetches `/api/live-photos`. Each card:
- shows `<img>` while idle,
- uses muted inline `<video>`,
- on `pointerdown` hides image and plays video from 0,
- on `pointerup`, `pointercancel`, `pointerleave` pauses/resets video and restores image,
- offers a normal play/stop button,
- offers JPG/MP4 download links,
- inserts manifest strings only via DOM `textContent`, never `innerHTML`.

- [ ] **Step 5: Verify GREEN and commit**

Run `python3 -m unittest discover -s tools -p 'test_*.py' -v`

Then:

```bash
git add tools/livephoto_upload_server.py tools/test_livephoto_upload_server.py
git commit -m "feat: add Live Photo read APIs and gallery"
```

### Task 3: Android server endpoint, models, and client

**Files:**
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/ServerEndpoint.kt`
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/ServerLivePhotoModels.kt`
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/LivePhotoServerClient.kt`
- Create: `app/src/test/java/com/harryzheng/vivolivephoto/ServerEndpointTest.kt`
- Create: `app/src/test/java/com/harryzheng/vivolivephoto/ServerLivePhotoModelsTest.kt`
- Create: `app/src/test/java/com/harryzheng/vivolivephoto/LivePhotoServerClientTest.kt`
- Modify: `app/src/main/java/com/harryzheng/vivolivephoto/UploadEndpoint.kt`
- Modify: `app/src/test/java/com/harryzheng/vivolivephoto/UploadEndpointTest.kt`
- Modify: `app/build.gradle.kts`

**Interfaces:**
- `ServerEndpoint(baseUrl)` with `uploadUrl`, `listUrl`, `galleryUrl`, `absolute(path)`, `fromUserInput(input)`
- `ServerLivePhotoItem` with all manifest and URL fields
- `typealias ServerLivePhotoManifest = ServerLivePhotoItem`
- `ServerLivePhotoJson.parseList`, `parseManifest`
- `LivePhotoServerClient.list`, `manifest`, `download`
- Existing `UploadEndpoint.fromUserInput` delegates to `ServerEndpoint.uploadUrl`.

- [ ] **Step 1: Write failing endpoint tests**

```kotlin
assertEquals(
    "http://192.168.1.10:8000/api/live-photos",
    ServerEndpoint.fromUserInput("http://192.168.1.10:8000/").listUrl
)
assertEquals(
    "http://192.168.1.10:8000/gallery",
    ServerEndpoint.fromUserInput("http://192.168.1.10:8000/api/live-photo/").galleryUrl
)
```

Keep rejection of non-HTTP(S) input.

- [ ] **Step 2: Write failing JSON and download tests**

JSON test uses exact schema version 1 and asserts filename, ID, SHA, sizes, and URL fields. Schema version 2 must throw.

Client test injects a fake `HttpURLConnection` returning a 32 KiB byte array and asserts `download` writes exactly that file and returns its length.

- [ ] **Step 3: Verify RED**

Run:

```bash
gradle testDebugUnitTest --tests 'com.harryzheng.vivolivephoto.ServerEndpointTest' --tests 'com.harryzheng.vivolivephoto.ServerLivePhotoModelsTest' --tests 'com.harryzheng.vivolivephoto.LivePhotoServerClientTest' --stacktrace
```

Expected: unresolved new classes.

- [ ] **Step 4: Implement**

`ServerEndpoint.fromUserInput` trims whitespace/slashes, requires HTTP(S), and strips a trailing `/api/live-photo` before deriving all URLs.

Use `org.json.JSONObject` for parsing. Add only this JVM test runtime dependency:

```kotlin
testImplementation("org.json:json:20240303")
```

Parser requires:
- `schemaVersion == 1`,
- `[0-9a-f]{28}` ID,
- 64-hex SHA fields,
- non-negative sizes,
- all filenames/URL fields.

`LivePhotoServerClient` injects `(String) -> HttpURLConnection`, uses 15 s connect / 120 s read timeout, GETs JSON, and streams media to `File.outputStream()` with a 64 KiB buffer. Non-2xx throws with HTTP code.

- [ ] **Step 5: Verify GREEN and commit**

Run `gradle testDebugUnitTest --stacktrace`

Then:

```bash
git add app/build.gradle.kts app/src/main/java/com/harryzheng/vivolivephoto/ServerEndpoint.kt app/src/main/java/com/harryzheng/vivolivephoto/ServerLivePhotoModels.kt app/src/main/java/com/harryzheng/vivolivephoto/LivePhotoServerClient.kt app/src/main/java/com/harryzheng/vivolivephoto/UploadEndpoint.kt app/src/test/java/com/harryzheng/vivolivephoto/ServerEndpointTest.kt app/src/test/java/com/harryzheng/vivolivephoto/ServerLivePhotoModelsTest.kt app/src/test/java/com/harryzheng/vivolivephoto/LivePhotoServerClientTest.kt app/src/test/java/com/harryzheng/vivolivephoto/UploadEndpointTest.kt
git commit -m "feat: add Live Photo server client"
```

### Task 4: Download verification and paired restore naming

**Files:**
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/DownloadedLivePhotoVerifier.kt`
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/RestorePolicy.kt`
- Create: `app/src/test/java/com/harryzheng/vivolivephoto/DownloadedLivePhotoVerifierTest.kt`
- Create: `app/src/test/java/com/harryzheng/vivolivephoto/RestorePolicyTest.kt`

**Interfaces:**
- `VerifiedLivePhotoDownload(manifest, imageFile, videoFile)`
- `DownloadedLivePhotoVerifier.verify(...)`
- `MediaKind { IMAGE, VIDEO }`
- `RestoreNames(imageName, videoName)`
- `RestoreNamePlanner.choose(...)`
- `PostWriteMedia(sha256, livePhotoId, hasVivoMediaExtInfo)`
- `RestoreValidation.requirePostWriteMatch(...)`.

- [ ] **Step 1: Write failing verifier tests**

Create real temp files containing vivo markers. Cover:
- exact download passes,
- modified JPG fails SHA,
- modified MP4 fails SHA,
- MP4 missing `vivoMediaExtInfo` fails even if ID matches.

- [ ] **Step 2: Write failing naming tests**

Cover:
- free `IMG_1.jpg` + `IMG_1.mp4` unchanged,
- only VIDEO collision still produces `IMG_1_restored_1.jpg` and `.mp4`,
- `_restored_1` collision advances both to `_restored_2`,
- mismatched source stems normalize both target stems to the image stem.

- [ ] **Step 3: Verify RED**

Run:

```bash
gradle testDebugUnitTest --tests 'com.harryzheng.vivolivephoto.DownloadedLivePhotoVerifierTest' --tests 'com.harryzheng.vivolivephoto.RestorePolicyTest' --stacktrace
```

Expected: unresolved verifier/policy classes.

- [ ] **Step 4: Implement verification**

Compute SHA-256 with `MessageDigest` and stream files. Reuse `VivoMetadataScanner` with fresh streams.

Require image/video SHA == manifest, both IDs == manifest ID, IDs equal each other, and MP4 marker exists.

- [ ] **Step 5: Implement naming and post-write validation**

`RestoreNamePlanner` tests both media collections for each candidate. `RestoreValidation` rechecks both SHA values, both IDs, and MP4 marker against the verified manifest.

- [ ] **Step 6: Verify GREEN and commit**

Run `gradle testDebugUnitTest --stacktrace`

Commit:

```bash
git add app/src/main/java/com/harryzheng/vivolivephoto/DownloadedLivePhotoVerifier.kt app/src/main/java/com/harryzheng/vivolivephoto/RestorePolicy.kt app/src/test/java/com/harryzheng/vivolivephoto/DownloadedLivePhotoVerifierTest.kt app/src/test/java/com/harryzheng/vivolivephoto/RestorePolicyTest.kt
git commit -m "feat: verify downloads and plan restore names"
```

### Task 5: Transaction-safe MediaStore restore

**Files:**
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/LivePhotoRestoreCoordinator.kt`
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/AndroidMediaStoreGateway.kt`
- Create: `app/src/test/java/com/harryzheng/vivolivephoto/LivePhotoRestoreCoordinatorTest.kt`

**Interfaces:**
- `MediaRef(uri: String)`
- `RestoreResult(image, video, names, imagePostWrite, videoPostWrite)`
- `RestoreMediaGateway` methods: `exists`, `insertPending`, `write`, `inspect`, `publish`, `delete`
- `LivePhotoRestoreCoordinator.restore(verified)`
- `AndroidMediaStoreGateway(ContentResolver)`.

- [ ] **Step 1: Write failing coordinator tests**

Use a fake gateway that records events and can throw at a named event.

Cover:
1. happy order: insert/write image, insert/write video, inspect both, publish both;
2. second write failure deletes both created rows;
3. post-write validation failure deletes both;
4. second publish failure deletes both, including first already published row.

- [ ] **Step 2: Verify RED**

Run:

```bash
gradle testDebugUnitTest --tests 'com.harryzheng.vivolivephoto.LivePhotoRestoreCoordinatorTest' --stacktrace
```

Expected: unresolved coordinator/gateway.

- [ ] **Step 3: Implement coordinator**

Use fixed `relativePath = "DCIM/Camera/"`.
Get one paired name set from `RestoreNamePlanner`.
Track each created `MediaRef`.
On any throwable, delete all created refs in reverse order, swallow cleanup exceptions, then rethrow original failure.

- [ ] **Step 4: Implement Android gateway**

For API 29+:
- map IMAGE to `MediaStore.Images`, VIDEO to `MediaStore.Video`,
- `exists`: query `DISPLAY_NAME` + `RELATIVE_PATH`,
- `insertPending`: set `DISPLAY_NAME`, `MIME_TYPE`, `RELATIVE_PATH`, `IS_PENDING=1`,
- `write`: stream source file to resolver output,
- `inspect`: reopen row, compute SHA-256, parse ID, detect MP4 marker,
- `publish`: update `IS_PENDING=0` and require one updated row,
- `delete`: resolver delete.

- [ ] **Step 5: Verify GREEN and compile**

Run:

```bash
gradle testDebugUnitTest assembleDebug --stacktrace
```

Expected: tests PASS and debug APK exists.

- [ ] **Step 6: Commit**

```bash
git add app/src/main/java/com/harryzheng/vivolivephoto/LivePhotoRestoreCoordinator.kt app/src/main/java/com/harryzheng/vivolivephoto/AndroidMediaStoreGateway.kt app/src/test/java/com/harryzheng/vivolivephoto/LivePhotoRestoreCoordinatorTest.kt
git commit -m "feat: restore Live Photo pair through MediaStore"
```

### Task 6: UI wiring, diagnostics, docs, and final CI

**Files:**
- Modify: `app/src/main/java/com/harryzheng/vivolivephoto/MainActivity.kt`
- Modify: `app/src/main/java/com/harryzheng/vivolivephoto/RestorePolicy.kt`
- Modify: `app/src/main/res/layout/activity_main.xml`
- Modify: `app/src/main/res/values/strings.xml`
- Create: `app/src/test/java/com/harryzheng/vivolivephoto/RestoreDiagnosticsTest.kt`
- Modify: `docs/upload-test.md`
- Verify existing workflow.

**Interfaces:**
- Add buttons: open web gallery, load server items, restore selected item, open restored media.
- Add spinner for server items.
- Preserve all existing choose/pair/upload behavior.

- [ ] **Step 1: Write failing diagnostics test**

`RestoreDiagnostics.format(result)` must contain:
- `RESTORE_VALIDATED = TRUE`,
- both restored names and IDs,
- `vivoMediaExtInfo: true`,
- Chinese instruction to verify the vivo Gallery badge/playback,
- no claim that vivo Gallery recognition succeeded.

- [ ] **Step 2: Verify RED, then implement formatter**

Run the test and confirm unresolved `RestoreDiagnostics`, then add the formatter to `RestorePolicy.kt`.

- [ ] **Step 3: Add layout controls and strings**

Add IDs:
- `openGalleryButton`
- `loadServerItemsButton`
- `serverItemSpinner`
- `restoreButton` initially disabled
- `openRestoredButton` initially disabled

Chinese labels:
- `打开网页 Live Photo 预览`
- `加载服务器 Live Photo`
- `下载并恢复到 vivo 相册`
- `打开恢复后的照片`

- [ ] **Step 4: Wire gallery and list**

`openGalleryButton` launches `ACTION_VIEW` for `ServerEndpoint.galleryUrl`.

`loadServerItemsButton` loads on a background thread, populates the spinner with `createdAt + imageFilename + shortened ID`, and enables restore only when items exist and API >= 29.

Below API 29 append: `恢复功能需要 Android 10 / API 29+。`

- [ ] **Step 5: Wire restore**

On background thread:
1. fetch authoritative manifest,
2. create two temp files under `cacheDir/livephoto_restore`,
3. stream image/video into temp files,
4. call `DownloadedLivePhotoVerifier.verify`,
5. call `LivePhotoRestoreCoordinator(AndroidMediaStoreGateway(contentResolver)).restore`,
6. store restored image URI,
7. display `RestoreDiagnostics.format(result)`,
8. delete both temp files in `finally`.

No MediaStore write occurs before verification passes.

- [ ] **Step 6: Wire open restored image**

Launch `ACTION_VIEW` with restored image URI, MIME `image/jpeg`, and `FLAG_GRANT_READ_URI_PERMISSION`. Catch `ActivityNotFoundException`.

- [ ] **Step 7: Update real-device procedure**

Extend `docs/upload-test.md` through:
- `/gallery` browser preview,
- app server-item loading,
- restore,
- `RESTORE_VALIDATED = TRUE`,
- open restored image,
- record dynamic badge YES/NO and press/hold playback YES/NO.

State explicitly: validated MediaStore restore + static vivo Gallery is a valid experimental result and triggers a separate vendor-private-registration investigation.

- [ ] **Step 8: Full verification**

Run:

```bash
python3 -m unittest discover -s tools -p 'test_*.py' -v
gradle testDebugUnitTest --stacktrace
gradle assembleDebug --stacktrace
```

Expected: both suites PASS and `app-debug.apk` exists.

- [ ] **Step 9: Commit and verify PR CI**

Commit:

```bash
git add app/src/main/java/com/harryzheng/vivolivephoto/MainActivity.kt app/src/main/java/com/harryzheng/vivolivephoto/RestorePolicy.kt app/src/main/res/layout/activity_main.xml app/src/main/res/values/strings.xml app/src/test/java/com/harryzheng/vivolivephoto/RestoreDiagnosticsTest.kt docs/upload-test.md
git commit -m "feat: add Live Photo preview and restore flow"
```

Confirm the latest PR `Android CI` shows success for:
- Run upload server tests
- Run unit tests
- Build debug APK
- Upload APK

Confirm artifact remains `vivo-livephoto-test-apk`.

Do not merge `main`; keep PR #1 open until X200s observation is recorded.

## Final Acceptance Evidence

```text
CI:
- Python tests: PASS
- Android unit tests: PASS
- app-debug.apk: produced
- artifact: vivo-livephoto-test-apk

Browser:
- /gallery loads
- JPG visible while idle
- MP4 plays on press/play
- raw JPG/MP4 endpoints return original bytes

Android restore:
- pre-write SHA/ID validation: PASS
- post-write SHA/ID validation: PASS
- RESTORE_VALIDATED = TRUE
- restored files share basename under DCIM/Camera/

vivo Gallery observation:
- dynamic-photo badge: YES / NO
- press/hold dynamic playback: YES / NO
```

A `NO` in the final two vivo observations is a valid experimental result if `RESTORE_VALIDATED = TRUE`; it does not justify private database writes in this feature.
