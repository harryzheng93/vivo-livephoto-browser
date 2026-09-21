package com.harryzheng.vivolivephoto

enum class MediaKind { IMAGE, VIDEO }

data class RestoreNames(val imageName: String, val videoName: String)

object RestoreNamePlanner {
    fun choose(
        imageFilename: String,
        videoFilename: String,
        exists: (MediaKind, String) -> Boolean,
    ): RestoreNames {
        require(imageFilename.isNotBlank() && videoFilename.isNotBlank()) { "Media filenames are required" }
        val imageStem = imageFilename.substringBeforeLast('.', imageFilename)
        var suffix = 0
        while (true) {
            val targetStem = if (suffix == 0) imageStem else "${imageStem}_restored_$suffix"
            val names = RestoreNames("$targetStem.jpg", "$targetStem.mp4")
            if (!exists(MediaKind.IMAGE, names.imageName) &&
                !exists(MediaKind.VIDEO, names.videoName)
            ) return names
            suffix++
        }
    }
}

data class PostWriteMedia(
    val sha256: String,
    val livePhotoId: String?,
    val hasVivoMediaExtInfo: Boolean,
)

object RestoreValidation {
    fun requirePostWriteMatch(
        verified: VerifiedLivePhotoDownload,
        image: PostWriteMedia,
        video: PostWriteMedia,
    ) {
        val manifest = verified.manifest
        require(image.sha256 == manifest.imageSha256) { "Restored image SHA-256 mismatch" }
        require(video.sha256 == manifest.videoSha256) { "Restored video SHA-256 mismatch" }
        require(image.livePhotoId == manifest.livePhotoId) { "Restored image ID mismatch" }
        require(video.livePhotoId == manifest.livePhotoId) { "Restored video ID mismatch" }
        require(image.livePhotoId == video.livePhotoId) { "Restored IDs do not match" }
        require(video.hasVivoMediaExtInfo) { "Restored MP4 missing vivoMediaExtInfo" }
    }
}
