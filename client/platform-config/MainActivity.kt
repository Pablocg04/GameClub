package com.gameclub.gameclub

import android.app.UiModeManager
import android.content.Context
import android.content.Intent
import android.content.ActivityNotFoundException
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.hardware.input.InputManager
import android.os.Handler
import android.os.Looper
import android.os.Build
import android.webkit.WebView
import android.provider.Settings
import android.view.InputDevice
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.WindowManager
import android.view.View
import android.view.ViewGroup
import io.flutter.embedding.android.FlutterView
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import kotlin.math.abs

class MainActivity : FlutterActivity(), InputManager.InputDeviceListener {
    private var sink: EventChannel.EventSink? = null
    private var sinkOwner: String? = null
    private var playerActive = false
    private var playerOwner: String? = null
    private var nativeResult: MethodChannel.Result? = null
    private var deviceChannel: MethodChannel? = null
    private val handler = Handler(Looper.getMainLooper())
    private val buttons = mutableMapOf<Int, MutableSet<Int>>()
    private val gameKeys = mutableSetOf<Pair<Int, Int>>()
    private val uiKeys = mutableSetOf<Pair<Int, Int>>()
    private var navigationKey = 0
    private val repeatNavigation = object : Runnable {
        override fun run() {
            if (navigationKey == 0 || playerActive) return
            sendNavigation(navigationKey)
            handler.postDelayed(this, 180)
        }
    }

    private fun isTelevision(): Boolean = BuildConfig.GAMECLUB_DEVICE == "tv"

    private fun isGamepad(source: Int): Boolean =
        source and InputDevice.SOURCE_GAMEPAD == InputDevice.SOURCE_GAMEPAD ||
            source and InputDevice.SOURCE_JOYSTICK == InputDevice.SOURCE_JOYSTICK

    private fun hasGamepad(): Boolean = InputDevice.getDeviceIds().any { isGamepad(InputDevice.getDevice(it)?.sources ?: 0) }

    private fun configurePlaybackDisplay(fast: Boolean) {
        val screen = if (Build.VERSION.SDK_INT >= 30) display else windowManager.defaultDisplay
        val attributes = window.attributes
        attributes.preferredRefreshRate = if (fast) 60f else 0f
        val modes = screen?.supportedModes?.filter { it.refreshRate in 59f..61f } ?: emptyList()
        val light = modes.filter { it.physicalWidth <= 1920 && it.physicalHeight <= 1080 }
        val selected = light.maxByOrNull { it.physicalWidth * it.physicalHeight }
            ?: modes.firstOrNull { it.physicalWidth == screen?.mode?.physicalWidth && it.physicalHeight == screen?.mode?.physicalHeight }
        attributes.preferredDisplayModeId = if (fast) selected?.modeId ?: 0 else 0
        window.attributes = attributes
    }

    private fun releasePlayer(restoreFocus: Boolean = false) {
        playerActive = false
        playerOwner = null
        buttons.clear()
        uiKeys.clear()
        navigationKey = 0
        handler.removeCallbacks(repeatNavigation)
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        configurePlaybackDisplay(false)
        if (restoreFocus) focusFlutter()
    }

