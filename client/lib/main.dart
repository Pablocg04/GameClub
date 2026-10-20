import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'integrated_player.dart';
import 'native_console.dart';
import 'game_files.dart';
import 'pinball_player.dart';
import 'player_host.dart';
import 'scrape_tools.dart';
import 'screenshots_gallery.dart';
import 'television.dart';
import 'native_arcade.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await DevicePlatform.initialize();
  runApp(const GameClubApp());
}

class GameClubApp extends StatelessWidget {
  const GameClubApp({super.key, this.apiOverride, this.television});

  final GameClubApi? apiOverride;
  final bool? television;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<bool>(
      valueListenable: DevicePlatform.gamepadConnected,
      builder: (context, gamepad, _) => TelevisionScope(
          enabled: television ?? (DevicePlatform.television || gamepad),
          child: MaterialApp(
            title: 'GameClub',
            debugShowCheckedModeBanner: false,
            shortcuts: {
              ...WidgetsApp.defaultShortcuts,
              const SingleActivator(LogicalKeyboardKey.select):
                  const ActivateIntent(),
              const SingleActivator(LogicalKeyboardKey.gameButtonA):
                  const ActivateIntent(),
              const SingleActivator(LogicalKeyboardKey.gameButtonB):
                  const TelevisionBackIntent(),
              const SingleActivator(LogicalKeyboardKey.escape):
                  const TelevisionBackIntent(),
            },
            actions: {
              TelevisionBackIntent:
                  CallbackAction<TelevisionBackIntent>(onInvoke: (_) {
                final focusContext =
                    FocusManager.instance.primaryFocus?.context;
                if (focusContext != null) {
                  Navigator.maybeOf(focusContext)?.maybePop();
                }
                return null;
              })
            },
            theme: ThemeData(
              brightness: Brightness.dark,
              colorScheme: ColorScheme.fromSeed(
                  seedColor: const Color(0xff8c7aff),
                  brightness: Brightness.dark),
              scaffoldBackgroundColor: const Color(0xff10111c),
              useMaterial3: true,
            ),
            home: LibraryPage(apiOverride: apiOverride),
          )));
}

class LibraryPage extends StatefulWidget {
  const LibraryPage({super.key, this.apiOverride});

  final GameClubApi? apiOverride;

  @override
  State<LibraryPage> createState() => _LibraryPageState();
}

class _LibraryPageState extends State<LibraryPage> {
  GameClubApi api = GameClubApi('http://192.168.0.47:8001', '');
  final server = TextEditingController(text: 'http://192.168.0.47:8001');
  final token = TextEditingController();
  List<Json> systems = [], games = [];
  Json settings = {};
  Map<String, String> executables = {};
  String? selectedSystem;
  String query = '', status = '';
  String? uploadStatus;
  int tab = 0, revision = 0;
  bool loading = true, busy = false, showEmpty = false;
  bool pinballOnly = false;
  double? progress;
  PlayerHost? playerHost;
  String ndsProfile = Platform.isAndroid ? 'fast' : 'balanced';
  final tvGridKey = GlobalKey<TelevisionGridState>();
  final tvNav =
      List.generate(3, (index) => FocusNode(debugLabel: 'Menú TV $index'));
  final tvFilter = FocusNode(debugLabel: 'Filtro TV');
  final tvSearch = FocusNode(debugLabel: 'Buscar TV');
  final tvServer = FocusNode(debugLabel: 'Servidor TV');
  final tvPerformance = FocusNode(debugLabel: 'Rendimiento TV');

  @override
  void initState() {
    super.initState();
    initialize();
  }

  Future<void> initialize() async {
    final prefs = await SharedPreferences.getInstance();
    server.text = prefs.getString('server') ?? server.text;
    token.text = prefs.getString('token') ?? '';
    ndsProfile = prefs.getString('ndsProfile') ?? ndsProfile;
    DevicePlatform.fastTelevision = prefs.getBool('fastTelevision') ?? true;
    DevicePlatform.directTelevisionView =
        prefs.getBool('directTelevisionView') ?? true;
    DevicePlatform.tvVsync = prefs.getBool('tvVsync') ?? true;
    final orientation = prefs.getString('mobileOrientation') ?? 'auto';
    DevicePlatform.mobileOrientation =
        {'auto', 'portrait', 'landscape'}.contains(orientation)
            ? orientation
            : 'auto';
    DevicePlatform.touchScale =
        (prefs.getDouble('touchScale') ?? 1).clamp(.8, 1.35);
    if (!{'fast', 'balanced'}.contains(ndsProfile)) {
      ndsProfile = Platform.isAndroid ? 'fast' : 'balanced';
    }
    executables = Map<String, String>.from(
        jsonDecode(prefs.getString('executables') ?? '{}') as Map);
    api = widget.apiOverride ?? GameClubApi(server.text, token.text);
    await reload();
  }

  @override
  void dispose() {
    for (final node in tvNav) {
      node.dispose();
    }
    tvFilter.dispose();
    tvSearch.dispose();
    tvServer.dispose();
    tvPerformance.dispose();
    server.dispose();
    token.dispose();
    api.dio.close(force: true);
    playerHost?.close();
    super.dispose();
  }

