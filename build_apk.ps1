$env:PYTHONIOENCODING = "utf-8"
$env:FLET_CLI_NO_RICH_OUTPUT = "1"
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

# Flet 0.85 can reuse a stale packaged Python app. Keep the existing dependency
# bundle, but force-refresh project source files inside app/app.zip before build.
$fletAppCache = Join-Path $PSScriptRoot "build\flutter\app"
$fletAppZip = Join-Path $fletAppCache "app.zip"
$fletAppZipHash = "$fletAppZip.hash"
$fallbackAppZip = Join-Path $PSScriptRoot "build\flutter\build\app\intermediates\assets\release\mergeReleaseAssets\flutter_assets\app\app.zip"

if (!(Test-Path $fletAppZip) -and (Test-Path $fallbackAppZip)) {
    New-Item -ItemType Directory -Path $fletAppCache -Force | Out-Null
    Copy-Item -LiteralPath $fallbackAppZip -Destination $fletAppZip -Force
}

if (Test-Path $fletAppZip) {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $sourceFiles = @()
    $sourceFiles += Get-Item -LiteralPath (Join-Path $PSScriptRoot "main.py") -ErrorAction SilentlyContinue
    $sourceFiles += Get-ChildItem -Path (Join-Path $PSScriptRoot "utils") -Filter "*.py" -File -ErrorAction SilentlyContinue
    $sourceFiles += Get-ChildItem -Path (Join-Path $PSScriptRoot "components") -Filter "*.py" -File -ErrorAction SilentlyContinue

    $zip = [System.IO.Compression.ZipFile]::Open($fletAppZip, [System.IO.Compression.ZipArchiveMode]::Update)
    try {
        $staleEntries = @(
            "__pycache__/",
            "utils/__pycache__/",
            "components/__pycache__/"
        )
        $entriesToDelete = @($zip.Entries | Where-Object {
            $entryName = $_.FullName
            $staleEntries | Where-Object { $entryName.StartsWith($_) }
        })
        foreach ($entry in $entriesToDelete) {
            $entry.Delete()
        }

        foreach ($file in $sourceFiles) {
            if ($null -eq $file) {
                continue
            }
            $rootPath = $PSScriptRoot.TrimEnd("\") + "\"
            $relative = $file.FullName.Substring($rootPath.Length).Replace("\", "/")
            $existing = @($zip.Entries | Where-Object { $_.FullName -eq $relative })
            foreach ($entry in $existing) {
                $entry.Delete()
            }
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $relative) | Out-Null
        }
    }
    finally {
        $zip.Dispose()
    }

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $fletAppZip).Hash.ToLowerInvariant()
    Set-Content -Path $fletAppZipHash -Value $hash -NoNewline
}

flet build apk
