package com.harryzheng.vivolivephoto

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {
    private lateinit var resultText: TextView
    private lateinit var serverUrlInput: EditText
    private lateinit var uploadButton: Button
    private var lastPairResult: PairSearchResult? = null

    private val imagePicker = registerForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        if (uri != null) inspect(uri)
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        resultText.text = permissionSummary() + "\n\n请选择一张 vivo Live Photo。"
        imagePicker.launch("image/*")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        resultText = findViewById(R.id.resultText)
        serverUrlInput = findViewById(R.id.serverUrlInput)
        uploadButton = findViewById(R.id.uploadButton)

        findViewById<Button>(R.id.selectButton).setOnClickListener {
            clearCurrentPair()
            if (hasFullMediaAccess()) {
                resultText.text = permissionSummary() + "\n\n请选择一张 vivo Live Photo。"
                imagePicker.launch("image/*")
            } else {
                permissionLauncher.launch(requiredPermissions())
            }
        }

        uploadButton.setOnClickListener { uploadCurrentPair() }
        resultText.text = permissionSummary() + "\n\n等待选择照片。"
    }

    private fun clearCurrentPair() {
        lastPairResult = null
        uploadButton.isEnabled = false
    }

    private fun inspect(uri: Uri) {
        clearCurrentPair()
        resultText.text = permissionSummary() + "\n\n正在解析 JPG 并查询 MediaStore 视频……"

        Thread {
            try {
                val finder = MediaStorePairFinder(contentResolver)
                val image = finder.inspectSelectedImage(uri)
                val result = finder.findCompanionVideo(image)

                runOnUiThread {
                    lastPairResult = result
                    uploadButton.isEnabled = result.matched != null
                    resultText.text = renderResult(result)
                }
            } catch (e: Exception) {
                val text = buildString {
                    appendLine(permissionSummary())
                    appendLine()
                    appendLine("ERROR")
                    appendLine(e::class.java.simpleName + ": " + (e.message ?: "(no message)"))
                    appendLine()
                    appendLine("如果错误与 MediaStore 权限有关，请在系统设置中给本应用完整的“照片和视频”访问权限后重试。")
                }
                runOnUiThread {
                    clearCurrentPair()
                    resultText.text = text
                }
            }
        }.start()
    }

    private fun uploadCurrentPair() {
        val result = lastPairResult
        val matched = result?.matched
        if (result == null || matched == null) {
            resultText.append("\n\nUPLOAD ERROR\n没有已验证的 JPG + MP4 配对。")
            uploadButton.isEnabled = false
            return
        }

        val plan = try {
            LivePhotoUploadPlan.create(
                serverInput = serverUrlInput.text.toString(),
                imageName = result.image.displayName,
                videoName = matched.displayName,
                imageLivePhotoId = result.image.livePhotoId,
                videoLivePhotoId = matched.livePhotoId
            )
        } catch (e: IllegalArgumentException) {
            resultText.append("\n\nUPLOAD ERROR\n${e.message ?: "上传参数无效"}")
            return
        }

        uploadButton.isEnabled = false
        resultText.append(
            "\n\nUPLOAD\n------\nendpoint: ${plan.endpoint}\n" +
                "正在原样流式上传 JPG + MP4……"
        )

        Thread {
            try {
                val response = contentResolver.openInputStream(result.image.uri).use { imageInput ->
                    requireNotNull(imageInput) { "无法打开 JPG 输入流" }
                    contentResolver.openInputStream(matched.uri).use { videoInput ->
                        requireNotNull(videoInput) { "无法打开 MP4 输入流" }
                        LivePhotoUploader().upload(
                            plan = plan,
                            imageInput = imageInput,
                            videoInput = videoInput,
                            imageContentType = contentResolver.getType(result.image.uri) ?: "image/jpeg",
                            videoContentType = contentResolver.getType(matched.uri) ?: "video/mp4"
                        )
                    }
                }

                runOnUiThread {
                    resultText.append(
                        "\n\nUPLOAD RESULT\n-------------\n" +
                            "HTTP ${response.statusCode}\n${response.body}"
                    )
                    uploadButton.isEnabled = lastPairResult?.matched != null
                }
            } catch (e: Exception) {
                runOnUiThread {
                    resultText.append(
                        "\n\nUPLOAD ERROR\n" +
                            e::class.java.simpleName + ": " + (e.message ?: "(no message)")
                    )
                    uploadButton.isEnabled = lastPairResult?.matched != null
                }
            }
        }.start()
    }

    private fun renderResult(result: PairSearchResult): String = buildString {
        appendLine(permissionSummary())
        appendLine()
        appendLine("JPG")
        appendLine("---")
        appendLine("name: ${result.image.displayName}")
        appendLine("path: ${result.image.relativePath ?: "(picker 未暴露)"}")
        appendLine("size: ${result.image.size ?: -1}")
        appendLine("dateTaken: ${result.image.dateTaken ?: -1}")
        appendLine("livePhotoId: ${result.image.livePhotoId ?: "NOT FOUND"}")
        appendLine()

        appendCandidates("同名 MP4 候选", result.exactCandidates)
        appendLine()
        appendCandidates("附近时间 MP4 候选", result.nearbyCandidates)
        appendLine()

        val matched = result.matched
        if (matched != null) {
            appendLine("MATCH = TRUE")
            appendLine("MP4: ${matched.displayName}")
            appendLine("MP4 path: ${matched.relativePath ?: "(unknown)"}")
            appendLine("MP4 livePhotoId: ${matched.livePhotoId}")
            appendLine("vivoMediaExtInfo: ${matched.hasVivoMediaExtInfo}")
            appendLine()
            appendLine("已启用“上传完整 Live Photo”。输入电脑测试服务器地址后即可验证端到端传输。")
        } else {
            appendLine("MATCH = FALSE")
            when {
                result.image.livePhotoId == null -> appendLine("原因优先检查：JPG 中没有解析到 com.android.camera.livephoto。")
                !hasVideoPermission() -> appendLine("原因优先检查：没有完整视频媒体权限，关联 MP4 可能对应用不可见。")
                result.exactCandidates.isEmpty() && result.nearbyCandidates.isEmpty() -> appendLine("MediaStore 中没有找到同名或附近时间的视频。")
                else -> appendLine("找到了视频候选，但其 vivo Live Photo ID 与 JPG 不一致或无法解析。")
            }
        }
    }

    private fun StringBuilder.appendCandidates(title: String, candidates: List<VideoCandidate>) {
        appendLine(title)
        appendLine("---")
        if (candidates.isEmpty()) {
            appendLine("(none)")
            return
        }
        candidates.forEachIndexed { index, item ->
            appendLine("[${index + 1}] ${item.displayName}")
            appendLine("    path=${item.relativePath ?: "(unknown)"}")
            appendLine("    size=${item.size ?: -1}")
            appendLine("    dateTaken=${item.dateTaken ?: -1}")
            appendLine("    vivoMediaExtInfo=${item.hasVivoMediaExtInfo}")
            appendLine("    livePhotoId=${item.livePhotoId ?: "NOT FOUND"}")
        }
    }

    private fun permissionSummary(): String = buildString {
        appendLine("PERMISSIONS")
        appendLine("-----------")
        if (Build.VERSION.SDK_INT >= 33) {
            appendLine("READ_MEDIA_IMAGES=${isGranted(Manifest.permission.READ_MEDIA_IMAGES)}")
            appendLine("READ_MEDIA_VIDEO=${isGranted(Manifest.permission.READ_MEDIA_VIDEO)}")
            if (Build.VERSION.SDK_INT >= 34) {
                appendLine("READ_MEDIA_VISUAL_USER_SELECTED=${isGranted(Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED)}")
            }
        } else {
            appendLine("READ_EXTERNAL_STORAGE=${isGranted(Manifest.permission.READ_EXTERNAL_STORAGE)}")
        }
        append("fullMediaAccess=${hasFullMediaAccess()}")
    }

    private fun hasFullMediaAccess(): Boolean = if (Build.VERSION.SDK_INT >= 33) {
        isGranted(Manifest.permission.READ_MEDIA_IMAGES) && isGranted(Manifest.permission.READ_MEDIA_VIDEO)
    } else {
        isGranted(Manifest.permission.READ_EXTERNAL_STORAGE)
    }

    private fun hasVideoPermission(): Boolean = if (Build.VERSION.SDK_INT >= 33) {
        isGranted(Manifest.permission.READ_MEDIA_VIDEO)
    } else {
        isGranted(Manifest.permission.READ_EXTERNAL_STORAGE)
    }

    private fun isGranted(permission: String): Boolean =
        ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED

    private fun requiredPermissions(): Array<String> = when {
        Build.VERSION.SDK_INT >= 34 -> arrayOf(
            Manifest.permission.READ_MEDIA_IMAGES,
            Manifest.permission.READ_MEDIA_VIDEO,
            Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED
        )
        Build.VERSION.SDK_INT >= 33 -> arrayOf(
            Manifest.permission.READ_MEDIA_IMAGES,
            Manifest.permission.READ_MEDIA_VIDEO
        )
        else -> arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE)
    }
}
