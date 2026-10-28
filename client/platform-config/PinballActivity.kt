package com.gameclub.gameclub

import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.graphics.Color
import android.hardware.input.InputManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import android.view.Gravity
import android.view.InputDevice
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.CheckBox
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.RelativeLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.TextView
import androidx.annotation.Keep
import org.json.JSONObject
import org.libsdl.app.SDLActivity
import java.io.File
import java.security.MessageDigest
import kotlin.concurrent.thread

/** VPX pertenece a GameClub y vive en :pinball, con un SDL/estado nativo limpio por partida. */
@Keep
class PinballActivity : SDLActivity(), InputManager.InputDeviceListener {
    private val handler = Handler(Looper.getMainLooper())
    private var sessionRoot: File? = null
    private lateinit var primary: File
    private lateinit var progress: TextView
    private var controls: View? = null
    private var dialog: AlertDialog? = null
    private val held = mutableMapOf<String, Int>()
    private val tapped = mutableSetOf<Int>()
    private val padKeys = mutableSetOf<Pair<Int, Int>>()
    private val axes = mutableMapOf<Int, FloatArray>()
    @Volatile private var closing = false
    private var ready = false
    private var loaded = false
    private var initialized = false
    private var restarting = false
    private var initializeRom = false
    private var initializedReload = false
    private var firstMenu = true
    private var state = "loading"
    private var queuedCoins = 0
    private var lastCoin = 0L
    private var startRequested = false
    private var menuSelection = 0
    private var menuButtons = emptyList<Button>()
    private var startupTimeout: Runnable? = null
    private var presentation = JSONObject()

    private external fun nativeReady(): Boolean
    private external fun nativeInitialize()
    private external fun nativeLoad(path: String, mechanical: Int, electronic: Int, scale: Int, score: Boolean): Int
    private external fun nativePlay(): Int
    private external fun nativeStop()
    private external fun nativeVersion(): String

    override fun getLibraries() = arrayOf("SDL3", "vpinball", "gameclub_pinball")
    override fun getMainSharedObject() = applicationInfo.nativeLibraryDir + "/libvpinball.so"
    override fun getFilesDir(): File = sessionRoot ?: super.getFilesDir()
    private fun television() = BuildConfig.GAMECLUB_DEVICE == "tv"
    private fun applyOrientation() {
        requestedOrientation = when {
            television() -> ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            intent.getStringExtra("orientation") == "portrait" -> ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT
            intent.getStringExtra("orientation") == "landscape" -> ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            else -> ActivityInfo.SCREEN_ORIENTATION_FULL_USER
        }
    }
    override fun setOrientationBis(w: Int, h: Int, resizable: Boolean, hint: String) { applyOrientation() }

