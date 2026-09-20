# vivo Live Photo Online Preview and Restore Design

## Intent

Extend the existing vivo X200s diagnostic project from a successful upload proof into a reversible end-to-end Live Photo workflow:

1. upload the original paired JPG + MP4,
2. browse and preview the pair from a normal web browser,
3. download the same original bytes through the Android app,
4. restore the pair into Android shared media storage, and
5. verify on the vivo X200s whether the stock gallery recognizes the restored pair as a dynamic photo.

The important product question is not merely whether both files can be downloaded. The decisive result is whether a pair restored through public Android MediaStore APIs is recognized by vivo's gallery without additional private database state.

## Current Baseline

The existing branch already proves that, on the user's vivo X200s:

- a selected vivo dynamic-photo JPG exposes a 28-character `com.android.camera.livephoto` ID,
- the companion MP4 can be found through `MediaStore.Video`,
- the MP4 contains `vivoMediaExtInfo`,
- the JPG and MP4 Live Photo IDs can be matched,
- the original pair can be streamed to a Python LAN server without re-encoding, and
- the server can validate both IDs and SHA-256 values.

This design preserves that upload path and builds on it rather than replacing it.

## Scope

### In scope

- Persistent server-side item metadata for newly uploaded Live Photos.
- JSON APIs for listing items and reading one item's metadata.
- Raw image/video download endpoints that return the exact stored bytes.
- A browser gallery for Live Photo-style preview.
- Android client support for listing server items.
- Android streaming download into app-private temporary files.
- Integrity and vivo metadata validation before restoration.
- MediaStore restoration of a same-basename JPG + MP4 pair under `DCIM/Camera/`.
- Transaction-like cleanup if either restored media write fails.
- A user action to open the restored media in a gallery-capable app for verification.
- CI tests for server API/storage behavior and pure Kotlin restoration-planning logic.

### Out of scope

- Pixel, Samsung, Xiaomi, OPPO, or newer vivo single-file Motion Photo variants.
- Editing, transcoding, thumbnail generation, or recompressing media.
- Public Internet hosting, authentication, TLS termination, multi-user authorization, or cloud object storage.
- Reverse engineering vivo private gallery databases unless the public MediaStore restoration experiment fails.
- Automatically deleting the user's original photo before the restore experiment.

## Architecture

The existing Python diagnostic server remains the storage and preview service. The existing Android app remains the privileged local-media bridge.

```text
vivo X200s
  |
  | original JPG + MP4
  v
Android diagnostic app
  |
  | multipart upload
  v
Python LAN server
  |-- item manifest
  |-- original JPG bytes
  |-- original MP4 bytes
  |-- JSON API
  '-- /gallery web preview
        |
        | list + raw downloads
        v
Android diagnostic app
  |
  | validate IDs + hashes
  | write through MediaStore
  v
DCIM/Camera/<same-basename>.jpg
DCIM/Camera/<same-basename>.mp4
  |
  v
vivo stock gallery recognition test
```

The browser preview is intentionally separate from Android restoration. Browsers can display the two server resources as one logical Live Photo, but they are not expected to understand vivo's private pairing format natively.

## Server Storage Model

Every **new successful upload** receives a generated `itemId`. Existing legacy upload directories created by the current diagnostic server are not automatically migrated; the user can re-upload a pair to create an indexed item.

Storage layout:

```text
livephoto_uploads/
  <itemId>/
    manifest.json
    <original-basename>.jpg
    <original-basename>.mp4
```

`itemId` is an opaque server-generated identifier and is not derived from a user-controlled filename. A UUID is sufficient for the diagnostic server.

The manifest contains:

```json
{
  "schemaVersion": 1,
  "itemId": "...",
  "createdAt": "...",
  "livePhotoId": "...",
  "imageFilename": "...jpg",
  "videoFilename": "...mp4",
  "imageContentType": "image/jpeg",
  "videoContentType": "video/mp4",
  "imageSize": 123,
  "videoSize": 456,
  "imageSha256": "...",
  "videoSha256": "...",
  "videoHasVivoMediaExtInfo": true
}
```

A manifest is written only after the existing upload validation succeeds. Failed or mismatched uploads keep the current error response and are not indexed as restorable items.

## Server API

The existing upload endpoint stays compatible:

### `POST /api/live-photo`

On success, the current response is extended with:

- `itemId`
- `metadataUrl`
- `imageUrl`
- `videoUrl`
- `galleryUrl`

### `GET /api/live-photos`

Returns a JSON object containing a newest-first `items` array. Each list item contains enough metadata for the Android selector without embedding media bytes.

### `GET /api/live-photo/{itemId}`

Returns the manifest plus canonical media URLs.

### `GET /api/live-photo/{itemId}/image`

Returns the stored JPG bytes unchanged with the stored image content type and an attachment-safe filename.

### `GET /api/live-photo/{itemId}/video`

Returns the stored MP4 bytes unchanged with the stored video content type and an attachment-safe filename.

### `GET /gallery`

Returns an HTML gallery generated by the Python server. The page consumes `/api/live-photos` and uses the image/video endpoints.

Unknown item IDs return 404. Malformed IDs never become filesystem paths; lookup is performed against validated manifest directories.

## Browser Preview Behavior

Each gallery card represents one server item.

- Idle state shows the JPG.
- On pointer press/touch, the card switches to the MP4 and starts playback from the beginning.
- On pointer release/cancel, playback stops and the JPG becomes visible again.
- A normal click on a dedicated play control is available for desktop accessibility.
- Separate "download JPG" and "download MP4" links expose the original bytes.
- The page displays the Live Photo ID and upload timestamp for diagnostics.

This is a Live Photo-style web interaction, not a claim that the browser has native vivo Live Photo support.

The video element is muted by default for reliable inline autoplay on mobile browsers. Controls can be exposed when explicitly playing.

## Android Client Additions

The existing server URL input remains the single server configuration field.

The diagnostic UI gains:

- **Open web gallery** — launches `<baseUrl>/gallery` in the default browser.
- **Load server Live Photos** — calls `GET /api/live-photos`.
- A simple server-item selector showing timestamp, image filename, and shortened Live Photo ID.
- **Restore selected Live Photo** — enabled only after a valid item is selected.
- Restoration progress and validation diagnostics.
- **Open restored media** — enabled after a successful MediaStore write.

A simple selector is preferred over a new gallery UI inside the app because the purpose of the Android app is restoration validation, not media browsing.

## Android Download and Validation Flow

The Android app never writes network bytes directly into public MediaStore.

For the selected item:

1. Fetch item metadata.
2. Stream the image endpoint into an app-private temporary file.
3. Stream the video endpoint into a second app-private temporary file.
4. While/after downloading, compute SHA-256.
5. Parse the downloaded JPG for `com.android.camera.livephoto`.
6. Parse the downloaded MP4 for `com.android.camera.livephoto` and `vivoMediaExtInfo`.
7. Require all of the following before public restoration:
   - image SHA-256 equals manifest,
   - video SHA-256 equals manifest,
   - image ID equals manifest `livePhotoId`,
   - video ID equals manifest `livePhotoId`,
   - image ID equals video ID,
   - MP4 contains `vivoMediaExtInfo`.
8. Reject and delete temporary files on any mismatch.

The same `VivoMetadataScanner` logic used by the existing pairing flow should be reused where possible so upload and restore validation do not drift.

## Restore Naming

The restored image and video must share one basename.

The preferred basename is the original image basename when both manifest filenames already share it.

Before insertion, the app queries both `MediaStore.Images` and `MediaStore.Video` for collisions under `DCIM/Camera/`.

If either target name already exists, choose a paired suffix:

```text
<base>_restored_1.jpg
<base>_restored_1.mp4
```

Increment until **both** names are free. Never suffix only one half of the pair.

The file contents and embedded vivo metadata are not modified when the outer filenames change. The restore experiment therefore tests whether vivo's gallery relies on embedded pair metadata plus shared basename/location, not byte rewriting.

## MediaStore Restore Transaction

Android restoration uses public MediaStore APIs.

For each file:

- target collection: `MediaStore.Images` for JPG and `MediaStore.Video` for MP4,
- `RELATIVE_PATH = "DCIM/Camera/"`,
- `DISPLAY_NAME` uses the chosen paired filenames,
- appropriate MIME type is preserved,
- on Android 10+, create rows with `IS_PENDING = 1`.

Sequence:

1. Insert pending image row.
2. Copy validated temporary JPG into its output stream.
3. Insert pending video row.
4. Copy validated temporary MP4 into its output stream.
5. Re-open both MediaStore URIs and run a post-write metadata check.
6. Set `IS_PENDING = 0` on both rows only after both writes and checks succeed.
7. Delete temporary files.
8. Return both public content URIs.

