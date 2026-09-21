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

object RestoreDiagnostics {
    fun format(result: RestoreResult): String = buildString {
        appendLine("RESTORE_VALIDATED = TRUE")
        appendLine("image name: ${result.names.imageName}")
        appendLine("image uri: ${result.image.uri}")
        appendLine("image livePhotoId: ${result.imagePostWrite.livePhotoId}")
        appendLine("video name: ${result.names.videoName}")
        appendLine("video uri: ${result.video.uri}")
        appendLine("video livePhotoId: ${result.videoPostWrite.livePhotoId}")
        appendLine("vivoMediaExtInfo: ${result.videoPostWrite.hasVivoMediaExtInfo}")
        append("请在 vivo 相册中检查动态照片标识和按住播放；以上只证明公开 MediaStore 恢复后的字节与元数据校验通过。")
    }
}
