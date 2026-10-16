import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:dio/dio.dart';
import 'package:path/path.dart' as p;

import 'api.dart';
import 'gamepad_script.dart';
import 'nds_touch.dart';
import 'mame_web_player.dart';

const integratedCores = <String, String>{
  'gb': 'gambatte',
  'gbc': 'gambatte',
  'gba': 'mgba',
  'snes': 'snes9x',
  'nds': 'desmume',
  'n64': 'mupen64plus_next',
  'mame': 'mame2003_plus',
};
const arcadeCores = {'mame2003_plus', 'mame2003', 'fbneo', 'mame_web'};

class PlayerSession {
  PlayerSession(this.id, this.game, this.rom, this.api, this.mobile,
      {this.ndsProfile = 'balanced',
      this.auxiliary = const {},
      this.arcadeCore,
      this.autoStart = true,
      this.television = false,
      this.nativeGamepad = false,
      this.mameDriver,
      this.fastTelevision = true,
      this.tvVsync = true});
  final String id;
  final Json game;
  final File rom;
  final GameClubApi api;
  final bool mobile;
  final String ndsProfile;
  final Map<String, File> auxiliary;
  final String? arcadeCore;
  final bool autoStart;
  final bool television;
  final bool nativeGamepad;
  final String? mameDriver;
  final bool fastTelevision;
  final bool tvVsync;
}

class PlayerHost {
  PlayerHost(this.directory);
  final Directory directory;
  HttpServer? server;
  final sessions = <String, PlayerSession>{};
  final assetLocks = <String, Future<File>>{};
  GameClubApi? assetApi;

  static const port = 43871;
  static const version = '4.2.3';

  Future<void> start({int listenPort = port}) async {
    if (server != null) return;
    await directory.create(recursive: true);
    try {
      server = await HttpServer.bind(InternetAddress.loopbackIPv4, listenPort);
    } on SocketException {
      throw Exception(
          'El reproductor local está ocupado. Cierra otra instancia de GameClub y vuelve a intentarlo.');
    }
    server!.listen(handle);
  }

