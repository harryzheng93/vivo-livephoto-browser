package com.harryzheng.vivolivephoto

object UploadEndpoint {
    private const val API_PATH = "/api/live-photo"

    fun fromUserInput(input: String): String {
        val trimmed = input.trim().trimEnd('/')
        require(trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            "服务器地址必须以 http:// 或 https:// 开头"
        }
        return if (trimmed.endsWith(API_PATH)) trimmed else trimmed + API_PATH
    }
}
