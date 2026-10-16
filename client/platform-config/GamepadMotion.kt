package com.gameclub.gameclub

import android.view.InputDevice
import android.view.MotionEvent
import kotlin.math.abs

/** Orden de puertos estable para teclas y ejes; no depende de controllerNumber de Android. */
class GamepadPorts {
    private val devices = linkedMapOf<Int, Int>()
    private val controllers = mutableMapOf<Int, Int>()
    fun port(deviceId: Int): Int {
        if (deviceId <= 0) return 0 // Dispositivo virtual de teclado/ADB.
        return devices.getOrPut(deviceId) {
            val number = InputDevice.getDevice(deviceId)?.controllerNumber ?: 0
            val port = (if (number > 0) controllers[number] else null) ?: (0..3).firstOrNull { !devices.containsValue(it) } ?: -1
            if (number > 0 && port >= 0) controllers[number] = port
            port
        }
    }
    fun remove(deviceId: Int): Int? {
        val port = devices.remove(deviceId)
        if (port != null && !devices.containsValue(port)) controllers.entries.removeAll { it.value == port }
        return port
    }
}

object GamepadMotion {
    fun isGamepad(source: Int): Boolean =
        source and InputDevice.SOURCE_GAMEPAD == InputDevice.SOURCE_GAMEPAD ||
            source and InputDevice.SOURCE_JOYSTICK == InputDevice.SOURCE_JOYSTICK

    fun axes(event: MotionEvent): FloatArray {
        fun supported(primary: Int, alternate: Int): Int =
            if (event.device?.getMotionRange(primary, event.source) == null && event.device?.getMotionRange(alternate, event.source) != null) alternate else primary
        fun stick(axis: Int): Float {
            val value = event.getAxisValue(axis)
            val flat = maxOf(event.device?.getMotionRange(axis, event.source)?.flat ?: .15f, .15f)
            return if (abs(value) <= flat) 0f else value.coerceIn(-1f, 1f)
        }
        return floatArrayOf(stick(MotionEvent.AXIS_X), stick(MotionEvent.AXIS_Y),
            stick(supported(MotionEvent.AXIS_Z, MotionEvent.AXIS_RX)), stick(supported(MotionEvent.AXIS_RZ, MotionEvent.AXIS_RY)),
            event.getAxisValue(MotionEvent.AXIS_HAT_X).coerceIn(-1f, 1f),
            event.getAxisValue(MotionEvent.AXIS_HAT_Y).coerceIn(-1f, 1f),
            maxOf(event.getAxisValue(MotionEvent.AXIS_LTRIGGER), event.getAxisValue(MotionEvent.AXIS_BRAKE)).coerceIn(0f, 1f),
            maxOf(event.getAxisValue(MotionEvent.AXIS_RTRIGGER), event.getAxisValue(MotionEvent.AXIS_GAS)).coerceIn(0f, 1f))
    }
}