  Uri open(Json game, File rom, GameClubApi api,
      {required bool mobile,
      String ndsProfile = 'balanced',
      Map<String, File> auxiliary = const {},
      String? arcadeCore,
      bool autoStart = true,
      bool television = false,
      bool nativeGamepad = false,
      String? mameDriver,
      bool fastTelevision = true,
      bool tvVsync = true}) {
    if (arcadeCore == 'mame_web' &&
        !{'nbmj8688', 'highvdeo', 'caswin'}.contains(mameDriver)) {
      throw Exception('Controlador MAME web no disponible');
    }
    if (arcadeCore != null &&
        (game['system_id'] != 'mame' || !arcadeCores.contains(arcadeCore))) {
      throw Exception('Núcleo arcade no disponible');
    }
    final random = Random.secure();
    final id = List.generate(
            24, (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'))
        .join();
    sessions[id] = PlayerSession(id, game, rom, api, mobile,
        ndsProfile: ndsProfile,
        auxiliary: auxiliary,
        arcadeCore: arcadeCore,
        autoStart: autoStart,
        television: television,
        nativeGamepad: nativeGamepad,
        mameDriver: mameDriver,
        fastTelevision: fastTelevision,
        tvVsync: tvVsync);
    assetApi = api;
    return Uri.parse('http://127.0.0.1:${server!.port}/session/$id/play');
  }

  void release(Uri uri) => sessions.remove(uri.pathSegments[1]);

  Future<void> close() async {
    await server?.close(force: true);
    server = null;
    sessions.clear();
  }

  Future<File> asset(String relative) {
    return assetLocks.putIfAbsent(
        relative,
        () => fetchAsset(relative).whenComplete(() {
              assetLocks.remove(relative);
            }));
  }

  Future<File> fetchAsset(String relative) async {
    if (!RegExp(r'^[a-zA-Z0-9_./-]{1,240}$').hasMatch(relative) ||
        relative
            .split('/')
            .any((part) => part.isEmpty || part.startsWith('.'))) {
      throw Exception('Ruta del motor inválida');
    }
    final file = File(p.joinAll(
        [directory.path, 'emulatorjs-$version', ...relative.split('/')]));
    if (await file.exists()) return file;
    final api = assetApi;
    if (api == null) throw Exception('No hay una sesión de juego activa');
    await file.parent.create(recursive: true);
    final temporary = File('${file.path}.part');
    try {
      final endpoint = relative.startsWith('mame-web/')
          ? '/api/player/$relative'
          : '/api/player/assets/$relative';
      await api.dio.download(endpoint, temporary.path,
          options: Options(receiveTimeout: const Duration(minutes: 3)));
      await temporary.rename(file.path);
    } finally {
      if (await temporary.exists()) await temporary.delete();
    }
    return file;
  }

  Future<void> handle(HttpRequest request) async {
    final response = request.response;
    response.headers.set('Cross-Origin-Opener-Policy', 'same-origin');
    response.headers.set('Cross-Origin-Embedder-Policy', 'require-corp');
    response.headers.set('Cross-Origin-Resource-Policy', 'same-origin');
    response.headers.set('X-Content-Type-Options', 'nosniff');
    try {
      final parts = request.uri.pathSegments;
      final session = parts.length >= 3 && parts[0] == 'session'
          ? sessions[parts[1]]
          : null;
      if (request.method == 'POST' &&
          session?.arcadeCore == 'mame_web' &&
          parts[2] == 'mame-save') {
        final bytes = BytesBuilder(copy: false);
        await for (final chunk in request) {
          bytes.add(chunk);
          if (bytes.length > 32 * 1024 * 1024) {
            throw Exception('Guardado demasiado grande');
          }
        }
        final data = jsonDecode(utf8.decode(bytes.takeBytes())) as Map;
        final archive = Archive();
        for (final entry in data.entries) {
          final name = entry.key as String;
          if (!validMameSavePath(name)) {
            throw Exception('Ruta de guardado inválida');
          }
          final content = base64Decode(entry.value as String);
          archive.addFile(ArchiveFile(name, content.length, content));
        }
        final file = battery(session!);
        await file.parent.create(recursive: true);
        final temporary = File('${file.path}.part');
        await temporary.writeAsBytes(ZipEncoder().encode(archive), flush: true);
        await temporary.rename(file.path);
        response.statusCode = 204;
      } else if (request.method == 'POST' &&
          session != null &&
          parts[2] == 'battery') {
        final relative = request.uri.queryParameters['path'] ?? '';
        if (relative.isEmpty ||
            relative.length > 300 ||
            relative.startsWith('/') ||
            relative.contains('\\') ||
            relative.contains(':') ||
            relative.runes.any((value) => value < 32) ||
            relative.split('/').any((part) => {'', '.', '..'}.contains(part))) {
          response.statusCode = 422;
        } else {
          final bytes = BytesBuilder(copy: false);
          await for (final chunk in request) {
            bytes.add(chunk);
            if (bytes.length > 32 * 1024 * 1024) {
              throw Exception('Partida demasiado grande');
            }
          }
          final archive = Archive()
            ..addFile(ArchiveFile(relative, bytes.length, bytes.takeBytes()));
          final file = battery(session);
          await file.parent.create(recursive: true);
          final temporary = File('${file.path}.part');
          await temporary.writeAsBytes(ZipEncoder().encode(archive),
              flush: true);
          await temporary.rename(file.path);
          response.statusCode = 204;
        }
      } else if (!{'GET', 'HEAD'}.contains(request.method)) {
        response.statusCode = 405;
      } else if (request.uri.path.startsWith('/engine/')) {
        final file = await asset(request.uri.path.substring('/engine/'.length));
        response.headers.contentType = contentType(file.path);
        response.headers
            .set('Cache-Control', 'public, max-age=31536000, immutable');
        response.contentLength = await file.length();
        if (request.method == 'GET') await response.addStream(file.openRead());
      } else {
        if (session == null) {
          response.statusCode = 404;
        } else if (parts[2] == 'play') {
          response.headers.contentType = ContentType.html;
          response.headers.set('Cache-Control', 'no-store');
          response.write(session.arcadeCore == 'mame_web'
              ? mameWebHtml(session)
              : playerHtml(session,
                  hasBattery: await battery(session).exists()));
        } else if (parts[2] == 'mame-save' &&
            session.arcadeCore == 'mame_web') {
          final data = <String, String>{};
          final file = battery(session);
          if (await file.exists()) {
            final archive = ZipDecoder().decodeBytes(await file.readAsBytes());
            for (final entry in archive.files) {
              if (entry.isFile && validMameSavePath(entry.name)) {
                data[entry.name] = base64Encode(entry.content);
              }
            }
          }
          response.headers.contentType = ContentType.json;
          response.write(jsonEncode(data));
        } else if (parts[2] == 'battery.zip' &&
            await battery(session).exists()) {
          final file = battery(session);
          response.headers.contentType = ContentType('application', 'zip');
          response.headers.set('Cache-Control', 'no-store');
          response.contentLength = await file.length();
          await response.addStream(file.openRead());
        } else if (parts[2] == 'aux' && parts.length >= 4) {
          final file = session.auxiliary[parts.skip(3).join('/')];
          if (file == null) {
            response.statusCode = 404;
          } else {
            response.headers.contentType = ContentType.binary;
            response.contentLength = await file.length();
            if (request.method == 'GET') {
              await response.addStream(file.openRead());
            }
          }
        } else if (parts[2] == 'rom') {
          response.headers.contentType = ContentType.binary;
          response.headers.set('Cache-Control', 'private, max-age=86400');
          response.contentLength = await session.rom.length();
          if (request.method == 'GET') {
            await response.addStream(session.rom.openRead());
          }
        } else {
          response.statusCode = 404;
        }
      }
    } catch (_) {
      try {
        response.statusCode = 502;
        response.write('No se pudo cargar el recurso del reproductor.');
      } catch (_) {}
    } finally {
      try {
        await response.close();
      } catch (_) {}
    }
  }

  static ContentType contentType(String filename) {
    switch (p.extension(filename)) {
      case '.js':
        return ContentType('application', 'javascript', charset: 'utf-8');
      case '.css':
        return ContentType('text', 'css', charset: 'utf-8');
      case '.json':
        return ContentType.json;
      case '.wasm':
        return ContentType('application', 'wasm');
      case '.png':
        return ContentType('image', 'png');
      case '.svg':
        return ContentType('image', 'svg+xml');
      default:
        return ContentType.binary;
    }
  }

  static bool validMameSavePath(String name) =>
      name.length <= 300 &&
      RegExp(r'^(nvram|cfg|sta)/[a-zA-Z0-9_./-]+$').hasMatch(name) &&
      !name.split('/').any((part) => {'', '.', '..'}.contains(part));

  File battery(PlayerSession session) {
    final library = session.api.dio.options.baseUrl
        .replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_');
    return File(p.joinAll([
      directory.path,
      'saves',
      library,
      session.game['id'] as String,
      if (session.game['system_id'] == 'mame')
        session.arcadeCore ?? 'mame2003_plus',
      'battery.zip'
    ]));
  }

  static String playerHtml(PlayerSession session, {bool hasBattery = false}) {
    final game = session.game;
    final core = session.arcadeCore ?? integratedCores[game['system_id']];
    if (core == null) throw Exception('Sistema sin motor integrado');
    String js(Object? value) => jsonEncode(value).replaceAll('<', r'\u003c');
    final id = game['id'] as String;
    final numericId = int.parse(id.substring(0, min(12, id.length)), radix: 16);
    final nds = game['system_id'] == 'nds';
    final arcade = game['system_id'] == 'mame';
    final fast = nds && session.ndsProfile == 'fast';
    final profileId =
        {'balanced': 0, 'fast': 1, 'quality': 2}[session.ndsProfile] ?? 0;
    return '''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<style>html,body,#game{width:100%;height:100%;margin:0;background:#10111c;overflow:hidden}body{touch-action:none}.ejs_menu_bar,.ejs_start_button{display:none!important}
${session.television ? '.ejs_virtualGamepad_parent,.ejs_virtualGamepad{display:none!important}' : ''}</style>
</head><body><div id="game"></div><script>
const send = (event, message) => {
  const data = JSON.stringify({event, message, session:${js(session.id)}});
  if (window.GameClub) window.GameClub.postMessage(data);
  else if (window.chrome && window.chrome.webview) window.chrome.webview.postMessage(data);
};
window.gameclubExit = async () => {
  if (window.gameclubLeaving) return;
  window.gameclubLeaving = true;
  try {
    // Adaptador de guardado para EmulatorJS 4.2.3: hay que sincronizar IDBFS
    // antes de que su manejador de salida desmonte el directorio de partidas.
    const emulator = window.EJS_emulator;
    if (emulator && emulator.started && emulator.gameManager) {
      await persistBattery();
      emulator.gameManager.saveSaveFiles();
      await new Promise((resolve,reject) => emulator.gameManager.FS.syncfs(false,
        error => error ? reject(error) : resolve()));
    }
    window.dispatchEvent(new Event('beforeunload'));
    send('exit', '');
  } catch (error) {
    window.gameclubLeaving = false;
    send('save-error', 'No se pudo guardar la partida. Vuelve a intentar cerrar el juego.');
  }
};
let batterySaving = null;
async function persistBattery() {
  if (batterySaving) await batterySaving;
  const operation = (async () => {
    const manager = window.EJS_emulator && window.EJS_emulator.gameManager;
    if (!manager || !window.EJS_emulator.started) return;
    const bytes = manager.getSaveFile();
    if (!bytes || !bytes.length) return;
    const path = manager.getSaveFilePath();
    if (!path.startsWith('/data/saves/')) return;
    const response = await fetch(${js('/session/${session.id}/battery')}+'?path='+encodeURIComponent(path.slice('/data/saves/'.length)),
      {method:'POST',headers:{'Content-Type':'application/octet-stream'},body:new Uint8Array(bytes)});
    if (!response.ok) throw new Error('No se pudo guardar la partida local');
  })();
  batterySaving = operation;
  try { await operation; } finally { if (batterySaving === operation) batterySaving = null; }
}
window.addEventListener('error', () => send('error', 'El motor encontró un error al cargar el juego.'));
window.addEventListener('unhandledrejection', () => send('error', 'No se pudo preparar el motor. Comprueba la conexión con la Raspberry.'));
${session.nativeGamepad ? nativeGamepadJavascript(analogConsole: game['system_id'] == 'n64') : ''}
window.EJS_player = '#game';
window.EJS_core = ${js(core)};
window.EJS_controlScheme = ${js(game['system_id'] == 'gbc' ? 'gb' : game['system_id'])};
window.EJS_gameUrl = ${js('/session/${session.id}/rom/${Uri.encodeComponent(game['filename'] as String)}')};
window.EJS_gameName = ${js('gameclub_$id${arcade ? '_$core' : ''}')};
window.EJS_gameID = ${arcade ? numericId * 4 + arcadeCores.toList().indexOf(core) : nds ? numericId * 3 + profileId : numericId};
window.EJS_pathtodata = '/engine/';
window.EJS_externalFiles = ${js({
          if (hasBattery)
            '/gameclub-battery/': '/session/${session.id}/battery.zip',
          for (final entry in session.auxiliary.entries)
            '/${arcade ? 'roms/' : ''}${entry.key}':
                '/session/${session.id}/aux/${entry.key.split('/').map(Uri.encodeComponent).join('/')}'
        })};
window.EJS_language = 'es-ES';
window.EJS_disableAutoLang = true;
window.EJS_color = '#8c7aff';
window.EJS_startOnLoaded = true;
const parallelNds = ${fast ? 'true' : 'false'} && window.crossOriginIsolated && typeof SharedArrayBuffer === 'function';
window.EJS_threads = parallelNds;
window.EJS_defaultOptions = {'save-state-location':'browser','save-save-interval':'30'
  ${nds ? """,
   'desmume_pointer_mouse':'enabled','desmume_pointer_type':'mouse',
  'desmume_internal_resolution':'256x192','desmume_gfx_texture_scaling':'1',
  'desmume_frameskip':${js(fast ? '1' : '0')},
  'desmume_advanced_timing':${js(fast ? 'disabled' : 'enabled')},
  'desmume_gfx_edgemark':${js(fast ? 'disabled' : 'enabled')},
  'desmume_load_to_memory':${js(fast && (game['size'] as int? ?? 0) <= 134217728 ? 'enabled' : 'disabled')},
  'desmume_num_cores':parallelNds ? '2' : '1'
  """ : ''}};
window.EJS_Buttons = {netplay:false,exitEmulation:false,saveSavFiles:false,loadSavFiles:false,
  screenRecord:false,gameclubExit:{custom:true,displayName:'Volver a GameClub',
  icon:'<svg viewBox="0 0 24 24"><path fill="currentColor" d="M20 11H7l5-5-1-1-7 7 7 7 1-1-5-5h13z"/></svg>',callback:window.gameclubExit}};
window.EJS_ready = () => {
  ${session.television && session.fastTelevision ? """
  const tvCfg=EJS_GameManager.prototype.getRetroArchCfg;
  EJS_GameManager.prototype.getRetroArchCfg=function() {
    return tvCfg.call(this)+'video_vsync = ${session.tvVsync}\\nvideo_smooth = false\\naudio_latency = 128\\naudio_out_rate = 32000\\n';
  };
  """ : ''}
  ${arcade ? """
  const originalWrite=EJS_GameManager.prototype.writeFile;
  EJS_GameManager.prototype.writeFile=function(path,data) {
    return originalWrite.call(this,path,data instanceof ArrayBuffer ? new Uint8Array(data) : data);
  };
  const originalCfg=EJS_GameManager.prototype.getRetroArchCfg;
  EJS_GameManager.prototype.getRetroArchCfg=function() {
    return originalCfg.call(this)+'system_directory = "/roms"\\n';
  };
  const originalDownload=EJS_emulator.downloadRom;
  EJS_emulator.downloadRom=async function(...args) {
    await originalDownload.apply(this,args);
    const manager=this.gameManager;
    manager.mkdir('/roms');
    manager.FS.rename('/'+this.fileName,'/roms/'+this.fileName);
    this.fileName='roms/'+this.fileName;
  };
  const originalError = EJS_emulator.startGameError.bind(EJS_emulator);
  const originalWarn=console.warn;
  console.warn=(...args) => {
    if(String(args[0]).includes('Failed to start game')) {
      send('core-failed',args.map(value => value && value.stack ? value.stack : String(value)).join(' ').slice(0,1800));
    }
    originalWarn.apply(console,args);
  };
  EJS_emulator.startGameError = message => { originalError(message); send('core-failed',String(message)); };
  EJS_emulator.on('start-clicked', () => send('core-loading',''));
  const originalInit=EJS_emulator.initModule;
  EJS_emulator.initModule=function(...args) {
    const runtime=window.EJS_Runtime;
    window.EJS_Runtime=options => {
      const watch=original => message => {
        if(original) original(message);
        if(/failed to load content|rom loading failed|roms couldn't be loaded|romset is (unknown|invalid)|required files are missing|ROM with name.*is missing|failed initializing driver|romset is known but marked as not working/i.test(String(message))) {
          send('core-failed',String(message).slice(0,1500));
        }
      };
      return runtime({...options,print:watch(options.print),printErr:watch(options.printErr)});
    };
    try { return originalInit.apply(this,args); } finally { window.EJS_Runtime=runtime; }
  };
  """ : ''}
  ${hasBattery ? """
  // En 4.2.3 los archivos externos se cargan antes de montar /data/saves.
  // Copiamos la batería al montaje restaurado antes de que arranque la ROM.
  const originalMount = EJS_GameManager.prototype.mountFileSystems;
  EJS_GameManager.prototype.mountFileSystems = async function(...args) {
    await originalMount.apply(this,args);
    const fs = this.FS;
    const copy = (source,destination) => {
      try { fs.mkdir(destination); } catch (_) {}
      for (const name of fs.readdir(source)) {
        if (name === '.' || name === '..') continue;
        const from=source+'/'+name, to=destination+'/'+name;
        if (fs.isDir(fs.stat(from).mode)) copy(from,to);
        else fs.writeFile(to,fs.readFile(from));
      }
    };
    if (fs.analyzePath('/gameclub-battery').exists) copy('/gameclub-battery','/data/saves');
  };
  """ : ''}
  send('ready', 'Pulsa Iniciar juego para comenzar.');
};
window.EJS_onGameStart = () => {
  ${nds && session.mobile ? ndsTouchJavascript : ''}
  ${session.television ? """
  window.gameclubPresentationFrames=0;
  const presentationTick=()=>{if(window.gameclubLeaving)return;window.gameclubPresentationFrames++;requestAnimationFrame(presentationTick);};
  requestAnimationFrame(presentationTick);
  """ : ''}
  ${session.television ? 'EJS_emulator.gameManager.setVSync(${session.tvVsync});' : ''}
  ${session.nativeGamepad ? 'window.gameclubRefreshControllers?.();' : ''}
  ${arcade ? """
  async function confirmBoot(manager) {
    try {
      if(${js(core)}==='fbneo') {
        const bytes=await Promise.race([manager.screenshot(),new Promise((_,reject)=>setTimeout(()=>reject(new Error('No se pudo comprobar el vídeo')),5000))]);
        const bitmap=await createImageBitmap(new Blob([bytes],{type:'image/png'}));
        if(bitmap.width===640 && bitmap.height===480) {
          const canvas=document.createElement('canvas');canvas.width=112;canvas.height=14;
          const context=canvas.getContext('2d');context.drawImage(bitmap,0,0);
          let hash=2166136261;
          for(const value of context.getImageData(0,0,112,14).data) hash=Math.imul(hash^value,16777619)>>>0;
          // Cabecera exacta «FBNeo Error» del núcleo fijado a EmulatorJS 4.2.3.
          if(hash===35096051) {bitmap.close();send('core-failed','FinalBurn Neo muestra un error de romset o BIOS, no un juego iniciado.');return;}
        }
        bitmap.close();
      }
      if(!window.gameclubLeaving) send('started',${js(core)});
    } catch(error) {send('core-failed',String(error));}
  }
  let attempts=0, previous=-1, advancing=0;
  const probe=setInterval(() => {
    if(window.gameclubLeaving) {clearInterval(probe);return;}
    try {
      const manager=EJS_emulator.gameManager;
      const frames=manager.functions.getFrameNum();
      if(frames>previous && previous>=0) advancing++;
      previous=frames;
      if(EJS_emulator.failedToStart) {clearInterval(probe);send('core-failed','El núcleo rechazó el juego');return;}
      if(advancing>=3) {clearInterval(probe);confirmBoot(manager);return;}
    } catch (_) {}
    if(++attempts>=30) {clearInterval(probe);send('core-failed','El núcleo no produjo fotogramas de emulación '+JSON.stringify({frames:previous,paused:EJS_emulator.paused,hidden:document.hidden,focus:document.hasFocus(),started:EJS_emulator.started}));}
  },500);
  """ : "send('started', '');"}
  ${nds || session.television ? """
  let previousFrames = EJS_emulator.gameManager.functions.getFrameNum(), previousTime = performance.now(),previousPresentation=window.gameclubPresentationFrames||0;
  setInterval(() => {
    if (window.gameclubLeaving || EJS_emulator.paused) { previousTime=performance.now();previousFrames=EJS_emulator.gameManager.functions.getFrameNum();return; }
    const now=performance.now(), frames=EJS_emulator.gameManager.functions.getFrameNum();
    const fps=(frames-previousFrames)*1000/(now-previousTime);
    const presentation=window.gameclubPresentationFrames||0;
    const presentationFps=(presentation-previousPresentation)*1000/(now-previousTime);previousPresentation=presentation;
    previousTime=now;previousFrames=frames;
    send('performance',JSON.stringify({fps:Math.round(fps),presentationFps:Math.round(presentationFps),speed:Math.round(fps/60*100),parallel:parallelNds,system:${js(game['system_id'])},profile:${js(session.television ? (session.fastTelevision ? 'tv-fast' : 'tv-balanced') : session.ndsProfile)}}));
  },3000);
  """ : ''}
  setInterval(() => {
    if (!window.gameclubLeaving) persistBattery().catch(() => send('error','No se pudo actualizar el guardado local.'));
  },30000);
};
</script><script src="/engine/loader.js"></script></body></html>''';
  }
}
