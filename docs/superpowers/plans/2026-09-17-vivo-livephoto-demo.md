# vivo Live Photo Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal Android APK that verifies vivo JPG/MP4 Live Photo pairing on a vivo X200s.

**Architecture:** A pure Kotlin scanner extracts vivo Live Photo IDs from byte streams. Android-specific code queries MediaStore for matching MP4 candidates. A single Activity handles permissions, image selection, and diagnostic rendering.

**Tech Stack:** Kotlin 1.9.24, Android Gradle Plugin 8.7.3, Gradle 8.9, JDK 17, Android SDK 35, JUnit 4, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-17-vivo-livephoto-demo-design.md`

## Global Constraints
- minSdk 26.
- targetSdk/compileSdk 35.
- No network permission or backend.
- Match is true only when JPG and MP4 vivo Live Photo IDs are equal.
- GitHub Actions must run tests and upload a debug APK artifact.

---

### Task 1: Pure vivo metadata scanner

**Files:**
- Create: `app/src/test/java/com/harryzheng/vivolivephoto/VivoMetadataScannerTest.kt`
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/VivoMetadataScanner.kt`

**Interfaces:**
- Produces: `VivoMetadataScanner.findLivePhotoId(InputStream): String?`
- Produces: `VivoMetadataScanner.containsVivoMediaExtInfo(InputStream): Boolean`

- [ ] Write tests for a valid 28-character ID, invalid ID, ID split across chunks, and `vivoMediaExtInfo` detection.
- [ ] Run tests and confirm RED because scanner is missing.
- [ ] Implement a streaming scanner with overlap between chunks.
- [ ] Run tests and confirm GREEN.

### Task 2: Android project and MediaStore pairing

**Files:**
- Create: `settings.gradle.kts`
- Create: `build.gradle.kts`
- Create: `app/build.gradle.kts`
- Create: `app/proguard-rules.pro`
- Create: `app/src/main/AndroidManifest.xml`
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/MediaStorePairFinder.kt`

**Interfaces:**
- Produces: `SelectedImageInfo`
- Produces: `PairSearchResult`
- Produces: `MediaStorePairFinder.inspectSelectedImage(Uri): SelectedImageInfo`
- Produces: `MediaStorePairFinder.findCompanionVideo(SelectedImageInfo): PairSearchResult`

- [ ] Configure Android/JUnit dependencies.
- [ ] Implement MediaStore metadata lookup and exact basename/path video query.
- [ ] Add same-directory time-nearby candidates for diagnostics.
- [ ] Scan candidates with `VivoMetadataScanner` and require equal IDs for a confirmed match.

### Task 3: Minimal diagnostic UI

**Files:**
- Create: `app/src/main/res/layout/activity_main.xml`
- Create: `app/src/main/res/values/strings.xml`
- Create: `app/src/main/res/values/themes.xml`
- Create: `app/src/main/java/com/harryzheng/vivolivephoto/MainActivity.kt`

**Interfaces:**
- User action: request full image/video media access, then select one image.
- Output: readable diagnostics including JPG name/path/ID, candidate MP4s, MP4 ID, and `MATCH = TRUE/FALSE`.

- [ ] Add Android 13+ image/video permissions and Android 14 selected-media declaration.
- [ ] Add image picker and runtime permission flow.
- [ ] Run MediaStore pairing off the main thread.
- [ ] Render success/failure and permission diagnostics.

### Task 4: Cloud build and documentation

**Files:**
- Create: `.github/workflows/android.yml`
- Modify: `README.md`

- [ ] Configure Actions with JDK 17, Gradle 8.9, Android SDK packages, unit tests, and debug APK build.
- [ ] Upload `app/build/outputs/apk/debug/app-debug.apk` as `vivo-livephoto-test-apk`.
- [ ] Document install/test steps and expected diagnostic output.
- [ ] Verify the workflow result and APK artifact before claiming completion.