    override fun onCreate(savedInstanceState: Bundle?) {
        val root = intent.getStringExtra("preferences")?.let { File(it).canonicalFile }
        val source = intent.getStringExtra("path")?.let { File(it).canonicalFile }
        val saves = File(applicationContext.filesDir, "pinball/saves").canonicalFile
        val tables = File(applicationInfo.dataDir, "app_flutter/GameClub/pinball").canonicalFile
        require(root != null && root.path.startsWith(saves.path + File.separator)) { "Ruta de guardados inválida" }
        require(source != null && source.isFile && source.extension.lowercase() == "vpx" && source.path.startsWith(tables.path + File.separator)) { "Mesa pinball no disponible" }
        root.mkdirs()
        sessionRoot = root
        primary = source
        val settings = File(root, "presentation.json")
        presentation = if (settings.isFile) runCatching { JSONObject(settings.readText()) }.getOrElse {
            android.util.Log.w("GameClubPinball", "No se pudieron leer los ajustes de imagen y sonido", it)
            JSONObject()
        } else JSONObject()
        setResult(RESULT_CANCELED)
        applyOrientation()
        super.onCreate(savedInstanceState)
        if (mBrokenLibraries) { writeState("error", "No se pudieron cargar las bibliotecas VPX incluidas"); return }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        progress = TextView(this).apply {
            text = "Preparando pinball de GameClub…"
            textSize = 20f; gravity = Gravity.CENTER
            setTextColor(Color.WHITE); setBackgroundColor(Color.rgb(16, 17, 28))
            isClickable = true
        }
        mLayout.addView(progress, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        buildControls()
        mLayout.addOnLayoutChangeListener { _, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom ->
            if (right - left != oldRight - oldLeft || bottom - top != oldBottom - oldTop) fitSurface()
        }
        progress.bringToFront()
        (getSystemService(Context.INPUT_SERVICE) as InputManager).registerInputDeviceListener(this, handler)
        writeState("loading")
        thread(name = "GameClub-Pinball-prepare") {
            try {
                prepareRuntime(root)
                var attempts = 0
                while (!closing && !nativeReady() && attempts++ < 150) Thread.sleep(200)
                check(!closing && nativeReady()) { "SDL no pudo preparar la superficie de pinball" }
                nativeInitialize()
            } catch (error: Throwable) { fail(error.message ?: "No se pudo preparar VPX") }
        }
    }

    private fun digest(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val bytes = ByteArray(65536)
            while (true) { val size = input.read(bytes); if (size < 0) break; digest.update(bytes, 0, size) }
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
    }
    private fun prepareRuntime(root: File) {
        val registry = JSONObject(assets.open("pinball-runtime.json").bufferedReader().use { it.readText() })
        val entries = registry.getJSONObject("assets")
        for (name in entries.keys()) {
            check(!closing) { "Preparación cancelada" }
            val target = File(root, name).canonicalFile
            check(target.path.startsWith(root.path + File.separator)) { "Ruta VPX inválida" }
            val item = entries.getJSONObject(name)
            if (target.isFile && target.length() == item.getLong("size") && digest(target) == item.getString("sha256")) continue
            target.parentFile!!.mkdirs()
            val part = File(target.path + ".part")
            try {
                assets.open("pinball/$name").use { input -> part.outputStream().use { output -> input.copyTo(output) } }
                check(part.length() == item.getLong("size") && digest(part) == item.getString("sha256")) { "Recursos VPX incompletos" }
                check(part.renameTo(target)) { "No se pudo publicar un recurso VPX" }
            } finally { part.delete() }
        }
        val preferences = File(root, "10.8").apply { mkdirs() }
        val ini = File(preferences, "VPinballX.ini")
        if (!ini.exists()) {
            val backend = PinballSupport.capabilities(this)["backend"]
            ini.writeText("""[Player]
GfxBackend=$backend
MaxFramerate=60
MaxTexDimension=1536
PlayfieldFullScreen=1
TouchOverlay=0
[Standalone]
WebServer=0
[Plugin.PinMAME]
Enable=1
[Plugin.ScoreView]
Enable=1
[ScoreView]
ScoreViewOutput=2
ScoreViewWidth=320
ScoreViewHeight=100
ScoreViewWndX=8
ScoreViewWndY=8
""")
        }
        initializeRom = (intent.getStringArrayExtra("roms") ?: emptyArray()).any { it.startsWith("afm_") } && !File(root, ".initialized-afm-v2").isFile
    }

    @Keep
    fun onNativeEvent(event: Int, data: String?) {
        handler.post {
            if (closing && event != 6) return@post
            when (event) {
                0 -> { initialized = true; android.util.Log.i("GameClubPinball", "Motor integrado: ${nativeVersion()}"); loadTable() }
                2, 3 -> if (!ready) {
                    val percent = runCatching { JSONObject(data ?: "{}").optInt("progress") }.getOrDefault(0)
                    progress.text = "Cargando mesa… $percent%"
                }
                4 -> playerStarted()
                6 -> {
                    loaded = false; ready = false; releaseAll()
                    if (restarting && !closing) {
                        restarting = false
                        handler.postDelayed({ loadTable() }, 600)
                    } else finishSaved()
                }
            }
        }
    }
    private fun loadTable() {
        if (closing) { finishSaved(); return }
        ready = false
        progress.visibility = View.VISIBLE
        progress.text = "Cargando ${intent.getStringExtra("title") ?: primary.nameWithoutExtension}…"
        progress.bringToFront()
        writeState("loading")
        startupTimeout?.let { handler.removeCallbacks(it) }
        startupTimeout = Runnable { if (!closing && !ready) fail("El motor no terminó de iniciar. Revisa el registro de la mesa en ${File(sessionRoot!!, "10.8/vpinball.log")}") }.also { handler.postDelayed(it, 300000) }
        thread(name = "GameClub-Pinball-load") {
            try {
                check(nativeLoad(primary.path, presentation.optInt("mechanical", 35), presentation.optInt("electronic", 100), presentation.optInt("scale", 95), presentation.optBoolean("score", true)) == 0) { "El motor no pudo cargar la mesa. Revisa sus archivos y ROMs." }
                loaded = true
                if (!closing) check(nativePlay() == 0) { "El motor no pudo iniciar la mesa" }
                else handler.post { finishSaved() }
            } catch (error: Throwable) { fail(error.message ?: "Error de VPX") }
        }
    }
    private fun playerStarted() {
        startupTimeout?.let { handler.removeCallbacks(it) }; startupTimeout = null
        ready = false
        writeState("starting")
        if (initializeRom && !initializedReload) {
            progress.text = "Inicializando la ROM por primera vez…\nSe conservarán tus partidas."
            listOf(10000L, 20000L).forEach { delay -> handler.postDelayed({
                if (!closing && loaded) tap(KeyEvent.KEYCODE_F3)
            }, delay) }
            handler.postDelayed({
                if (!closing && loaded) { initializedReload = true; restartTable() }
            }, 35000)
        } else {
            progress.text = "Encendiendo la ROM…"
            handler.postDelayed({
                if (closing || !loaded) return@postDelayed
                if (initializeRom) File(sessionRoot!!, ".initialized-afm-v2").writeText("complete\n")
                ready = true
                progress.visibility = View.GONE
                writeState("running")
                if (firstMenu) { firstMenu = false; showMenu() }
            }, if (intent.getBooleanExtra("requiresRom", false)) 15000 else 800)
        }
    }
    private fun writeState(value: String, message: String = "") {
        state = value
        sessionRoot?.let { root ->
            val part = File(root, "session.json.part")
            part.writeText(JSONObject(mapOf("state" to value, "message" to message, "time" to System.currentTimeMillis())).toString())
            part.renameTo(File(root, "session.json"))
        }
        android.util.Log.i("GameClubPinball", "state=$value $message")
    }
    private fun fail(message: String) {
        handler.post {
            if (isFinishing) return@post
            closing = true; releaseAll(); writeState("error", message)
            setResult(RESULT_CANCELED, Intent().putExtra("pinball_error", message))
            AlertDialog.Builder(this).setTitle("No se pudo abrir el pinball").setMessage(message)
                .setPositiveButton("Volver a GameClub") { _, _ -> finish() }.setCancelable(false).show()
        }
    }
    private fun finishSaved() {
        if (state != "error") { writeState("closed"); setResult(RESULT_OK) }
        handler.postDelayed({ finish() }, 400)
    }
    private fun stopTable() {
        if (closing) return
        closing = true; releaseAll(); writeState("saving")
        if (initialized && loaded) nativeStop() else finishSaved()
    }
    private fun restartTable() {
        if (closing || !loaded) return
        releaseAll(); ready = false; restarting = true; writeState("restarting")
        progress.visibility = View.VISIBLE; progress.text = "Reiniciando mesa…"; progress.bringToFront()
        nativeStop()
    }

    private fun press(token: String, key: Int, down: Boolean) {
        if (down) {
            if (!ready || closing || dialog != null || held.containsKey(token)) return
            if (!held.containsValue(key)) onNativeKeyDown(key)
            held[token] = key
        } else {
            val old = held.remove(token) ?: return
            if (!held.containsValue(old)) onNativeKeyUp(old)
        }
    }
    private fun tap(key: Int) {
        if (!tapped.add(key)) return
        onNativeKeyDown(key)
        handler.postDelayed({ if (tapped.remove(key) && !mBrokenLibraries) onNativeKeyUp(key) }, if (key == KeyEvent.KEYCODE_1) 500 else 100)
    }
    private val deliverCoin = object : Runnable {
        override fun run() {
            if (!ready || closing || dialog != null) { queuedCoins = 0; startRequested = false; return }
            val now = SystemClock.uptimeMillis()
            if (queuedCoins > 0 && now - lastCoin >= 1100) {
                queuedCoins--; lastCoin = now; tap(KeyEvent.KEYCODE_5)
            }
            if (startRequested && queuedCoins == 0 && now - lastCoin >= 1100) {
                startRequested = false; tap(KeyEvent.KEYCODE_1)
            }
            if (queuedCoins > 0 || startRequested) handler.postDelayed(this, 80)
        }
    }
    private fun credit() { if (ready && dialog == null) { queuedCoins = minOf(queuedCoins + 1, 20); handler.removeCallbacks(deliverCoin); handler.post(deliverCoin) } }
    private fun startGame() { if (ready && dialog == null) { startRequested = true; handler.removeCallbacks(deliverCoin); handler.post(deliverCoin) } }
    private fun releaseAll() {
        if (!mBrokenLibraries) (held.values.toSet() + tapped).forEach { onNativeKeyUp(it) }
        held.clear(); tapped.clear(); padKeys.clear(); axes.clear(); queuedCoins = 0; startRequested = false
        handler.removeCallbacks(deliverCoin)
    }
    private fun showMenu() {
        if (closing || dialog != null) return
        releaseAll(); menuSelection = 0
        val column = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(8), dp(20), dp(12)) }
        column.addView(TextView(this).apply {
            text = "Select/Y: moneda · Start: partida · A: bola\nLB/LT y RB/RT: flippers\nStart + Select o Atrás: menú\nCruceta para elegir, A para aceptar y B para continuar."
            setPadding(0, 0, 0, dp(12)); textSize = 16f
        })
        val labels = listOf("Continuar", "Reiniciar mesa", "Guardar y salir", "Imagen y sonido")
        menuButtons = labels.mapIndexed { index, label -> Button(this).apply {
            text = label; isFocusable = true; isFocusableInTouchMode = false
            setOnFocusChangeListener { _, focused -> if (focused) menuSelection = index }
            setOnClickListener { selectMenu(index) }
            column.addView(this, LinearLayout.LayoutParams(-1, dp(52)))
        } }
        dialog = AlertDialog.Builder(this).setTitle("Menú pinball · GameClub").setView(ScrollView(this@PinballActivity).apply { addView(column) }).setCancelable(false).create().apply {
            setOnKeyListener { _, key, event ->
                if (event.action != KeyEvent.ACTION_DOWN) return@setOnKeyListener key in setOf(KeyEvent.KEYCODE_BUTTON_A, KeyEvent.KEYCODE_BUTTON_B, KeyEvent.KEYCODE_BUTTON_START)
                when (key) {
                    KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_LEFT -> { menuSelection = (menuSelection + menuButtons.size - 1) % menuButtons.size; menuButtons[menuSelection].requestFocus(); true }
                    KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT -> { menuSelection = (menuSelection + 1) % menuButtons.size; menuButtons[menuSelection].requestFocus(); true }
                    KeyEvent.KEYCODE_BUTTON_A, KeyEvent.KEYCODE_BUTTON_START, KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_DPAD_CENTER -> { if (event.repeatCount == 0) selectMenu(menuSelection); true }
                    KeyEvent.KEYCODE_BUTTON_B, KeyEvent.KEYCODE_BACK, KeyEvent.KEYCODE_ESCAPE -> { selectMenu(0); true }
                    else -> false
                }
            }
            show()
        }
        menuButtons.first().requestFocus()
        writeState("menu")
    }
    private fun selectMenu(index: Int) {
        val old = dialog; dialog = null; old?.dismiss(); releaseAll()
        when (index) { 1 -> restartTable(); 2 -> stopTable(); 3 -> showPresentation(); else -> writeState(if (ready) "running" else "starting") }
    }
    private fun showPresentation() {
        val column = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(8), dp(20), dp(12)) }
        column.addView(TextView(this).apply { text = "Ajustes para esta mesa. Aplicarlos reinicia la partida; se conservan la configuración y los récords de la ROM." })
        fun slider(label: String, key: String, default: Int, minimum: Int = 0): SeekBar {
            val caption = TextView(this)
            val bar = SeekBar(this).apply { max = 100 - minimum; progress = presentation.optInt(key, default).coerceIn(minimum, 100) - minimum }
            fun update(value: Int) { caption.text = "$label: ${value + minimum}%" }
            update(bar.progress)
            bar.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(view: SeekBar?, value: Int, user: Boolean) { update(value) }
                override fun onStartTrackingTouch(view: SeekBar?) {}
                override fun onStopTrackingTouch(view: SeekBar?) {}
            })
            column.addView(caption); column.addView(bar)
            return bar
        }
        val mechanical = slider("Golpes, bola y flippers", "mechanical", 35)
        val electronic = slider("Música, voces y electrónica (ROM)", "electronic", 100)
        val scale = slider("Tamaño de la mesa", "scale", 95, 70)
        val score = CheckBox(this).apply { text = "Mostrar marcador adicional (ScoreView)"; isChecked = presentation.optBoolean("score", true) }
        column.addView(score)
        column.addView(TextView(this).apply { text = "Si la mesa ya muestra su marcador y ves dos, desactiva el adicional." })
        dialog = AlertDialog.Builder(this).setTitle("Imagen y sonido")
            .setView(ScrollView(this).apply { addView(column) })
            .setPositiveButton("Aplicar y reiniciar") { _, _ ->
                presentation = JSONObject(mapOf("mechanical" to mechanical.progress, "electronic" to electronic.progress, "scale" to scale.progress + 70, "score" to score.isChecked))
                val target = File(sessionRoot!!, "presentation.json")
                val part = File(target.path + ".part")
                part.writeText(presentation.toString()); check(part.renameTo(target)) { "No se pudieron guardar los ajustes de la mesa" }
                dialog = null; restartTable()
            }
            .setNegativeButton("Cancelar") { _, _ -> dialog = null; showMenu() }
            .setOnCancelListener { dialog = null; showMenu() }.create().apply { show() }
    }
    private fun dp(value: Int) = (value * resources.displayMetrics.density * intent.getDoubleExtra("touchScale", 1.0).coerceIn(.8, 1.35)).toInt()
    private fun control(label: String, key: Int? = null, action: (() -> Unit)? = null): Button = Button(this).apply {
        text = label; textSize = 14f; setPadding(0, 0, 0, 0); isAllCaps = false
        if (key != null) setOnTouchListener { view, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> press("touch-$label", key, true)
                MotionEvent.ACTION_UP -> { press("touch-$label", key, false); view.performClick() }
                MotionEvent.ACTION_CANCEL -> press("touch-$label", key, false)
            }; true
        } else setOnClickListener { action?.invoke() }
    }
    private fun buildControls() {
        releaseAll(); controls?.let { mLayout.removeView(it) }; controls = null
        val surface = RelativeLayout.LayoutParams(-1, -1)
        if (television()) { mSurface.layoutParams = surface; return }
        val landscape = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
        val overlay = FrameLayout(this)
        fun column(side: Int, buttons: List<Button>) {
            val group = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
            buttons.forEach { group.addView(it, LinearLayout.LayoutParams(-1, 0, 1f)) }
            overlay.addView(group, FrameLayout.LayoutParams(dp(90), -1, side))
        }
        if (landscape) {
            surface.leftMargin = dp(90); surface.rightMargin = dp(90)
            column(Gravity.LEFT, listOf(control("Moneda", action = ::credit), control("Partida", action = ::startGame), control("Izq.", KeyEvent.KEYCODE_SHIFT_LEFT)))
            column(Gravity.RIGHT, listOf(control("Menú", action = ::showMenu), control("Bola", KeyEvent.KEYCODE_ENTER), control("Der.", KeyEvent.KEYCODE_SHIFT_RIGHT)))
        } else {
            surface.bottomMargin = dp(126)
            val bottom = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
            val row = LinearLayout(this)
            listOf(control("Moneda", action = ::credit), control("Partida", action = ::startGame), control("Bola", KeyEvent.KEYCODE_ENTER), control("Menú", action = ::showMenu)).forEach { row.addView(it, LinearLayout.LayoutParams(0, -1, 1f)) }
            bottom.addView(row, LinearLayout.LayoutParams(-1, dp(50)))
            val flippers = LinearLayout(this)
            listOf(control("Flipper izquierdo", KeyEvent.KEYCODE_SHIFT_LEFT), control("Flipper derecho", KeyEvent.KEYCODE_SHIFT_RIGHT)).forEach { flippers.addView(it, LinearLayout.LayoutParams(0, -1, 1f)) }
            bottom.addView(flippers, LinearLayout.LayoutParams(-1, dp(76)))
            overlay.addView(bottom, FrameLayout.LayoutParams(-1, dp(126), Gravity.BOTTOM))
        }
        mSurface.layoutParams = surface
        mLayout.addView(overlay, ViewGroup.LayoutParams(-1, -1)); controls = overlay
        fitSurface()
    }
    private fun fitSurface() {
        if (television() || mLayout.width <= 0 || mLayout.height <= 0) return
        val landscape = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
        val side = if (landscape) dp(90) else 0
        val bottom = if (landscape) 0 else dp(126)
        val availableWidth = (mLayout.width - 2 * side).coerceAtLeast(1)
        val availableHeight = (mLayout.height - bottom).coerceAtLeast(1)
        // VPX caches its projection aspect at player creation. Keep the SDL
        // surface at the same aspect on rotation, fitting it inside the controls.
        // This avoids stretching the table and does not reset the running ROM.
        val width = minOf(availableWidth, (availableHeight * .6f).toInt()).coerceAtLeast(1)
        val height = (width / .6f).toInt().coerceAtLeast(1)
        mSurface.layoutParams = RelativeLayout.LayoutParams(width, height).apply {
            leftMargin = side + (availableWidth - width) / 2
            rightMargin = mLayout.width - leftMargin - width
            topMargin = (availableHeight - height) / 2
            bottomMargin = mLayout.height - topMargin - height
        }
    }
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (mBrokenLibraries) return super.dispatchKeyEvent(event)
        if (dialog != null) return super.dispatchKeyEvent(event)
        if (event.keyCode in setOf(KeyEvent.KEYCODE_BACK, KeyEvent.KEYCODE_ESCAPE, KeyEvent.KEYCODE_BUTTON_MODE)) {
            if (event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) showMenu()
            return true
        }
        val pad = KeyEvent.isGamepadButton(event.keyCode) || GamepadMotion.isGamepad(event.source) || GamepadMotion.isGamepad(event.device?.sources ?: 0)
        if (!pad) return super.dispatchKeyEvent(event)
        val id = event.deviceId; val key = Pair(id, event.keyCode)
        val down = event.action == KeyEvent.ACTION_DOWN
        if (down) { if (event.repeatCount != 0) return true; padKeys.add(key) }
        else if (!padKeys.remove(key)) return true
        if (padKeys.contains(Pair(id, KeyEvent.KEYCODE_BUTTON_SELECT)) && padKeys.contains(Pair(id, KeyEvent.KEYCODE_BUTTON_START))) { showMenu(); return true }
        val token = "pad-$id-${event.keyCode}"
        when (event.keyCode) {
            KeyEvent.KEYCODE_BUTTON_SELECT -> if (!down && !padKeys.contains(Pair(id, KeyEvent.KEYCODE_BUTTON_START))) credit()
            KeyEvent.KEYCODE_BUTTON_START -> if (!down && !padKeys.contains(Pair(id, KeyEvent.KEYCODE_BUTTON_SELECT))) startGame()
            KeyEvent.KEYCODE_BUTTON_Y -> if (down) credit()
            KeyEvent.KEYCODE_BUTTON_A -> press(token, KeyEvent.KEYCODE_ENTER, down)
            KeyEvent.KEYCODE_BUTTON_X, KeyEvent.KEYCODE_BUTTON_L1, KeyEvent.KEYCODE_BUTTON_L2 -> press(token, KeyEvent.KEYCODE_SHIFT_LEFT, down)
            KeyEvent.KEYCODE_BUTTON_B, KeyEvent.KEYCODE_BUTTON_R1, KeyEvent.KEYCODE_BUTTON_R2 -> press(token, KeyEvent.KEYCODE_SHIFT_RIGHT, down)
            KeyEvent.KEYCODE_DPAD_LEFT -> press(token, KeyEvent.KEYCODE_Z, down)
            KeyEvent.KEYCODE_DPAD_RIGHT -> press(token, KeyEvent.KEYCODE_SLASH, down)
            KeyEvent.KEYCODE_DPAD_UP -> press(token, KeyEvent.KEYCODE_SPACE, down)
        }
        return true
    }
    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
        if (!mBrokenLibraries && event.action == MotionEvent.ACTION_MOVE && (GamepadMotion.isGamepad(event.source) || GamepadMotion.isGamepad(event.device?.sources ?: 0))) {
            val values = GamepadMotion.axes(event); axes[event.deviceId] = values
            val id = event.deviceId
            press("axis-$id-lt", KeyEvent.KEYCODE_SHIFT_LEFT, values[6] > .4f)
            press("axis-$id-rt", KeyEvent.KEYCODE_SHIFT_RIGHT, values[7] > .4f)
            press("axis-$id-left", KeyEvent.KEYCODE_Z, values[0] < -.6f)
            press("axis-$id-right", KeyEvent.KEYCODE_SLASH, values[0] > .6f)
            return true
        }
        return super.dispatchGenericMotionEvent(event)
    }
    override fun onInputDeviceRemoved(deviceId: Int) { padKeys.removeAll { it.first == deviceId }; releaseAll() }
    override fun onInputDeviceAdded(deviceId: Int) {}
    override fun onInputDeviceChanged(deviceId: Int) {}
    override fun onBackPressed() { showMenu() }
    override fun onPause() { releaseAll(); super.onPause() }
    override fun onWindowFocusChanged(hasFocus: Boolean) { super.onWindowFocusChanged(hasFocus); if (!hasFocus) releaseAll() }
    override fun onConfigurationChanged(newConfig: Configuration) { super.onConfigurationChanged(newConfig); if (!mBrokenLibraries) { buildControls(); if (!ready) progress.bringToFront() } }
    override fun onDestroy() {
        closing = true; releaseAll(); handler.removeCallbacksAndMessages(null)
        (getSystemService(Context.INPUT_SERVICE) as InputManager).unregisterInputDeviceListener(this)
        super.onDestroy()
        Process.killProcess(Process.myPid())
    }
}
