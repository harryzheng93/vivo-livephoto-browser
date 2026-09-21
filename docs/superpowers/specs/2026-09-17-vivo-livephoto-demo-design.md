# vivo Live Photo Demo Design

## Goal
Build a minimal Android app that runs on the user's vivo X200s and verifies whether a selected vivo Live Photo can be paired with its companion MP4 through Android MediaStore.

## Scope
- Kotlin Android app, classic Views only.
- Android 13+ media permissions, with Android 14+ partial-access detection.
- User selects an image from the system gallery.
- App scans the selected JPEG for `com.android.camera.livephoto` and extracts the 28-character vivo Live Photo ID.
- App queries `MediaStore.Video` for the same basename and directory, then scans candidate MP4 files for `vivoMediaExtInfo` and the same Live Photo ID.
- UI prints image metadata, image ID, candidate videos, video ID, and final match status.
- No upload, no backend, no account, no network access.
- GitHub Actions builds and unit-tests the app and publishes a debug APK artifact.

## Non-goals
- Pixel/Samsung Motion Photo support.
- vivo X300+ single-file Motion Photo support.
- Production-grade gallery UI.
- Editing or converting Live Photos.

## Architecture
`MainActivity` owns permission flow, launches the gallery picker, and renders diagnostics. `MediaStorePairFinder` reads MediaStore metadata and finds candidate videos. `VivoMetadataScanner` is a pure Kotlin streaming scanner that detects vivo markers and extracts the Live Photo ID without loading large videos fully into memory.

## Permission behavior
On Android 13+, request `READ_MEDIA_IMAGES` and `READ_MEDIA_VIDEO`. On Android 14+, declare `READ_MEDIA_VISUAL_USER_SELECTED` so the app can detect selected-only access. The demo should tell the user when full media access is not granted because the companion video may otherwise be invisible.

## Matching strategy
1. Read the selected image's display name, relative path, date taken, and size.
2. Scan the JPEG for `com.android.camera.livephoto` and capture the 28-character ID.
3. Query videos with the same basename in the same relative path.
4. Scan each candidate for `vivoMediaExtInfo` and `com.android.camera.livephoto`.
5. A pair is confirmed only when the image and video IDs are identical.
6. If exact-name lookup fails, query nearby videos in the same directory by capture time to provide diagnostics.

## Build
Use Android Gradle Plugin 8.7.3, Gradle 8.9, Kotlin 1.9.24, JDK 17, compile/target SDK 35, min SDK 26. GitHub Actions installs the Android SDK, runs unit tests, assembles `app-debug.apk`, and uploads it as an artifact.

## Success criteria
On the vivo X200s, selecting an original Live Photo produces either:
- `MATCH = TRUE` with the same 28-character ID from JPG and MP4; or
- enough diagnostics to show exactly whether permission, filename/path matching, or vivo metadata discovery failed.
