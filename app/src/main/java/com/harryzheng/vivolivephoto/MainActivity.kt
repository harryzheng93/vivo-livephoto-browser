package com.harryzheng.vivolivephoto

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {
    private lateinit var resultText: TextView

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
        findViewById<Button>(R.id.selectButton).setOnClickListener {
            if (hasFullMediaAccess()) {
                resultText.text = permissionSummary() + "\n\n请选择一张 vivo Live Photo。"
                imagePicker.launch("image/*")
            } else {
                permissionLauncher.launch(requiredPermissions())
            }
        }

        resultText.text = permissionSummary() + "\n\n等待选择照片。"
    }

    private fun inspect(uri: Uri) {
        resultText.text = permissionSummary() + "\n\n正在解析 JPG 并查询 MediaStore 视频……"

        Thread {
            val text = try {
                val finder = MediaStorePairFinder(contentResolver)
                val image = finder.inspectSelectedImage(uri)
                val result = finder.findCompanionVideo(image)
                renderResult(result)
            } catch (e: Exception) {
                buildString {
                    appendLine(permissionSummary())
                    appendLine()
                    appendLine("ERROR")
                    appendLine(e::class.java.simpleName + ": " + (e.message ?: "(no message)"))
                    appendLine()
                    appendLine("如果错误与 MediaStore 权限有关，请在系统设置中给本应用完整的“照片和视频”访问权限后重试。")
                }
            }

            runOnUiThread { resultText.text = text }
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
