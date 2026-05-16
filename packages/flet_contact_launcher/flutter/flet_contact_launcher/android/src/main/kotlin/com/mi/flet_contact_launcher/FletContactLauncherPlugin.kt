package com.mi.flet_contact_launcher

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.ContactsContract
import io.flutter.embedding.engine.plugins.FlutterPlugin
import io.flutter.embedding.engine.plugins.activity.ActivityAware
import io.flutter.embedding.engine.plugins.activity.ActivityPluginBinding
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.PluginRegistry
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class FletContactLauncherPlugin : FlutterPlugin, MethodChannel.MethodCallHandler,
    ActivityAware, PluginRegistry.RequestPermissionsResultListener {

    private lateinit var channel: MethodChannel
    private lateinit var appContext: Context
    private val mainHandler = Handler(Looper.getMainLooper())
    private var activity: Activity? = null
    private var pendingPhone: String? = null
    private var pendingResult: MethodChannel.Result? = null
    private var lastLaunchFailure: String? = null

    override fun onAttachedToEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        appContext = binding.applicationContext
        channel = MethodChannel(binding.binaryMessenger, "flet_contact_launcher/native")
        channel.setMethodCallHandler(this)
    }

    override fun onDetachedFromEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        channel.setMethodCallHandler(null)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "openContact" -> {
                val phone = call.argument<String>("phone").orEmpty().trim()
                if (phone.isEmpty()) {
                    result.success("error:empty phone")
                    return
                }
                handleOpenContact(phone, result)
            }
            else -> result.notImplemented()
        }
    }

    private fun handleOpenContact(phone: String, result: MethodChannel.Result) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M &&
            appContext.checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED
        ) {
            val currentActivity = activity
            if (currentActivity == null) {
                result.success("permission_denied:no_activity_for_request")
                return
            }
            pendingPhone = phone
            pendingResult = result
            currentActivity.requestPermissions(
                arrayOf(Manifest.permission.READ_CONTACTS),
                REQUEST_READ_CONTACTS
            )
            return
        }
        openContactAsync(phone, result)
    }

    private fun openContactAsync(phone: String, result: MethodChannel.Result) {
        Thread {
            val status = launchContact(phone)
            mainHandler.post { result.success(status) }
        }.start()
    }

    private fun launchContact(phone: String): String {
        lastLaunchFailure = null

        val contact = findContact(phone)
        if (contact != null && launchByContactRef(contact)) {
            return "opened_contact"
        }

        if (launchContactsSearch(phone)) {
            return "opened_search"
        }

        return when {
            contact == null -> "not_found"
            lastLaunchFailure != null -> "launch_failed:$lastLaunchFailure"
            else -> "launch_failed"
        }
    }

    private fun launchByContactRef(contact: ContactRef): Boolean {
        val lookupUri = ContactsContract.Contacts.getLookupUri(contact.id, contact.lookupKey)
            ?: return false
        val packages = listOf(
            "com.samsung.android.app.contacts",
            "com.google.android.contacts",
            "com.android.contacts",
        )

        for (packageName in packages) {
            val intent = Intent(Intent.ACTION_VIEW, lookupUri)
            intent.setPackage(packageName)
            if (startIfResolvable(intent)) {
                return true
            }
        }

        val genericIntent = Intent(Intent.ACTION_VIEW, lookupUri)
        val contactPackage = findContactPackage(genericIntent)
        if (contactPackage != null) {
            genericIntent.setPackage(contactPackage)
            return startIfResolvable(genericIntent)
        }
        return false
    }

    private fun launchContactsSearch(phone: String): Boolean {
        val packages = listOf(
            "com.samsung.android.app.contacts",
            "com.google.android.contacts",
            "com.android.contacts",
        )
        for (packageName in packages) {
            val intent = Intent("com.android.contacts.action.FILTER_CONTACTS")
            intent.setPackage(packageName)
            intent.putExtra("com.android.contacts.extra.FILTER_TEXT", phone)
            if (startIfResolvable(intent)) {
                return true
            }
        }

        for (packageName in packages) {
            val launchIntent = appContext.packageManager.getLaunchIntentForPackage(packageName) ?: continue
            launchIntent.putExtra("query", phone)
            if (startIfResolvable(launchIntent)) {
                return true
            }
        }

        return false
    }

    private fun startIfResolvable(intent: Intent): Boolean {
        val packageManager = appContext.packageManager
        val packageName = intent.`package`
        if (packageName != null && !isPackageInstalled(packageName)) {
            lastLaunchFailure = "package_not_installed:$packageName"
            return false
        }
        if (packageName == null && intent.resolveActivity(packageManager) == null) {
            lastLaunchFailure = "no_activity"
            return false
        }

        val launchIntent = Intent(intent)
        if (activity == null) {
            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        val launched = AtomicBoolean(false)
        val latch = CountDownLatch(1)
        mainHandler.post {
            try {
                (activity ?: appContext).startActivity(launchIntent)
                launched.set(true)
                lastLaunchFailure = null
            } catch (e: Exception) {
                lastLaunchFailure = "${e.javaClass.simpleName}:${e.message ?: "start_failed"}"
            } finally {
                latch.countDown()
            }
        }
        latch.await(1500, TimeUnit.MILLISECONDS)
        if (!launched.get() && lastLaunchFailure == null) {
            lastLaunchFailure = "start_timeout"
        }
        return launched.get()
    }

    private fun isPackageInstalled(packageName: String): Boolean {
        return try {
            appContext.packageManager.getPackageInfo(packageName, 0)
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun findContactPackage(intent: Intent): String? {
        val packageManager = appContext.packageManager
        return packageManager.queryIntentActivities(intent, 0)
            .mapNotNull { it.activityInfo?.packageName }
            .firstOrNull { it.contains("contact", ignoreCase = true) }
    }

    private fun findContact(phone: String): ContactRef? {
        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
            ContactsContract.CommonDataKinds.Phone.LOOKUP_KEY,
            ContactsContract.CommonDataKinds.Phone.NORMALIZED_NUMBER,
            ContactsContract.CommonDataKinds.Phone.NUMBER,
        )

        val normalizedTargets = buildPhoneCandidates(phone)
            .map { candidate -> candidate.filter { it.isDigit() } }
            .filter { it.isNotEmpty() }
            .toSet()

        val numberTargets = buildPhoneCandidates(phone).toSet()

        val selectionParts = mutableListOf<String>()
        val args = mutableListOf<String>()

        if (normalizedTargets.isNotEmpty()) {
            val placeholders = normalizedTargets.joinToString(",") { "?" }
            selectionParts += "${ContactsContract.CommonDataKinds.Phone.NORMALIZED_NUMBER} IN ($placeholders)"
            args += normalizedTargets
        }
        if (numberTargets.isNotEmpty()) {
            val placeholders = numberTargets.joinToString(",") { "?" }
            selectionParts += "${ContactsContract.CommonDataKinds.Phone.NUMBER} IN ($placeholders)"
            args += numberTargets
        }

        val selection = selectionParts.joinToString(" OR ")

        appContext.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            projection,
            selection.ifEmpty { null },
            args.toTypedArray().takeIf { args.isNotEmpty() },
            null
        )?.use { cursor ->
            while (cursor.moveToNext()) {
                val id = cursor.getLong(0)
                val lookupKey = cursor.getString(1) ?: ""
                val normalizedNumber = (cursor.getString(2) ?: "").filter { it.isDigit() }
                val rawNumber = cursor.getString(3) ?: ""
                val rawDigits = rawNumber.filter { it.isDigit() }

                if (lookupKey.isNotEmpty() && (
                    normalizedNumber in normalizedTargets ||
                    rawNumber in numberTargets ||
                    rawDigits in normalizedTargets
                )) {
                    return ContactRef(id, lookupKey)
                }
            }
        }

        if (normalizedTargets.isNotEmpty()) {
            appContext.contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                projection,
                null,
                null,
                null
            )?.use { cursor ->
                while (cursor.moveToNext()) {
                    val id = cursor.getLong(0)
                    val lookupKey = cursor.getString(1) ?: ""
                    val normalizedNumber = (cursor.getString(2) ?: "").filter { it.isDigit() }
                    val rawDigits = (cursor.getString(3) ?: "").filter { it.isDigit() }
                    val tail10 = rawDigits.takeLast(10)
                    if (lookupKey.isNotEmpty() && (
                        normalizedNumber in normalizedTargets ||
                        rawDigits in normalizedTargets ||
                        normalizedTargets.any { it.takeLast(10) == tail10 && tail10.isNotEmpty() }
                    )) {
                        return ContactRef(id, lookupKey)
                    }
                }
            }
        }
        return null
    }

    private fun buildPhoneCandidates(phone: String): List<String> {
        val trimmed = phone.trim()
        val digits = trimmed.filter { it.isDigit() }
        val variants = linkedSetOf<String>()

        if (trimmed.isNotEmpty()) {
            variants.add(trimmed)
        }
        if (digits.isNotEmpty()) {
            variants.add(digits)
        }
        if (digits.length == 11 && digits.startsWith("8")) {
            variants.add("+7" + digits.substring(1))
            variants.add("7" + digits.substring(1))
        }
        if (digits.length == 11 && digits.startsWith("7")) {
            variants.add("+$digits")
            variants.add("8" + digits.substring(1))
        }
        if (trimmed.startsWith("+7") && digits.length == 11) {
            variants.add("8" + digits.substring(1))
            variants.add(digits)
        }
        return variants.toList()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ): Boolean {
        if (requestCode != REQUEST_READ_CONTACTS) {
            return false
        }

        val phone = pendingPhone
        val result = pendingResult
        pendingPhone = null
        pendingResult = null

        if (result == null) {
            return true
        }

        if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED && phone != null) {
            openContactAsync(phone, result)
        } else {
            result.success("permission_denied")
        }
        return true
    }

    override fun onAttachedToActivity(binding: ActivityPluginBinding) {
        activity = binding.activity
        binding.addRequestPermissionsResultListener(this)
    }

    override fun onDetachedFromActivityForConfigChanges() {
        activity = null
    }

    override fun onReattachedToActivityForConfigChanges(binding: ActivityPluginBinding) {
        activity = binding.activity
        binding.addRequestPermissionsResultListener(this)
    }

    override fun onDetachedFromActivity() {
        activity = null
    }

    companion object {
        private const val REQUEST_READ_CONTACTS = 7924
    }

    private data class ContactRef(val id: Long, val lookupKey: String)
}
