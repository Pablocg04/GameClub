package com.gameclub.gameclub

import android.os.Bundle
import android.os.Process
import android.os.Build
import android.os.SystemClock
import android.content.pm.ActivityInfo
import android.content.Context
import android.hardware.input.InputManager
import android.view.InputDevice
import android.view.KeyEvent
import android.view.MotionEvent
import android.window.OnBackInvokedCallback
import android.window.OnBackInvokedDispatcher
import org.libsdl.app.SDLActivity

/** El motor vive en :emulation: un fallo de un core no cierra la biblioteca. */
class NativeGameActivity : SDLActivity(), InputManager.InputDeviceListener {
    private val ports = GamepadPorts()
    private val heldKeys = mutableSetOf<Pair<Int, Int>>()
    private var backCallback: Any? = null
    private var lastBackKey = 0L
    private var lastSystemBack = 0L
    private fun systemBack() {
        val now = SystemClock.uptimeMillis()
        // Algunos Android entregan la misma pulsación como tecla y como callback predictivo.
        if (now-lastBackKey < 500 || now-lastSystemBack < 300) return
        lastSystemBack = now
        if (!mBrokenLibraries) nativeMenu() else finish()
    }
    private external fun nativeButton(index: Int, down: Boolean, port: Int)
    private external fun nativeAxes(values: FloatArray, port: Int)
    private external fun nativeReset(port: Int)
    private external fun nativeMenu()
    override fun getLibraries() = arrayOf("SDL3", "gameclub_native")
    private fun orientationMode(): String = if (BuildConfig.GAMECLUB_DEVICE == "tv") "tv" else intent.getStringExtra("orientation") ?: "auto"
    private fun applyOrientation() {
        requestedOrientation = when(orientationMode()) {
            "tv", "landscape" -> ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            "portrait" -> ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT
            else -> ActivityInfo.SCREEN_ORIENTATION_FULL_USER
        }
    }
    override fun getArguments(): Array<String> = (intent.getStringArrayExtra("arguments") ?: emptyArray()) + arrayOf(
        "--touch-density=${resources.displayMetrics.density}",
        "--touch-scale=${intent.getDoubleExtra("touchScale", 1.0)}",
        "--orientation=${orientationMode()}"
    )
    override fun setOrientationBis(w: Int, h: Int, resizable: Boolean, hint: String) { applyOrientation() }
    override fun onCreate(savedInstanceState: Bundle?) {
        setResult(RESULT_OK)
        applyOrientation()
        super.onCreate(savedInstanceState)
        (getSystemService(Context.INPUT_SERVICE) as InputManager).registerInputDeviceListener(this, null)
        if (Build.VERSION.SDK_INT >= 33) {
            val callback = OnBackInvokedCallback { systemBack() }
            onBackInvokedDispatcher.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, callback)
            backCallback = callback
        }
    }
    override fun onBackPressed() { systemBack() }
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (mBrokenLibraries) return super.dispatchKeyEvent(event)
        val pad = KeyEvent.isGamepadButton(event.keyCode) || event.isFromSource(InputDevice.SOURCE_GAMEPAD) ||
            event.isFromSource(InputDevice.SOURCE_JOYSTICK) ||
            (event.device?.sources ?: 0) and InputDevice.SOURCE_GAMEPAD == InputDevice.SOURCE_GAMEPAD
        if (event.keyCode == KeyEvent.KEYCODE_BACK || (pad && event.keyCode == KeyEvent.KEYCODE_BUTTON_MODE)) {
            if(event.keyCode == KeyEvent.KEYCODE_BACK) lastBackKey=SystemClock.uptimeMillis()
            if(event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) nativeMenu()
            return true
        }
        val index = when(event.keyCode) {
            KeyEvent.KEYCODE_BUTTON_A -> 8; KeyEvent.KEYCODE_BUTTON_B -> 0
            KeyEvent.KEYCODE_BUTTON_X -> 9; KeyEvent.KEYCODE_BUTTON_Y -> 1
            KeyEvent.KEYCODE_BUTTON_SELECT -> 2; KeyEvent.KEYCODE_BUTTON_START -> 3
            KeyEvent.KEYCODE_DPAD_UP -> 4; KeyEvent.KEYCODE_DPAD_DOWN -> 5
            KeyEvent.KEYCODE_DPAD_LEFT -> 6; KeyEvent.KEYCODE_DPAD_RIGHT -> 7
            KeyEvent.KEYCODE_BUTTON_L1 -> 10; KeyEvent.KEYCODE_BUTTON_R1 -> 11
            KeyEvent.KEYCODE_BUTTON_L2 -> 12; KeyEvent.KEYCODE_BUTTON_R2 -> 13
            KeyEvent.KEYCODE_BUTTON_THUMBL -> 14; KeyEvent.KEYCODE_BUTTON_THUMBR -> 15
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER -> 8
            else -> null
        }
        if(index != null && (pad || event.keyCode in KeyEvent.KEYCODE_DPAD_UP..KeyEvent.KEYCODE_DPAD_CENTER || event.keyCode == KeyEvent.KEYCODE_ENTER)) {
            val key = Pair(event.deviceId, event.keyCode)
            if (event.action == KeyEvent.ACTION_UP && !heldKeys.remove(key)) return true
            if (event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) heldKeys.add(key)
            val controller = GamepadMotion.isGamepad(event.source) || GamepadMotion.isGamepad(event.device?.sources ?: 0)
            val port = if (controller) ports.port(event.deviceId) else 0
            if(event.repeatCount == 0 && port >= 0) nativeButton(index, event.action == KeyEvent.ACTION_DOWN, port)
            return true
        }
        return super.dispatchKeyEvent(event)
    }
    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
        if (!mBrokenLibraries && event.action == MotionEvent.ACTION_MOVE &&
            (GamepadMotion.isGamepad(event.source) || GamepadMotion.isGamepad(event.device?.sources ?: 0))) {
            val port = ports.port(event.deviceId)
            if (port >= 0) nativeAxes(GamepadMotion.axes(event), port)
            return true
        }
        return super.dispatchGenericMotionEvent(event)
    }
    override fun onInputDeviceRemoved(deviceId: Int) {
        heldKeys.removeAll { it.first == deviceId }
        ports.remove(deviceId)?.let { if (!mBrokenLibraries) nativeReset(it) }
    }
    override fun onInputDeviceAdded(deviceId: Int) {}
    override fun onInputDeviceChanged(deviceId: Int) {}
    override fun onPause() {
        heldKeys.clear()
        if (!mBrokenLibraries) nativeReset(-1)
        super.onPause()
    }
    override fun onDestroy() {
        (getSystemService(Context.INPUT_SERVICE) as InputManager).unregisterInputDeviceListener(this)
        if (Build.VERSION.SDK_INT >= 33) {
            (backCallback as? OnBackInvokedCallback)?.let { onBackInvokedDispatcher.unregisterOnBackInvokedCallback(it) }
        }
        super.onDestroy()
        // SDL y algunos cores usan estado global; cada partida empieza en un proceso limpio.
        Process.killProcess(Process.myPid())
    }
}