  void notify(String text) {
    if (!mounted) return;
    final detailed = text.length > 240 || text.split('\n').length > 4;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(detailed ? text.split('\n').first : text),
        action: detailed
            ? SnackBarAction(
                label: 'Detalles',
                onPressed: () => showDialog<void>(
                    context: context,
                    builder: (context) => AlertDialog(
                            title: const Text('Diagnóstico del juego'),
                            scrollable: true,
                            content: SelectableText(text),
                            actions: [
                              TextButton(
                                  autofocus: true,
                                  onPressed: () => Navigator.pop(context),
                                  child: const Text('Cerrar'))
                            ])))
            : null));
  }

  Future<void> reload() async {
    if (!mounted) return;
    final request = ++revision;
    setState(() {
      loading = true;
      status = '';
    });
    try {
      final results = await Future.wait([
        api.list('/api/systems', {'include_empty': true}),
        api.list('/api/games', {
          if (selectedSystem != null) 'system_id': selectedSystem,
          'favorites': tab == 1,
          if (pinballOnly) 'category': 'pinball'
        }),
      ]);
      final config = await api.dio.get<Json>('/api/settings');
      if (!mounted || request != revision) return;
      setState(() {
        systems = results[0];
        games = results[1];
        settings = config.data!;
        loading = false;
      });
    } catch (error) {
      if (!mounted || request != revision) return;
      setState(() {
        status = GameClubApi.error(error);
        loading = false;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && TelevisionScope.of(context)) tvNav[tab].requestFocus();
      });
    }
  }

  Future<void> perform(Future<void> Function() action) async {
    if (busy) return;
    setState(() {
      busy = true;
      progress = null;
    });
    try {
      await action();
    } catch (error) {
      notify(GameClubApi.error(error));
    } finally {
      if (mounted) {
        setState(() {
          busy = false;
          progress = null;
          uploadStatus = null;
        });
      }
    }
  }

  void transferProgress(int sent, int total) {
    if (mounted) {
      setState(() {
        progress = total > 0 ? sent / total : null;
      });
    }
  }

  Future<String?> chooseSystem(List<String> filenames) async {
    final extensions =
        filenames.map((name) => p.extension(name).toLowerCase()).toSet();
    final matches = systems
        .where((s) =>
            extensions.every((ext) => (s['extensions'] as List).contains(ext)))
        .toList();
    String? value =
        matches.length == 1 ? matches.first['id'] as String : selectedSystem;
    return showDialog<String>(
        context: context,
        builder: (context) => StatefulBuilder(
              builder: (context, update) => AlertDialog(
                scrollable: true,
                title: Text(filenames.length == 1
                    ? 'Añadir juego'
                    : 'Añadir ${filenames.length} juegos'),
                content: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(filenames.take(4).join('\n')),
                      if (filenames.length > 4)
                        Text('Y ${filenames.length - 4} archivos más'),
                      const SizedBox(height: 16),
                      DropdownButtonFormField<String>(
                        initialValue: value,
                        isExpanded: true,
                        decoration: const InputDecoration(
                            labelText: 'Consola de destino'),
                        items: systems
                            .map((s) => DropdownMenuItem(
                                value: s['id'] as String,
                                child: Text(s['name'] as String)))
                            .toList(),
                        onChanged: (id) => update(() {
                          value = id;
                        }),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                          'Todos los archivos seleccionados se guardarán en la carpeta de esta consola.'),
                      if (value == 'vpinball') ...[
                        const SizedBox(height: 12),
                        const Text(
                            'Un ZIP/VPXZ por mesa: incluye el .vpx y sus ROMs ZIP (también la ROM padre si la necesita). Puedes añadir el panel .directb2s, música y el script standalone. No subas las ROMs ZIP por separado. Un .vpx suelto solo sirve para mesas autosuficientes.'),
                      ],
                    ]),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Cancelar')),
                  FilledButton(
                      onPressed: value == null
                          ? null
                          : () => Navigator.pop(context, value),
                      child: const Text('Subir')),
                ],
              ),
            ));
  }

  Future<void> addGames() async {
    final result = await FilePicker.platform.pickFiles(allowMultiple: true);
    if (result == null || result.files.isEmpty || !mounted) return;
    if (result.files.any((file) => file.path == null)) {
      notify(
          'No se puede acceder a uno de los archivos seleccionados. Selecciona archivos disponibles en el dispositivo.');
      return;
    }
    final system =
        await chooseSystem(result.files.map((file) => file.name).toList());
    if (system == null || !mounted) return;
    await perform(() async {
      int uploaded = 0;
      final errors = <String>[];
      for (var index = 0; index < result.files.length; index++) {
        if (!mounted) return;
        final file = result.files[index];
        setState(() {
          uploadStatus =
              'Subiendo ${index + 1} de ${result.files.length}: ${file.name}';
        });
        try {
          await api.upload('/api/systems/$system/upload', file.path!, file.name,
              (sent, total) {
            if (mounted) {
              setState(() {
                progress = total > 0
                    ? (index + sent / total) / result.files.length
                    : null;
              });
            }
          });
          uploaded++;
        } catch (error) {
          errors.add('${file.name}: ${GameClubApi.error(error)}');
        }
      }
      await reload();
      notify('$uploaded de ${result.files.length} juegos añadidos a $system');
      if (errors.isNotEmpty && mounted) {
        await showDialog<void>(
            context: context,
            builder: (context) => AlertDialog(
                  title: const Text('Archivos no añadidos'),
                  content:
                      SingleChildScrollView(child: Text(errors.join('\n\n'))),
                  actions: [
                    TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Aceptar'))
                  ],
                ));
      }
    });
  }

  Future<void> addSystem() async {
    final id = TextEditingController(),
        name = TextEditingController(),
        extensions = TextEditingController();
    final accepted = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
              title: const Text('Añadir consola'),
              content: SingleChildScrollView(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                TextField(
                    controller: name,
                    decoration:
                        const InputDecoration(labelText: 'Nombre visible')),
                TextField(
                    controller: id,
                    decoration: const InputDecoration(
                        labelText: 'Carpeta / identificador',
                        hintText: 'solo minusculas, números, - y _')),
                TextField(
                    controller: extensions,
                    decoration: const InputDecoration(
                        labelText: 'Extensiones separadas por espacios',
                        hintText: '.rom .zip')),
                const SizedBox(height: 12),
                const Text(
                    'Registra el sistema en la biblioteca. El emulador se configura por dispositivo.'),
              ])),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Cancelar')),
                FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Añadir')),
              ],
            ));
    if (accepted == true && mounted) {
      await perform(() async {
        await api.dio.post('/api/systems', data: {
          'id': id.text.trim(),
          'name': name.text.trim(),
          'extensions':
              extensions.text.trim().toLowerCase().split(RegExp(r'\s+'))
        });
        await reload();
        notify('Consola añadida');
      });
    }
    id.dispose();
    name.dispose();
    extensions.dispose();
  }

  Future<void> scrape(Json game) async {
    await perform(() async {
      const provider = 'auto';
      var candidates = await api
          .list('/api/games/${game['id']}/scrape', {'provider': provider});
      if (!mounted) return;
      final query = TextEditingController(text: game['title'] as String);
      bool searching = false;
      final id = await showDialog<String>(
          context: context,
          builder: (context) => StatefulBuilder(
              builder: (context, update) => AlertDialog(
                    title: const Text('Selecciona el juego correcto'),
                    scrollable: true,
                    content: SizedBox(
                        width: 480,
                        height: 400,
                        child: Column(children: [
                          Row(children: [
                            Expanded(
                                child: TextField(
                                    controller: query,
                                    decoration: const InputDecoration(
                                        labelText: 'Buscar por título'))),
                            IconButton(
                                tooltip: 'Buscar',
                                onPressed: searching
                                    ? null
                                    : () async {
                                        update(() {
                                          searching = true;
                                        });
                                        try {
                                          final result = await api.list(
                                              '/api/games/${game['id']}/scrape',
                                              {
                                                'provider': provider,
                                                'q': query.text.trim()
                                              });
                                          if (context.mounted) {
                                            update(() {
                                              candidates = result;
                                            });
                                          }
                                        } catch (error) {
                                          notify(GameClubApi.error(error));
                                        } finally {
                                          if (context.mounted) {
                                            update(() {
                                              searching = false;
                                            });
                                          }
                                        }
                                      },
                                icon: const Icon(Icons.search))
                          ]),
                          if (searching) const LinearProgressIndicator(),
                          if (candidates.isEmpty)
                            const Padding(
                                padding: EdgeInsets.all(16),
                                child: Text(
                                    'Sin coincidencias en Libretro, LaunchBox ni GameTDB. Prueba otro título o usa Subir carátula en la ficha.')),
                          Expanded(
                              child: ListView(
                                  children: candidates
                                      .map((candidate) => ListTile(
                                            title: Text(
                                                candidate['title'] as String),
                                            subtitle: Text(
                                                candidate['description']
                                                    as String,
                                                maxLines: 2,
                                                overflow:
                                                    TextOverflow.ellipsis),
                                            onTap: () => Navigator.pop(context,
                                                candidate['id'] as String),
                                          ))
                                      .toList()))
                        ])),
                    actions: [
                      TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('Cancelar'))
                    ],
                  )));
      query.dispose();
      if (id == null) return;
      await api.dio.post('/api/games/${game['id']}/scrape',
          data: {'provider_id': id, 'provider': provider});
      await reload();
      notify('Carátula actualizada');
    });
  }

  Future<void> manualCover(Json game) async {
    final result = await FilePicker.platform.pickFiles(type: FileType.image);
    if (result == null || result.files.single.path == null || !mounted) return;
    await perform(() async {
      final file = result.files.single;
      await api.upload('/api/games/${game['id']}/cover', file.path!, file.name,
          transferProgress);
      await reload();
      notify('Carátula guardada');
    });
  }

  Future<String> download(Json game) async {
    final documents = await getApplicationDocumentsDirectory();
    final file = GameFiles.location(api, game, documents);
    return (await GameFiles.fetch(api, game, file,
            onProgress: transferProgress))
        .path;
  }

  Future<void> openGame(Json game) async {
    final television = TelevisionScope.of(context);
    await perform(() async {
      if (game['system_id'] == 'vpinball') {
        await PinballPlayer(api, onProgress: (text, value) {
          if (mounted) {
            setState(() {
              uploadStatus = text;
              progress = value;
            });
          }
        }).play(game);
        return;
      }
      if (game['system_id'] == 'mame' ||
          nativeConsoleCores.containsKey(game['system_id'])) {
        void updateProgress(String text, double? value) {
          if (mounted) {
            setState(() {
              uploadStatus = text;
              progress = value;
            });
          }
        }

        if (nativeConsoleCores.containsKey(game['system_id'])) {
          await NativeConsole(api, onProgress: updateProgress).play(game);
          return;
        }
        await NativeArcade(api, onProgress: (text, value) {
          if (mounted) {
            setState(() {
              uploadStatus = text;
              progress = value;
            });
          }
        }).play(game);
        return;
      }
      if (integratedCores.containsKey(game['system_id'])) {
        if (game['system_id'] == 'nds' &&
            p.extension(game['filename'] as String).toLowerCase() == '.dsi') {
          throw Exception(
              'El motor integrado de Nintendo DS utiliza juegos .nds. Los títulos DSi requieren otra integración.');
        }
        final support = await getApplicationSupportDirectory();
        playerHost ??= PlayerHost(Directory(p.join(support.path, 'player')));
        await playerHost!.start();
        final path = await download(game);
        final uri = playerHost!.open(game, File(path), api,
            mobile: Platform.isAndroid,
            ndsProfile: ndsProfile,
            television: television,
            fastTelevision: DevicePlatform.fastTelevision,
            tvVsync: DevicePlatform.tvVsync,
            nativeGamepad: DevicePlatform.nativeGamepads);
        try {
          if (mounted) {
            final route = MaterialPageRoute<void>(
                builder: (_) =>
                    IntegratedPlayer(uri: uri, title: game['title'] as String));
            await Navigator.of(context).push(route);
            await route.completed;
          }
        } finally {
          playerHost!.release(uri);
        }
        return;
      }
      final extension = p.extension(game['filename'] as String).toLowerCase();
      if ({'.cue', '.m3u', '.cia', '.vpk', '.zip', '.7z', '.rpx'}
          .contains(extension)) {
        throw Exception(
            'Este formato necesita preparar varios archivos, extraerlos o instalarlos. El lanzamiento de este formato se añadirá en la siguiente fase.');
      }
      final path = await download(game);
      final executable = executables[game['system_id']] ?? '';
      if (Platform.isWindows && executable.isNotEmpty) {
        if (!await File(executable).exists()) {
          throw Exception(
              'No se encuentra el emulador. Revisa su ruta en Ajustes.');
        }
        await Process.start(executable, [path],
            workingDirectory: p.dirname(executable));
      } else {
        final result = await OpenFilex.open(path);
        if (result.type != ResultType.done) {
          throw Exception(
              'Juego descargado. No se encontró una aplicación que pueda abrirlo: ${result.message}');
        }
      }
    });
    if (television && mounted) {
      try {
        await DevicePlatform.channel.invokeMethod<void>('libraryActive');
      } on MissingPluginException {/* Pruebas. */} on PlatformException {
        /* Actividad cerrada. */
      }
      if (mounted) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          if (tab < 2 && tvGridKey.currentState != null) {
            tvGridKey.currentState!.focusSelected();
          } else {
            tvNav[tab].requestFocus();
          }
        });
      }
    }
  }

  void controllerTab(int delta) {
    if (busy) return;
    final next = (tab + delta + 3) % 3;
    SystemChannels.textInput.invokeMethod<void>('TextInput.hide');
    setState(() => tab = next);
    tvNav[next].requestFocus();
    reload();
  }

  void controllerSearch() {
    if (busy || tab == 2) return;
    tvSearch.requestFocus();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && tvSearch.hasFocus) {
        SystemChannels.textInput.invokeMethod<void>('TextInput.show');
      }
    });
  }

  Future<void> detail(Json game) async {
    final action = await showDialog<String>(
        context: context,
        builder: (context) => AlertDialog(
              title: Text(game['title'] as String),
              content: SizedBox(
                  width: 440,
                  child: SingleChildScrollView(
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                        Text(
                            '${game['filename']} · ${formatSize(game['size'] as int)}'),
                        const SizedBox(height: 16),
                        Text((game['description'] as String).isEmpty
                            ? 'Todavía no hay descripción disponible.'
                            : game['description'] as String),
                        const SizedBox(height: 16),
                        Text(game['system_id'] == 'vpinball'
                            ? 'Mesa Visual Pinball + PinMAME. Se juega desde GameClub. Android incluye el motor (Android 13+ ARM64), controles táctiles, mando y menú para continuar o salir.'
                            : (integratedCores.containsKey(game['system_id']) ||
                                    nativeConsoleCores
                                        .containsKey(game['system_id']))
                                ? 'Se juega dentro de GameClub, sin instalar otro emulador. El reproductor incluye controles, menú de ajustes y partidas guardadas locales.'
                                : 'Se ejecuta en tu dispositivo mediante el emulador configurado. Los controles de juego los proporciona ese emulador.'),
                        if (game['system_id'] == 'mame')
                          const Padding(
                              padding: EdgeInsets.only(top: 8),
                              child: Text(
                                  'Arcade nativo: MAME 2003-Plus, MAME 2003, FinalBurn Neo y MAME completo. Arranque directo a pantalla completa, sin WebView. El motor comprueba la compatibilidad final del ROMset.')),
                        if (nativeConsoleCores.containsKey(game['system_id']))
                          const Padding(
                              padding: EdgeInsets.only(top: 8),
                              child: Text(
                                  'Consola nativa: NES con Nestopia UE y Atari 2600 con Stella. Motores incluidos en la app, sin WebView. Start inicia; en Atari actúa como RESET y Select como GAME SELECT.')),
                        const Divider(height: 28),
                        ScreenshotsGallery(
                            api: api, gameId: game['id'] as String),
                      ]))),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context, 'favorite'),
                    child: Text(game['favorite'] == true
                        ? 'Quitar favorito'
                        : 'Favorito')),
                TextButton(
                    onPressed: () => Navigator.pop(context, 'manual'),
                    child: const Text('Subir carátula')),
                TextButton(
                    onPressed: () => Navigator.pop(context, 'scrape'),
                    child: const Text('Buscar carátula')),
                TextButton(
                    onPressed: () => Navigator.pop(context, 'download'),
                    child: const Text('Descargar')),
                FilledButton.icon(
                    autofocus: TelevisionScope.of(context),
                    onPressed: () => Navigator.pop(context, 'play'),
                    icon: const Icon(Icons.play_arrow),
                    label: Text(game['system_id'] == 'vpinball'
                        ? 'Jugar pinball'
                        : (integratedCores.containsKey(game['system_id']) ||
                                nativeConsoleCores
                                    .containsKey(game['system_id']))
                            ? 'Jugar en GameClub'
                            : 'Abrir con emulador')),
              ],
            ));
    if (!mounted) return;
    switch (action) {
      case 'favorite':
        await perform(() async {
          await api.dio.patch('/api/games/${game['id']}',
              data: {'favorite': game['favorite'] != true});
          await reload();
        });
      case 'manual':
        await manualCover(game);
      case 'scrape':
        await scrape(game);
      case 'download':
        await perform(() async {
          final path = await download(game);
          notify('Guardado en $path');
        });
      case 'play':
        await openGame(game);
    }
  }

  static String formatSize(int size) => size >= 1073741824
      ? '${(size / 1073741824).toStringAsFixed(1)} GB'
      : size >= 1048576
          ? '${(size / 1048576).toStringAsFixed(1)} MB'
          : '${(size / 1024).toStringAsFixed(1)} KB';

  Widget cover(Json game) {
    Widget placeholder() => Container(
        color: const Color(0xff25273d),
        alignment: Alignment.center,
        child: const Icon(Icons.videogame_asset_outlined,
            size: 64, color: Color(0xff8c7aff)));
    if (game['cover_url'] == null) return placeholder();
    return Image.network(
        '${api.imageUrl(game['cover_url'] as String)}?v=$revision',
        headers: api.dio.options.headers
            .map((key, value) => MapEntry(key, value.toString())),
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => placeholder());
  }

  Widget libraryView() {
    final tv = TelevisionScope.of(context);
    final visibleSystems = systems
        .where((s) => showEmpty || (s['game_count'] as int) > 0)
        .toList();
    final visibleGames = games
        .where((g) =>
            (g['title'] as String).toLowerCase().contains(query.toLowerCase()))
        .toList();
    return Column(children: [
      Padding(
          padding: const EdgeInsets.all(16),
          child: CallbackShortcuts(
              bindings: tv && MediaQuery.viewInsetsOf(context).bottom == 0
                  ? {
                      const SingleActivator(LogicalKeyboardKey.arrowDown): () =>
                          tvFilter.requestFocus(),
                    }
                  : const {},
              child: TextField(
                focusNode: tv ? tvSearch : null,
                decoration: InputDecoration(
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: IconButton(
                        tooltip: pinballOnly
                            ? 'Quitar filtro de pinball MAME'
                            : 'Pinballs de MAME',
                        isSelected: pinballOnly,
                        icon: const Icon(Icons.sports_baseball_outlined),
                        onPressed: busy
                            ? null
                            : () {
                                setState(() {
                                  pinballOnly = !pinballOnly;
                                  selectedSystem = pinballOnly ? 'mame' : null;
                                  tab = 0;
                                });
                                reload();
                              }),
                    hintText: 'Buscar en la biblioteca',
                    border: OutlineInputBorder()),
                onChanged: (value) => setState(() {
                  query = value;
                }),
              ))),
      if (MediaQuery.viewInsetsOf(context).bottom == 0)
        SizedBox(
            height: 52,
            child: tv
                ? TelevisionFilters(
                    labels: [
                      'Todas',
                      ...visibleSystems
                          .map((s) => '${s['name']} · ${s['game_count']}')
                    ],
                    selected: selectedSystem == null
                        ? 0
                        : visibleSystems
                                .indexWhere((s) => s['id'] == selectedSystem) +
                            1,
                    firstFocus: tvFilter,
                    enabled: !busy,
                    onSelected: (index) {
                      selectedSystem = index == 0
                          ? null
                          : visibleSystems[index - 1]['id'] as String;
                      if (selectedSystem != 'mame') pinballOnly = false;
                      reload();
                    },
                    onDown: () => tvGridKey.currentState?.focusSelected(),
                    onUp: () => tvSearch.requestFocus(),
                    onMenu: () => tvNav[tab].requestFocus(),
                  )
                : ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    children: [
                        Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: ChoiceChip(
                                focusNode: tv ? tvFilter : null,
                                label: const Text('Todas'),
                                selected: selectedSystem == null,
                                onSelected: busy
                                    ? null
                                    : (_) {
                                        selectedSystem = null;
                                        pinballOnly = false;
                                        reload();
                                      })),
                        ...visibleSystems.map((s) => Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: ChoiceChip(
                              label: Text('${s['name']} · ${s['game_count']}'),
                              selected: selectedSystem == s['id'],
                              onSelected: busy
                                  ? null
                                  : (_) {
                                      selectedSystem = s['id'] as String;
                                      if (selectedSystem != 'mame') {
                                        pinballOnly = false;
                                      }
                                      reload();
                                    },
                            ))),
                      ])),
      Expanded(
          child: loading
              ? const Center(child: CircularProgressIndicator())
              : status.isNotEmpty
                  ? emptyState(Icons.wifi_off, status, 'Reintentar', reload)
                  : visibleGames.isEmpty
                      ? emptyState(
                          Icons.sports_esports_outlined,
                          'No hay juegos en esta vista.\nAñade tus ROMs o escanea las carpetas de la Raspberry.',
                          'Añadir juego',
                          addGames)
                      : tv
                          ? TelevisionGrid(
                              key: tvGridKey,
                              identity: '$tab-$selectedSystem-$query',
                              autofocus: !tvNav.any((node) => node.hasFocus) &&
                                  !tvFilter.hasFocus &&
                                  !tvSearch.hasFocus,
                              onMenu: () => tvNav[tab].requestFocus(),
                              onFilters: () => tvFilter.requestFocus(),
                              count: visibleGames.length,
                              builder: (context, index, node, autofocus) =>
                                  gameCard(visibleGames[index],
                                      focusNode: node, autofocus: autofocus))
                          : GridView.builder(
                              padding: const EdgeInsets.all(16),
                              gridDelegate:
                                  const SliverGridDelegateWithMaxCrossAxisExtent(
                                      maxCrossAxisExtent: 220,
                                      mainAxisSpacing: 16,
                                      crossAxisSpacing: 16,
                                      childAspectRatio: 0.66),
                              itemCount: visibleGames.length,
                              itemBuilder: (context, index) {
                                return gameCard(visibleGames[index]);
                              })),
    ]);
  }

  Widget gameCard(Json game, {FocusNode? focusNode, bool autofocus = false}) =>
      FocusGameCard(
          key: ValueKey('game-${game['id']}'),
          focusNode: focusNode,
          autofocus: autofocus,
          onTap: busy ? null : () => detail(game),
          child: Column(children: [
            Expanded(
                child: SizedBox(width: double.infinity, child: cover(game))),
            Padding(
                padding: const EdgeInsets.all(12),
                child: Row(children: [
                  Expanded(
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                        Text(game['title'] as String,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style:
                                const TextStyle(fontWeight: FontWeight.w600)),
                        Text((game['system_id'] as String).toUpperCase(),
                            style: const TextStyle(
                                color: Colors.white54, fontSize: 12)),
                      ])),
                  if (game['favorite'] == true)
                    const Icon(Icons.star, color: Colors.amber, size: 18),
                ])),
          ]));

  Widget emptyState(IconData icon, String text, String label,
          Future<void> Function() action) =>
      Center(
        child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(icon, size: 64, color: const Color(0xff8c7aff)),
              const SizedBox(height: 16),
              Text(text, textAlign: TextAlign.center),
              const SizedBox(height: 20),
              FilledButton(onPressed: busy ? null : action, child: Text(label)),
            ])),
      );

  Future<void> saveConnection() async {
    final uri = Uri.tryParse(server.text.trim());
    if (uri == null ||
        !{'http', 'https'}.contains(uri.scheme) ||
        uri.host.isEmpty ||
        uri.hasQuery ||
        uri.hasFragment) {
      notify('Introduce una dirección como http://192.168.0.47:8001');
      return;
    }
    await perform(() async {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('server', server.text.trim());
      await prefs.setString('token', token.text.trim());
      api.dio.close(force: true);
      api = GameClubApi(server.text.trim(), token.text.trim());
      selectedSystem = null;
      pinballOnly = false;
      await reload();
    });
  }

  Future<void> chooseExecutable(Json system) async {
    final result = await FilePicker.platform
        .pickFiles(type: FileType.custom, allowedExtensions: ['exe']);
    if (result == null || result.files.single.path == null) return;
    executables[system['id'] as String] = result.files.single.path!;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('executables', jsonEncode(executables));
    if (mounted) setState(() {});
  }

  Future<void> setNdsProfile(String value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ndsProfile', value);
    if (mounted) {
      setState(() {
        ndsProfile = value;
      });
    }
  }

  Widget settingsView() {
    final children = <Widget>[
      if (DevicePlatform.mobile) ...[
        const Text('Pantalla y controles del móvil',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(
            initialValue: DevicePlatform.mobileOrientation,
            decoration: const InputDecoration(
                labelText: 'Orientación del juego',
                border: OutlineInputBorder()),
            items: const [
              DropdownMenuItem(
                  value: 'auto', child: Text('Automática (girar el móvil)')),
              DropdownMenuItem(value: 'portrait', child: Text('Vertical')),
              DropdownMenuItem(value: 'landscape', child: Text('Horizontal'))
            ],
            onChanged: (value) async {
              if (value == null) return;
              final prefs = await SharedPreferences.getInstance();
              await prefs.setString('mobileOrientation', value);
              if (mounted) {
                setState(() => DevicePlatform.mobileOrientation = value);
              }
            }),
        const SizedBox(height: 16),
        Text(
            'Tamaño de los controles arcade: ${(DevicePlatform.touchScale * 100).round()}%'),
        Slider(
            value: DevicePlatform.touchScale,
            min: .8,
            max: 1.35,
            divisions: 11,
            label: '${(DevicePlatform.touchScale * 100).round()}%',
            onChanged: (value) =>
                setState(() => DevicePlatform.touchScale = value),
            onChangeEnd: (value) async {
              final prefs = await SharedPreferences.getInstance();
              await prefs.setDouble('touchScale', value);
            }),
        const Text(
            'En vertical, la cruceta y los botones se colocan debajo de la imagen. Los cambios se aplican al abrir el juego.'),
        const Divider(height: 32),
      ],
      if (TelevisionScope.of(context) && !DevicePlatform.mobile) ...[
        const Text('Android TV y mandos Bluetooth',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
        const Text(
            'Arcade utiliza MAME nativo. Los ajustes de rendimiento siguientes solo afectan a los motores de consola.'),
        const SizedBox(height: 12),
        SwitchListTile(
            focusNode: tvPerformance,
            title: const Text('Rendimiento rápido para TV'),
            subtitle: const Text(
                'Reduce el tamaño del reproductor y solicita 60 Hz/1080p cuando la tele lo permite. Se aplica al volver a abrir el juego.'),
            value: DevicePlatform.fastTelevision,
            onChanged: (value) async {
              final prefs = await SharedPreferences.getInstance();
              await prefs.setBool('fastTelevision', value);
              if (mounted) {
                setState(() => DevicePlatform.fastTelevision = value);
              }
            }),
        Text(
            'Pantalla: ${DevicePlatform.info['refreshRate'] ?? '?'} Hz · WebView: ${DevicePlatform.info['webView'] ?? '?'}'),
        SwitchListTile(
            title: const Text('Sincronizar motor con WebView (rAF)'),
            subtitle: const Text(
                'Permite comparar la temporización rAF con el bucle inmediato anterior (desactivado). La opción más rápida depende del equipo. Se aplica al reabrir el juego.'),
            value: DevicePlatform.tvVsync,
            onChanged: (value) async {
              final prefs = await SharedPreferences.getInstance();
              await prefs.setBool('tvVsync', value);
              if (mounted) {
                setState(() => DevicePlatform.tvVsync = value);
              }
            }),
        SwitchListTile(
            title: const Text('Composición directa del reproductor'),
            subtitle: const Text(
                'Prueba la vista Android directa para evitar copias de textura. Si falla la imagen, desactívala y vuelve a abrir el juego.'),
            value: DevicePlatform.directTelevisionView,
            onChanged: (value) async {
              final prefs = await SharedPreferences.getInstance();
              await prefs.setBool('directTelevisionView', value);
              if (mounted) {
                setState(() => DevicePlatform.directTelevisionView = value);
              }
            }),
        const Text(
            'Empareja el mando desde los ajustes Bluetooth de la tele. Usa la cruceta o el stick para navegar y A/OK para seleccionar. Los juegos integrados arrancan automáticamente. Durante el juego, Start + Select abre el menú; Atrás del mando de la tele guarda y vuelve a la biblioteca.'),
        const SizedBox(height: 12),
        OutlinedButton.icon(
            onPressed: () => perform(() =>
                DevicePlatform.channel.invokeMethod<void>('bluetoothSettings')),
            icon: const Icon(Icons.bluetooth),
            label: const Text('Abrir ajustes Bluetooth de la tele')),
        const Divider(height: 32),
      ],
      const Text('Conexión con tu Raspberry',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
      const SizedBox(height: 16),
      TextField(
          focusNode: tvServer,
          controller: server,
          decoration: const InputDecoration(
              labelText: 'Servidor', border: OutlineInputBorder())),
      const SizedBox(height: 12),
      TextField(
          controller: token,
          obscureText: true,
          decoration: const InputDecoration(
              labelText: 'Token (si está configurado)',
              border: OutlineInputBorder())),
      const SizedBox(height: 12),
      Align(
          alignment: Alignment.centerLeft,
          child: FilledButton(
              onPressed: busy ? null : saveConnection,
              child: const Text('Guardar y conectar'))),
      if (status.isNotEmpty)
        Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(status)),
      const Divider(height: 40),
      const Text('Biblioteca',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
      SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Mostrar consolas vacías'),
          value: showEmpty,
          onChanged: (value) => setState(() {
                showEmpty = value;
              })),
      Wrap(spacing: 12, runSpacing: 12, children: [
        OutlinedButton.icon(
            onPressed: busy
                ? null
                : () => perform(() async {
                      await api.dio.post('/api/scan');
                      await reload();
                    }),
            icon: const Icon(Icons.sync),
            label: const Text('Escanear carpetas')),
        OutlinedButton.icon(
            onPressed: busy ? null : addSystem,
            icon: const Icon(Icons.add),
            label: const Text('Añadir consola')),
      ]),
      const Divider(height: 40),
      const Text('Carátulas',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
      const SizedBox(height: 12),
      ScrapeTools(
          api: api,
          settings: settings,
          enabled: !busy && !loading,
          onCompleted: () => reload()),
      const SizedBox(height: 16),
      const Text(
          'Las carátulas se buscan en Libretro → LaunchBox → GameTDB, sin cuenta ni claves. Si no hay resultados, puedes subir tu propia imagen desde la ficha del juego.'),
      const Divider(height: 40),
      const Text('Emuladores',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
      const Text(
          'Visual Pinball: un ZIP/VPXZ por mesa con su .vpx, ROM ZIP y panel opcional. Android 13+ ARM64 incluye el motor en GameClub; PC descarga el motor portátil verificado. Start + Select abre el menú. El icono de bola filtra los pinballs de MAME.'),
      const Text(
          'NES y Atari 2600: motores nativos Nestopia UE y Stella incluidos en la app. Start inicia; en Atari equivale a RESET y Select a GAME SELECT.'),
      const Padding(
          padding: EdgeInsets.symmetric(vertical: 12),
          child: Text(
              'Integrados: Nintendo DS, Game Boy, Game Boy Color, Game Boy Advance, Super Nintendo y Nintendo 64. No requieren instalar emuladores. La primera carga prepara el motor automáticamente; los ajustes de controles y guardado están en el reproductor.')),
      DropdownButtonFormField<String>(
          key: ValueKey('nds-profile-$ndsProfile'),
          initialValue: ndsProfile,
          decoration: const InputDecoration(
              labelText: 'Rendimiento de Nintendo DS',
              border: OutlineInputBorder()),
          items: const [
            DropdownMenuItem(
                value: 'fast', child: Text('Rápido · menos carga gráfica')),
            DropdownMenuItem(
                value: 'balanced',
                child: Text('Equilibrado · temporización precisa'))
          ],
          onChanged: busy
              ? null
              : (value) {
                  if (value != null) setNdsProfile(value);
                }),
      const SizedBox(height: 8),
      const Text(
          'Rápido usa resolución nativa, salto de un fotograma y dos hilos cuando la vista web lo permite. El motor web no tiene JIT; algunos juegos 3D pueden seguir limitados. El cambio se aplica al volver a abrir el juego.'),
      Text(Platform.isWindows
          ? 'Selecciona el ejecutable. Esta versión le pasa la ruta del juego como argumento; los adaptadores específicos se añadirán por emulador.'
          : 'Instala el emulador en Android. Esta versión usa el selector de aplicaciones compatible con el archivo; el lanzamiento directo se añadirá por emulador.'),
      const Padding(
          padding: EdgeInsets.symmetric(vertical: 12),
          child: Text(
              'Arcade nativo: MAME 2003-Plus, MAME 2003, FinalBurn Neo y MAME completo. Incluidos en GameClub, sin WebView ni aplicaciones de emulación externas. El catálogo histórico ayuda a resolver BIOS, padres y CHD.')),
      if (Platform.isWindows)
        ...systems
            .where((s) =>
                !integratedCores.containsKey(s['id']) &&
                !nativeConsoleCores.containsKey(s['id']) &&
                s['id'] != 'vpinball')
            .map((s) => ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(s['name'] as String),
                subtitle: Text(executables[s['id']] ?? s['emulator'] as String),
                trailing: const Icon(Icons.folder_open),
                onTap: busy ? null : () => chooseExecutable(s))),
      const Divider(height: 40),
      const Text('Mandos y controles',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
      const SizedBox(height: 12),
      const Text(
          'En los sistemas integrados, abre el menú de controles del reproductor para mapear teclado y mandos. Android dispone de botones táctiles y Nintendo DS admite la pantalla táctil. Los sistemas externos utilizan los controles de su emulador.'),
    ];
    return TelevisionScope.of(context)
        ? TelevisionSettings(children: children)
        : ListView(padding: const EdgeInsets.all(24), children: children);
  }

  @override
  Widget build(BuildContext context) => Focus(
      onKeyEvent: (_, event) {
        if (event.synthesized &&
            {
              LogicalKeyboardKey.gameButtonA,
              LogicalKeyboardKey.enter,
              LogicalKeyboardKey.select,
              LogicalKeyboardKey.space
            }.contains(event.logicalKey)) {
          return KeyEventResult.handled;
        }
        if (!TelevisionScope.of(context) ||
            event is! KeyDownEvent ||
            ModalRoute.of(context)?.isCurrent != true) {
          return KeyEventResult.ignored;
        }
        if (event.logicalKey == LogicalKeyboardKey.gameButtonLeft1) {
          controllerTab(-1);
          return KeyEventResult.handled;
        }
        if (event.logicalKey == LogicalKeyboardKey.gameButtonRight1) {
          controllerTab(1);
          return KeyEventResult.handled;
        }
        if (event.logicalKey == LogicalKeyboardKey.gameButtonSelect &&
            tab < 2) {
          controllerSearch();
          return KeyEventResult.handled;
        }
        return KeyEventResult.ignored;
      },
      child: Padding(
          padding: TelevisionScope.of(context)
              ? const EdgeInsets.symmetric(horizontal: 24, vertical: 12)
              : EdgeInsets.zero,
          child: Scaffold(
            appBar: AppBar(title: const Text('GameClub · 0.10.0'), actions: [
              IconButton(
                  tooltip: 'Escanear biblioteca',
                  onPressed: busy
                      ? null
                      : () => perform(() async {
                            await api.dio.post('/api/scan');
                            await reload();
                          }),
                  icon: const Icon(Icons.sync)),
              IconButton(
                  tooltip: 'Añadir juego',
                  onPressed: busy || systems.isEmpty ? null : addGames,
                  icon: const Icon(Icons.add)),
            ]),
            body: Column(children: [
              if (busy) LinearProgressIndicator(value: progress),
              if (busy && uploadStatus != null)
                Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    child: Text(uploadStatus!,
                        maxLines: 1, overflow: TextOverflow.ellipsis)),
              Expanded(
                  child: Focus(
                      onKeyEvent: (_, event) {
                        if (TelevisionScope.of(context) &&
                            event is KeyDownEvent &&
                            {
                              LogicalKeyboardKey.gameButtonB,
                              LogicalKeyboardKey.escape
                            }.contains(event.logicalKey)) {
                          tvNav[tab].requestFocus();
                          return KeyEventResult.handled;
                        }
                        return KeyEventResult.ignored;
                      },
                      child: tab == 2 ? settingsView() : libraryView())),
            ]),
            bottomNavigationBar: TelevisionScope.of(context)
                ? Padding(
                    padding: const EdgeInsets.all(8),
                    child: Row(
                        children: List.generate(
                            3,
                            (index) => Expanded(
                                child: Focus(
                                    onKeyEvent: (_, event) {
                                      if (event is! KeyDownEvent) {
                                        return KeyEventResult.ignored;
                                      }
                                      if (event.logicalKey ==
                                          LogicalKeyboardKey.arrowLeft) {
                                        tvNav[(index + 2) % 3].requestFocus();
                                        return KeyEventResult.handled;
                                      }
                                      if (event.logicalKey ==
                                          LogicalKeyboardKey.arrowRight) {
                                        tvNav[(index + 1) % 3].requestFocus();
                                        return KeyEventResult.handled;
                                      }
                                      if (event.logicalKey ==
                                          LogicalKeyboardKey.arrowUp) {
                                        if (tab == 2) {
                                          tvPerformance.requestFocus();
                                        } else {
                                          tvGridKey.currentState
                                              ?.focusSelected();
                                        }
                                        return KeyEventResult.handled;
                                      }
                                      return KeyEventResult.ignored;
                                    },
                                    child: TextButton.icon(
                                        focusNode: tvNav[index],
                                        onPressed: busy
                                            ? null
                                            : () {
                                                setState(() => tab = index);
                                                reload();
                                              },
                                        style: TextButton.styleFrom(
                                            backgroundColor: tab == index
                                                ? const Color(0xff25273d)
                                                : null),
                                        icon: Icon([
                                          Icons.grid_view,
                                          Icons.star_outline,
                                          Icons.settings_outlined
                                        ][index]),
                                        label: Text([
                                          'Biblioteca',
                                          'Favoritos',
                                          'Ajustes'
                                        ][index])))))))
                : NavigationBar(
                    selectedIndex: tab,
                    onDestinationSelected: busy
                        ? null
                        : (value) {
                            setState(() {
                              tab = value;
                            });
                            reload();
                          },
                    destinations: const [
                        NavigationDestination(
                            icon: Icon(Icons.grid_view), label: 'Biblioteca'),
                        NavigationDestination(
                            icon: Icon(Icons.star_outline), label: 'Favoritos'),
                        NavigationDestination(
                            icon: Icon(Icons.settings_outlined),
                            label: 'Ajustes'),
                      ]),
          )));
}
