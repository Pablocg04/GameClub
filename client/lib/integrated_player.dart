import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:window_manager/window_manager.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import 'package:webview_windows/webview_windows.dart';
import 'television.dart';
import 'android_gamepad.dart';
import 'game_menu.dart';

class IntegratedPlayer extends StatefulWidget {
  const IntegratedPlayer(
      {super.key,
      required this.uri,
      required this.title,
      this.coreLabel,
      this.onCoreFailed,
      this.onCoreStarted,
      this.mameWebControls = false});
  final Uri uri;
  final String title;
  final String? coreLabel;
  final void Function(String)? onCoreFailed;
  final VoidCallback? onCoreStarted;
  final bool mameWebControls;

  @override
  State<IntegratedPlayer> createState() => _IntegratedPlayerState();
}

class _IntegratedPlayerState extends State<IntegratedPlayer> {
  static bool windowsEnvironmentReady = false;
  WebviewController? windows;
  WebViewController? android;
  StreamSubscription? messages;
  String status = 'Preparando el reproductor integrado…';
  bool initialized = false, failed = false, closing = false, canExit = false;
  Completer<String?>? exitCompleted;
  Timer? coreTimeout;
  bool coreStarted = false, coreFailureReported = false;
  AndroidGamepad? gamepad;
  bool television = false, gameMenu = false;
  bool wasFullscreen = false;

  Future<void> execute(String code) async {
    if (windows != null) await windows!.executeScript(code);
    if (android != null) await android!.runJavaScript(code);
  }

  Future<void> showGameMenu() async {
    if (!mounted || gameMenu || closing) return;
    gameMenu = true;
    await gamepad?.active(false);
    await execute(
        "document.activeElement?.blur();window.gameclubReleaseControllers?.();if(window.EJS_emulator?.started){EJS_emulator.gameManager.toggleMainLoop(0);EJS_emulator.paused=true;}true;");
    if (!mounted) return;
    final action = await showDialog<String>(
        context: context,
        requestFocus: true,
        builder: (_) => GameMenu(configureControls: widget.mameWebControls));
    gameMenu = false;
    if (!mounted) return;
    if (action == 'exit') {
      await leave();
    } else {
      await gamepad?.active(true);
      await execute(
          "if(window.EJS_emulator?.started){EJS_emulator.gameManager.toggleMainLoop(1);EJS_emulator.paused=false;}true;");
      if (action == 'controls') {
        await execute('window.gameclubConfigureControls?.();true;');
      }
    }
  }

  void coreFailure(String reason) {
    if (closing || coreFailureReported || !mounted) return;
    coreTimeout?.cancel();
    coreFailureReported = true;
    setState(() {
      status = reason;
      failed = true;
    });
    widget.onCoreFailed?.call(reason);
  }