    private fun focusFlutter() {
            fun flutterView(view: View): FlutterView? {
                if (view is FlutterView) return view
                if (view is ViewGroup) for (i in 0 until view.childCount) flutterView(view.getChildAt(i))?.let { return it }
                return null
            }
            handler.post {
                if (playerActive) return@post
                flutterView(window.decorView)?.let {
                    val previous = it.descendantFocusability
                    it.descendantFocusability = ViewGroup.FOCUS_BLOCK_DESCENDANTS
                    it.isFocusableInTouchMode = true
                    it.requestFocus()
                    it.descendantFocusability = previous
                }
            }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        if (isTelevision()) requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        (getSystemService(Context.INPUT_SERVICE) as InputManager).registerInputDeviceListener(this, handler)
        deviceChannel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "gameclub/device")
        deviceChannel!!.setMethodCallHandler { call, result ->
            when (call.method) {
                "info" -> {
                    val screen = if (Build.VERSION.SDK_INT >= 30) display else windowManager.defaultDisplay
                    val webView = if (Build.VERSION.SDK_INT >= 26) WebView.getCurrentWebViewPackage()?.versionName else "Android ${Build.VERSION.RELEASE}"
                    result.success(mapOf("television" to isTelevision(), "nativeGamepads" to true,
                        "model" to Build.MODEL, "refreshRate" to screen?.refreshRate, "webView" to webView,
                        "playerActive" to playerActive, "gamepadConnected" to hasGamepad(), "variant" to BuildConfig.GAMECLUB_DEVICE))
                }
                "bluetoothSettings" -> {
                    try { startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS)) }
                    catch (_: ActivityNotFoundException) { startActivity(Intent(Settings.ACTION_SETTINGS)) }
                    result.success(null)
                }
                "playerActive" -> {
                    val owner = call.argument<String>("owner")
                    if (call.argument<Boolean>("active") != true && owner != null && playerOwner != owner) {
                        result.success(null)
                        return@setMethodCallHandler
                    }
                    playerActive = call.argument<Boolean>("active") == true
                    if (playerActive) playerOwner = owner
                    navigationKey = 0
                    handler.removeCallbacks(repeatNavigation)
                    buttons.clear()
                    if (playerActive) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    if (playerActive && isTelevision()) configurePlaybackDisplay(call.argument<Boolean>("fast") == true)
                    else if (call.argument<Boolean>("restoreDisplay") == true) configurePlaybackDisplay(false)
                    if (!playerActive && call.argument<Boolean>("restoreDisplay") == true) releasePlayer(true)
                    else if (!playerActive) focusFlutter()
                    result.success(null)
                }
                "libraryActive" -> { releasePlayer(true); result.success(null) }
                "nativePlatform" -> {
                    val abi = Build.SUPPORTED_ABIS.first { it == "arm64-v8a" || it == "armeabi-v7a" || it == "x86_64" }
                    result.success("android-$abi")
                }
                "playNative" -> {
                    if (nativeResult != null) { result.error("busy", "Ya hay un juego abierto", null); return@setMethodCallHandler }
                    releasePlayer(true)
                    nativeResult = result
                    val arguments = call.argument<List<String>>("arguments") ?: emptyList()
                    try {
                        startActivityForResult(Intent(this, NativeGameActivity::class.java)
                            .putExtra("arguments", arguments.toTypedArray())
                            .putExtra("orientation", call.argument<String>("orientation") ?: "auto")
                            .putExtra("touchScale", call.argument<Double>("touchScale") ?: 1.0), 7101)
                    } catch (error: Exception) { nativeResult=null;result.error("native",error.message,null) }
                }
                else -> result.notImplemented()
            }
        }
        EventChannel(flutterEngine.dartExecutor.binaryMessenger, "gameclub/gamepad").setStreamHandler(object : EventChannel.StreamHandler {
            override fun onListen(arguments: Any?, events: EventChannel.EventSink) {
                sinkOwner = (arguments as? Map<*, *>)?.get("owner") as? String
                sink = events
            }
            override fun onCancel(arguments: Any?) {
                val owner = (arguments as? Map<*, *>)?.get("owner") as? String
                if (owner != null && owner != sinkOwner) return
                sink = null
                sinkOwner = null
                if (owner == playerOwner) releasePlayer(true)
            }
        })
    }

    private fun buttonIndex(key: Int): Int? = when (key) {
        KeyEvent.KEYCODE_BUTTON_A -> 8
        KeyEvent.KEYCODE_BUTTON_B -> 0
        KeyEvent.KEYCODE_BUTTON_X -> 9
        KeyEvent.KEYCODE_BUTTON_Y -> 1
        KeyEvent.KEYCODE_BUTTON_SELECT -> 2
        KeyEvent.KEYCODE_BUTTON_START -> 3
        KeyEvent.KEYCODE_DPAD_UP -> 4
        KeyEvent.KEYCODE_DPAD_DOWN -> 5
        KeyEvent.KEYCODE_DPAD_LEFT -> 6
        KeyEvent.KEYCODE_DPAD_RIGHT -> 7
        KeyEvent.KEYCODE_BUTTON_L1 -> 10
        KeyEvent.KEYCODE_BUTTON_R1 -> 11
        KeyEvent.KEYCODE_BUTTON_L2 -> 12
        KeyEvent.KEYCODE_BUTTON_R2 -> 13
        KeyEvent.KEYCODE_BUTTON_THUMBL -> 14
        KeyEvent.KEYCODE_BUTTON_THUMBR -> 15
        else -> null
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        val pad = KeyEvent.isGamepadButton(event.keyCode) || isGamepad(event.source) || isGamepad(event.device?.sources ?: 0)
        val key = Pair(event.deviceId, event.keyCode)
        val routedKey = pad || event.keyCode in KeyEvent.KEYCODE_DPAD_UP..KeyEvent.KEYCODE_DPAD_CENTER ||
            event.keyCode == KeyEvent.KEYCODE_ENTER || event.keyCode == KeyEvent.KEYCODE_BACK || event.keyCode == KeyEvent.KEYCODE_ESCAPE
        if (!playerActive && routedKey) {
            if (event.action == KeyEvent.ACTION_DOWN) {
                if (event.repeatCount == 0) uiKeys.add(key)
                else if (!uiKeys.contains(key)) return true
            } else if (event.action == KeyEvent.ACTION_UP && !uiKeys.remove(key)) {
                // El DOWN lo recibió la actividad nativa ya cerrada. No sintetizar
                // una activación nueva en la biblioteca al recibir solo su UP.
                gameKeys.remove(key)
                return true
            }
        }
        if (pad && (buttonIndex(event.keyCode) != null || event.keyCode == KeyEvent.KEYCODE_BUTTON_MODE)) {
            if (event.action == KeyEvent.ACTION_UP) {
                if (!gameKeys.remove(key)) return super.dispatchKeyEvent(event)
                if (!playerActive) return true
            } else if (event.action == KeyEvent.ACTION_DOWN) {
                if (event.repeatCount == 0) {
                    if (!playerActive) {
                        gameKeys.remove(key)
                        return super.dispatchKeyEvent(event)
                    }
                    gameKeys.add(key)
                } else if (!gameKeys.contains(key)) return super.dispatchKeyEvent(event)
                else if (!playerActive) return true
            }
        }
        if (playerActive && pad) {
            if (event.keyCode == KeyEvent.KEYCODE_BUTTON_MODE) {
                if (event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) sink?.success(mapOf("type" to "menu"))
                return true
            }
            val index = buttonIndex(event.keyCode)
            if (index != null && (event.action == KeyEvent.ACTION_DOWN || event.action == KeyEvent.ACTION_UP)) {
                val pressed = buttons.getOrPut(event.deviceId) { mutableSetOf() }
                if (event.action == KeyEvent.ACTION_DOWN) pressed.add(index) else pressed.remove(index)
                if (pressed.contains(2) && pressed.contains(3) && event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) {
                    sink?.success(mapOf("type" to "menu"))
                    return true
                }
                sink?.success(mapOf("type" to "button", "device" to event.deviceId, "index" to index, "pressed" to (event.action == KeyEvent.ACTION_DOWN)))
                return true
            }
        }
        return super.dispatchKeyEvent(event)
    }

    private fun axis(event: MotionEvent, axis: Int): Float {
        val value = event.getAxisValue(axis)
        val flat = event.device?.getMotionRange(axis, event.source)?.flat ?: 0.15f
        return if (abs(value) <= maxOf(flat, 0.15f)) 0f else value.coerceIn(-1f, 1f)
    }

    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
        if ((isGamepad(event.source) || isGamepad(event.device?.sources ?: 0)) && event.action == MotionEvent.ACTION_MOVE) {
            val values = GamepadMotion.axes(event)
            val x = values[0]
            val y = values[1]
            val hx = values[4]
            val hy = values[5]
            if (playerActive) {
                sink?.success(mapOf("type" to "axes", "device" to event.deviceId,
                    "axes" to values.toList()))
                return true
            } else {
                val dx = if (hx != 0f) hx else x
                val dy = if (hy != 0f) hy else y
                val key = when {
                    abs(dx) < 0.5f && abs(dy) < 0.5f -> 0
                    abs(dx) > abs(dy) -> if (dx > 0) KeyEvent.KEYCODE_DPAD_RIGHT else KeyEvent.KEYCODE_DPAD_LEFT
                    else -> if (dy > 0) KeyEvent.KEYCODE_DPAD_DOWN else KeyEvent.KEYCODE_DPAD_UP
                }
                if (key != navigationKey) {
                    navigationKey = key
                    handler.removeCallbacks(repeatNavigation)
                    if (key != 0) { sendNavigation(key); handler.postDelayed(repeatNavigation, 420) }
                }
                return true
            }
        }
        return super.dispatchGenericMotionEvent(event)
    }

    private fun sendNavigation(key: Int) {
        super.dispatchKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, key))
        super.dispatchKeyEvent(KeyEvent(KeyEvent.ACTION_UP, key))
    }

    override fun onInputDeviceRemoved(deviceId: Int) {
        deviceChannel?.invokeMethod("gamepadConnected", hasGamepad())
        gameKeys.removeAll { it.first == deviceId }
        buttons.remove(deviceId)
        if (playerActive) sink?.success(mapOf("type" to "disconnect", "device" to deviceId))
        navigationKey = 0
        handler.removeCallbacks(repeatNavigation)
    }
    override fun onInputDeviceAdded(deviceId: Int) { deviceChannel?.invokeMethod("gamepadConnected", hasGamepad()) }
    override fun onInputDeviceChanged(deviceId: Int) { deviceChannel?.invokeMethod("gamepadConnected", hasGamepad()) }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 7101) {
            val result = nativeResult
            nativeResult = null
            releasePlayer(true)
            handler.postDelayed({ result?.success(null) }, 250)
        }
    }

    override fun onPause() {
        uiKeys.clear()
        if (playerActive) sink?.success(mapOf("type" to "reset"))
        buttons.clear()
        navigationKey = 0
        handler.removeCallbacks(repeatNavigation)
        super.onPause()
    }

    override fun onDestroy() {
        (getSystemService(Context.INPUT_SERVICE) as InputManager).unregisterInputDeviceListener(this)
        handler.removeCallbacksAndMessages(null)
        sink = null
        super.onDestroy()
    }
}
