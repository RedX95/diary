$env:PYTHONIOENCODING = "utf-8"
$env:PUB_HOSTED_URL = "https://pub.flutter-io.cn"
$env:FLUTTER_STORAGE_BASE_URL = "https://storage.flutter-io.cn"

$androidStudioJbr = "C:\Program Files\Android\Android Studio\jbr"
if (Test-Path (Join-Path $androidStudioJbr "bin\java.exe")) {
    $env:JAVA_HOME = $androidStudioJbr
    $env:PATH = "$androidStudioJbr\bin;$env:PATH"
}

# Work around a broken screen_brightness_android release that references
# an AGP version not published to Google's Maven repository.
$screenBrightnessGradle = Join-Path $env:LOCALAPPDATA "Pub\Cache\hosted\pub.flutter-io.cn\screen_brightness_android-2.1.4\android\build.gradle"
if (Test-Path $screenBrightnessGradle) {
    $content = Get-Content $screenBrightnessGradle -Raw
    $content = $content.Replace("com.android.tools.build:gradle:8.13.2", "com.android.tools.build:gradle:8.12.1")
    $content = $content.Replace("org.jetbrains.kotlin:kotlin-gradle-plugin:2.3.21", "org.jetbrains.kotlin:kotlin-gradle-plugin:2.2.20")
    $content = $content.Replace('kotlin-stdlib-jdk7:2.3.21', 'kotlin-stdlib-jdk7:2.2.20')
    Set-Content -Path $screenBrightnessGradle -Value $content
}

# screen_brightness_android 2.1.4 ships a plugin class that is not emitted into
# the release jar in this toolchain. Replace it with a minimal no-op plugin so
# GeneratedPluginRegistrant can compile. This app does not use screen brightness APIs.
$screenBrightnessPlugin = Join-Path $env:LOCALAPPDATA "Pub\Cache\hosted\pub.flutter-io.cn\screen_brightness_android-2.1.4\android\src\main\kotlin\com\aaassseee\screen_brightness_android\ScreenBrightnessAndroidPlugin.kt"
if (Test-Path $screenBrightnessPlugin) {
    @'
package com.aaassseee.screen_brightness_android

import io.flutter.embedding.engine.plugins.FlutterPlugin
import io.flutter.embedding.engine.plugins.activity.ActivityAware
import io.flutter.embedding.engine.plugins.activity.ActivityPluginBinding

class ScreenBrightnessAndroidPlugin : FlutterPlugin, ActivityAware {
    override fun onAttachedToEngine(binding: FlutterPlugin.FlutterPluginBinding) {}
    override fun onDetachedFromEngine(binding: FlutterPlugin.FlutterPluginBinding) {}
    override fun onAttachedToActivity(binding: ActivityPluginBinding) {}
    override fun onDetachedFromActivityForConfigChanges() {}
    override fun onReattachedToActivityForConfigChanges(binding: ActivityPluginBinding) {}
    override fun onDetachedFromActivity() {}
}
'@ | Set-Content -Path $screenBrightnessPlugin
}

# Flutter 3.41.x still needs the legacy DSL flags for plugin compatibility.
$androidGradleProperties = Join-Path $PSScriptRoot "build\flutter\android\gradle.properties"
if (Test-Path $androidGradleProperties) {
    $gradleProps = Get-Content $androidGradleProperties -Raw
    if ($gradleProps -notmatch "(?m)^android\.newDsl=") {
        $gradleProps = $gradleProps.TrimEnd() + "`r`nandroid.newDsl=false"
    }
    if ($gradleProps -notmatch "(?m)^android\.builtInKotlin=") {
        $gradleProps = $gradleProps.TrimEnd() + "`r`nandroid.builtInKotlin=false"
    }
    Set-Content -Path $androidGradleProperties -Value $gradleProps
}

flet build apk