  @override
  void didUpdateWidget(covariant IntegratedPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.uri != widget.uri) {
      coreTimeout?.cancel();
      coreStarted = false;
      coreFailureReported = false;
      failed = false;
      status = 'Probando ${widget.coreLabel ?? 'otro núcleo'}…';
      reloadCore();
    }
  }

  Future<void> reloadCore() async {
    try {
      await windows?.loadUrl(widget.uri.toString());
      await android?.loadRequest(widget.uri);
    } catch (_) {
      coreFailure('No se pudo cargar el núcleo');
    }
  }

  @override
  void initState() {
    super.initState();
    initialize();
  }

  void receive(dynamic value) {
    if (!mounted) return;
    try {
      final event = value is String ? jsonDecode(value) as Map : value as Map;
      if (event['session'] != null &&
          event['session'] != widget.uri.pathSegments[1]) {
        return;
      }
      switch (event['event']) {
        case 'ready':
          setState(() {
            failed = false;
            status = 'Iniciando el juego…';
          });
        case 'started':
          coreTimeout?.cancel();
          coreStarted = true;
          setState(() {
            status = '';
            failed = false;
          });
          widget.onCoreStarted?.call();
        case 'core-loading':
          coreTimeout?.cancel();
          coreTimeout = Timer(const Duration(minutes: 4),
              () => coreFailure('El núcleo no terminó de arrancar'));
        case 'core-failed':
          coreFailure(event['message'] as String);
        case 'performance':
          if (!closing && !failed) {
            final data = jsonDecode(event['message'] as String) as Map;
            setState(() {
              status = data['system'] == 'nds'
                  ? 'NDS: ${data['fps']} fotogramas/s · ${data['speed']}% de velocidad${data['parallel'] == true ? ' · multihilo' : ''}'
                  : '${data['fps']} FPS emulación · ${data['presentationFps'] ?? '?'} FPS WebView · ${DevicePlatform.fastTelevision ? 'TV rápido' : 'TV equilibrado'}';
            });
          }
        case 'error':
          if (widget.onCoreFailed != null && !coreStarted) {
            coreFailure(event['message'] as String);
            return;
          }
          setState(() {
            status = event['message'] as String;
            failed = true;
          });
        case 'exit':
          if (exitCompleted != null && !exitCompleted!.isCompleted) {
            exitCompleted!.complete(null);
          } else {
            leave(save: false);
          }
        case 'save-error':
          if (exitCompleted != null && !exitCompleted!.isCompleted) {
            exitCompleted!.complete(event['message'] as String);
          }
      }
    } catch (_) {}
  }

  Future<void> initialize() async {
    try {
      // La consulta nativa se hizo antes de crear la aplicación.
      television = DevicePlatform.television;
      if (Platform.isWindows) {
        await windowManager.ensureInitialized();
        wasFullscreen = await windowManager.isFullScreen();
        await windowManager.setFullScreen(true);
        if (!windowsEnvironmentReady) {
          final support = await getApplicationSupportDirectory();
          await WebviewController.initializeEnvironment(
              userDataPath: p.join(support.path, 'player-webview'),
              additionalArguments:
                  '--autoplay-policy=no-user-gesture-required');
          windowsEnvironmentReady = true;
        }
        final controller = WebviewController();
        windows = controller;
        await controller.initialize();
        if (!mounted) return;
        await controller.setBackgroundColor(const Color(0xff10111c));
        await controller.setPopupWindowPolicy(WebviewPopupWindowPolicy.deny);
        messages = controller.webMessage.listen(receive);
        await controller.loadUrl(widget.uri.toString());
      } else if (Platform.isAndroid) {
        if (!television) {
          await SystemChrome.setPreferredOrientations(
              switch (DevicePlatform.mobileOrientation) {
            'portrait' => [
                DeviceOrientation.portraitUp,
                DeviceOrientation.portraitDown
              ],
            'landscape' => [
                DeviceOrientation.landscapeLeft,
                DeviceOrientation.landscapeRight
              ],
            _ => []
          });
        }
        await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
        final controller = WebViewController();
        android = controller;
        if (controller.platform is AndroidWebViewController) {
          await (controller.platform as AndroidWebViewController)
              .setMediaPlaybackRequiresUserGesture(false);
        }
        await controller.setJavaScriptMode(JavaScriptMode.unrestricted);
        await controller.setBackgroundColor(const Color(0xff10111c));
        await controller.addJavaScriptChannel('GameClub',
            onMessageReceived: (event) => receive(event.message));
        await controller.setNavigationDelegate(NavigationDelegate(
          onNavigationRequest: (request) => request.url == 'about:blank' ||
                  (Uri.tryParse(request.url)?.isScheme('http') == true &&
                      Uri.parse(request.url).origin == widget.uri.origin)
              ? NavigationDecision.navigate
              : NavigationDecision.prevent,
          onWebResourceError: (error) {
            if (mounted && !closing && error.isForMainFrame != false) {
              setState(() {
                failed = true;
                status = 'No se pudo abrir el reproductor integrado.';
              });
            }
          },
        ));
        await controller.loadRequest(widget.uri);
        if (!mounted || closing) return;
        if (DevicePlatform.nativeGamepads) {
          gamepad = AndroidGamepad(execute: execute, onMenu: showGameMenu);
          await gamepad!.start();
        }
      } else {
        throw Exception(
            'El reproductor integrado está preparado para Windows y Android.');
      }
      if (mounted) {
        setState(() {
          initialized = true;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          failed = true;
          status = 'No se pudo iniciar el reproductor: $error';
        });
      }
    }
  }

  Future<void> leave({bool save = true}) async {
    if (closing) return;
    closing = true;
    if (mounted) {
      setState(() {
        status = 'Guardando y cerrando el juego…';
      });
    }
    if (save && initialized) {
      try {
        exitCompleted = Completer<String?>();
        const code =
            '(() => { if (window.gameclubExit) { window.gameclubExit(); return true; } return false; })()';
        dynamic requested;
        if (windows != null) requested = await windows!.executeScript(code);
        if (android != null) {
          requested = await android!.runJavaScriptReturningResult(code);
        }
        if ((requested == false || requested == 'false') &&
            !exitCompleted!.isCompleted) {
          exitCompleted!.complete(null);
        }
        final error =
            await exitCompleted!.future.timeout(const Duration(seconds: 15));
        if (error != null) throw Exception(error);
      } catch (_) {
        if (mounted) {
          setState(() {
            closing = false;
            status =
                'No se pudo confirmar el guardado. Vuelve a intentar cerrar el juego.';
          });
        }
        return;
      } finally {
        exitCompleted = null;
      }
    }
    if (!mounted) return;
    await gamepad?.dispose();
    try {
      await execute(
              "window.gameclubLeaving=true;window.gameclubReleaseControllers?.();try{window.EJS_emulator?.gameManager?.toggleMainLoop(0);}catch(_){}window.stop();true;")
          .timeout(const Duration(seconds: 2));
      if (android != null) await android!.loadRequest(Uri.parse('about:blank'));
      if (windows != null) await windows!.loadUrl('about:blank');
    } catch (_) {
      /* El guardado ya se confirmó; se libera la vista al desmontar. */
    }
    if (!mounted) return;
    setState(() {
      canExit = true;
    });
    Navigator.of(context).pop();
  }

  @override
  void dispose() {
    gamepad?.dispose();
    coreTimeout?.cancel();
    messages?.cancel();
    windows?.dispose();
    if (Platform.isAndroid) {
      SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
      if (!television) SystemChrome.setPreferredOrientations([]);
    }
    if (Platform.isWindows) windowManager.setFullScreen(wasFullscreen);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
        canPop: canExit,
        onPopInvokedWithResult: (didPop, result) {
          if (!didPop) showGameMenu();
        },
        child: Scaffold(
          backgroundColor: Colors.black,
          floatingActionButton: television
              ? null
              : Opacity(
                  opacity: .5,
                  child: FloatingActionButton.small(
                      tooltip: 'Menú del juego',
                      onPressed: closing ? null : showGameMenu,
                      child: const Icon(Icons.more_horiz))),
          body: Column(children: [
            if (status.isNotEmpty && (!coreStarted || failed || closing))
              Padding(
                  padding: const EdgeInsets.all(10),
                  child: Text(status, textAlign: TextAlign.center)),
            if (!initialized && !failed) const LinearProgressIndicator(),
            Expanded(
                child: initialized
                    ? Platform.isWindows
                        ? Webview(windows!)
                        : television && DevicePlatform.fastTelevision
                            ? ClipRect(
                                child: FittedBox(
                                    fit: BoxFit.contain,
                                    child: SizedBox(
                                        width: 640,
                                        height: 360,
                                        child: WebViewWidget.fromPlatformCreationParams(
                                            params: AndroidWebViewWidgetCreationParams(
                                                controller: android!.platform,
                                                displayWithHybridComposition:
                                                    DevicePlatform
                                                        .directTelevisionView)))))
                            : television
                                ? WebViewWidget.fromPlatformCreationParams(
                                    params: AndroidWebViewWidgetCreationParams(
                                        controller: android!.platform,
                                        displayWithHybridComposition:
                                            DevicePlatform
                                                .directTelevisionView))
                                : WebViewWidget(controller: android!)
                    : const SizedBox.shrink()),
          ]),
        ),
      );
}