If any insert, copy, or post-write validation fails, delete every MediaStore row created during that restore attempt and delete temporary files. The user should not be left with a half-restored pair.

For Android versions below 29, the project may keep its existing minimum compatibility behavior, but the X200s validation path targets modern scoped storage.

## Gallery Verification

After restore, the app reports:

- restored JPG display name and URI,
- restored MP4 display name and URI,
- post-write JPG Live Photo ID,
- post-write MP4 Live Photo ID,
- whether `vivoMediaExtInfo` survived,
- `RESTORE_VALIDATED = TRUE/FALSE`.

The **Open restored media** action sends an `ACTION_VIEW` intent for the restored image URI with read permission. Android may offer vivo Gallery or another capable media viewer.

The final vivo recognition result remains a human-observed test:

- dynamic-photo badge appears,
- opening the image offers vivo's dynamic-photo behavior,
- press/hold playback works.

The app must not report "vivo gallery restored successfully" solely because MediaStore writes succeeded.

## Failure Interpretation

The diagnostic output distinguishes these cases:

- **Server integrity failure** — hashes or IDs differ before MediaStore insertion.
- **MediaStore write failure** — public rows cannot be created or copied.
- **Post-write mutation/failure** — bytes/metadata no longer validate after insertion.
- **Public restore valid, vivo gallery static** — the strongest evidence that vivo needs additional private gallery/index database state or another vendor-specific registration step.
- **Public restore valid, vivo gallery dynamic** — proves that preserved file metadata plus public MediaStore restoration is sufficient on the tested X200s software version.

## Security and Diagnostic Constraints

This remains a LAN diagnostic tool.

- The debug app may continue to allow cleartext HTTP for local testing.
- The server keeps the existing upload size limit.
- Filenames are sanitized before storage.
- `itemId` values are treated as opaque identifiers and validated before lookup.
- No endpoint accepts arbitrary filesystem paths.
- The gallery escapes manifest-derived text before inserting it into HTML.
- The implementation must not add Internet-facing deployment guidance that implies the server is production secure.

## Testing Strategy

### Python server tests

Add tests for:

- successful upload manifest creation,
- failed verification does not create an indexed item,
- list ordering and manifest serialization,
- safe item lookup / invalid ID rejection,
- image endpoint returns exact bytes,
- video endpoint returns exact bytes,
- gallery route returns HTML without embedding raw media bytes,
- HTML escaping for user-derived filenames.

Keep existing chunked-transfer and pair-validation tests.

### Kotlin/JVM tests

Keep Android framework-independent policy in pure Kotlin where practical and test:

- server base URL normalization,
- parsing server list/manifest JSON,
- paired restore-name selection,
- collision suffix selection,
- restore eligibility requires all metadata/hash checks,
- mismatch blocks restore.

### Android integration behavior

CI can compile the MediaStore code but cannot prove vivo gallery recognition. The final acceptance test must be performed on the user's X200s.

## Acceptance Procedure on vivo X200s

1. Start the Python server on the laptop.
2. Install the new debug APK.
3. Upload an original Live Photo and confirm the server returns `success: true` plus an `itemId`.
4. Open `/gallery` in a browser and verify JPG idle + MP4 press/play behavior.
5. In the Android app, load server items and select the uploaded pair.
6. Restore it to `DCIM/Camera/`.
7. Confirm the app reports `RESTORE_VALIDATED = TRUE`.
8. Open the restored image in vivo Gallery.
9. Record whether vivo displays the dynamic-photo indicator and whether dynamic playback works.

To avoid confusing the restored pair with the original, the user may temporarily move or delete the original **manually after a verified server upload**, but the diagnostic app will not automate that destructive action.

## Success Criteria

The implementation phase is complete when:

- CI passes server tests and Android unit tests,
- a new debug APK artifact is produced,
- server web preview works against a real uploaded pair,
- Android restores a byte-validated same-basename pair through MediaStore without leaving partial files on failure, and
- the app exposes enough diagnostics to distinguish a successful public-media restore from vivo gallery recognition.

The research question is fully closed only after the X200s gallery test:

- **Recognized as dynamic:** public restore is sufficient for this tested vivo format/software version.
- **Not recognized as dynamic despite validated bytes:** proceed to a separate investigation of vivo-specific database/provider registration.
