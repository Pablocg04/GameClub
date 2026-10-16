import 'dart:convert';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/main.dart';
import 'package:gameclub/scrape_tools.dart';
import 'package:shared_preferences/shared_preferences.dart';

class LibraryAdapter implements HttpClientAdapter {
  final requests = <RequestOptions>[];
  final Json settings = {'scrape_provider': 'auto'};
  final Json job = {'status': 'idle', 'total': 0, 'processed': 0};

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    requests.add(options);
    final Object data;
    switch (options.path) {
      case '/api/scrape/job':
        if (options.method == 'POST') {
          job.addAll({'status': 'running', 'total': 2, 'processed': 0});
        }
        data = job;
      case '/api/scrape/job/cancel':
        job['status'] = 'cancelling';
        data = job;
      case '/api/systems':
        data = [
          {
            'id': 'gba',
            'name': 'Game Boy Advance',
            'game_count': 1,
            'extensions': ['.gba', '.zip'],
            'emulator': 'mGBA'
          },
          {
            'id': 'psx',
            'name': 'PlayStation',
            'game_count': 0,
            'extensions': ['.chd', '.zip'],
            'emulator': 'DuckStation'
          },
        ];
      case '/api/games':
        data = options.queryParameters['favorites'] == true
            ? []
            : [
                {
                  'id': 'test',
                  'title': 'Mi juego',
                  'filename': 'Mi juego.gba',
                  'system_id': 'gba',
                  'size': 1024,
                  'favorite': false,
                  'cover_url': null,
                  'description': ''
                },
              ];
      case '/api/games/test/screenshots':
        data = {'images': [], 'checked': true};
      case '/api/games/test/scrape':
        data = options.method == 'GET'
            ? [
                {
                  'id': 'public-result',
                  'title': 'Resultado Libretro',
                  'description': 'Carátula Europa'
                }
              ]
            : {};
      default:
        data = settings;
    }
    return ResponseBody.fromString(jsonEncode(data), 200, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType]
    });
  }

  @override
  void close({bool force = false}) {}
}

class BatchPicker extends FilePicker {
  BatchPicker(this.files);
  final List<PlatformFile> files;
  @override
  Future<FilePickerResult?> pickFiles(
      {String? dialogTitle,
      String? initialDirectory,
      FileType type = FileType.any,
      List<String>? allowedExtensions,
      Function(FilePickerStatus)? onFileLoading,
      bool allowCompression = false,
      int compressionQuality = 0,
      bool allowMultiple = false,
      bool withData = false,
      bool withReadStream = false,
      bool lockParentWindow = false,
      bool readSequential = false}) async {
    expect(allowMultiple, isTrue);
    return FilePickerResult(files);
  }
}

class BatchApi extends GameClubApi {
  BatchApi() : super('http://test', '');
  final uploads = <Json>[];
  @override
  Future<void> upload(String endpoint, String path, String name,
      void Function(int, int) progress) async {
    uploads.add({'endpoint': endpoint, 'filename': name});
    progress(3, 3);
  }
}

void main() {
  testWidgets('la ficha muestra capturas sin impedir marcar favoritos',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    final adapter = LibraryAdapter();
    api.dio.httpClientAdapter = adapter;
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Mi juego'));
    await tester.pumpAndSettle();
    expect(find.text('Capturas del juego'), findsOneWidget);
    expect(find.text('Añadir capturas'), findsOneWidget);
    expect(adapter.requests.any((r) => r.path == '/api/games/test/screenshots'),
        isTrue);
    await tester.tap(find.text('Favorito'));
    await tester.pumpAndSettle();
    expect(
        adapter.requests.any((r) =>
            r.path == '/api/games/test' &&
            r.method == 'PATCH' &&
            (r.data as Map)['favorite'] == true),
        isTrue);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
      'el lote usa Libretro aunque el servidor conserve el proveedor antiguo',
      (tester) async {
    final api = GameClubApi('http://test', '');
    final adapter = LibraryAdapter();
    adapter.settings['scrape_provider'] = 'screenscraper';
    api.dio.httpClientAdapter = adapter;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
                child: ScrapeTools(
                    api: api,
                    settings: adapter.settings,
                    onCompleted: () {})))));
    await tester.pumpAndSettle();
    expect(find.textContaining('ScreenScraper'), findsNothing);
    expect(find.text('Guardar acceso API'), findsNothing);
    await tester.tap(find.byKey(const ValueKey('scrape-all')));
    await tester.pumpAndSettle();
    expect(
        adapter.requests
            .lastWhere((r) => r.path == '/api/scrape/job' && r.method == 'POST')
            .data,
        {'overwrite': false, 'resume': false, 'provider': 'auto'});
    expect(find.text('En curso: 0 de 2 juegos'), findsOneWidget);
    await tester.tap(find.text('Cancelar scrape'));
    await tester.pumpAndSettle();
    expect(adapter.requests.any((r) => r.path == '/api/scrape/job/cancel'),
        isTrue);
    expect(find.text('Cancelando: 0 de 2 juegos'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('biblioteca oculta consolas vacías y permite filtrar favoritos',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    final adapter = LibraryAdapter();
    api.dio.httpClientAdapter = adapter;
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    expect(find.text('Mi juego'), findsOneWidget);
    expect(find.text('Game Boy Advance · 1'), findsOneWidget);
    expect(find.text('PlayStation · 0'), findsNothing);
    await tester.tap(find.text('Favoritos'));
    await tester.pumpAndSettle();
    expect(find.text('Mi juego'), findsNothing);
    expect(
        adapter.requests.any((r) =>
            r.path == '/api/games' && r.queryParameters['favorites'] == true),
        isTrue);
    await tester.tap(find.text('Ajustes'));
    await tester.pumpAndSettle();
    expect(find.text('Conexión con tu Raspberry'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('búsqueda filtra juegos sin alterar el catálogo', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    api.dio.httpClientAdapter = LibraryAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'otro');
    await tester.pumpAndSettle();
    expect(find.text('Mi juego'), findsNothing);
    await tester.enterText(find.byType(TextField), 'Mi');
    await tester.pumpAndSettle();
    expect(find.text('Mi juego'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('ajustes muestran solo carátulas sin cuenta ni claves',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    final adapter = LibraryAdapter();
    adapter.settings['scrape_provider'] = 'screenscraper';
    api.dio.httpClientAdapter = adapter;
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ajustes'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
        find.text('Libretro → LaunchBox → GameTDB'), 300,
        scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('ScreenScraper'), findsNothing);
    expect(find.text('Guardar cuenta'), findsNothing);
    expect(find.text('Proveedor de carátulas'), findsNothing);
    expect(
        adapter.requests.any((r) => r.path.contains('screenscraper')), isFalse);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
      'la búsqueda individual y la selección siempre usan el catálogo público',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    final adapter = LibraryAdapter();
    adapter.settings['scrape_provider'] = 'screenscraper';
    api.dio.httpClientAdapter = adapter;
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Mi juego'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Buscar carátula'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(
        adapter.requests
            .lastWhere((r) => r.path == '/api/games/test/scrape')
            .queryParameters['provider'],
        'auto');
    expect(
        adapter.requests
            .lastWhere((r) => r.path == '/api/games/test/scrape')
            .receiveTimeout,
        const Duration(minutes: 10));
    await tester.tap(find.text('Resultado Libretro'));
    await tester.pumpAndSettle();
    expect(
        adapter.requests
            .lastWhere(
                (r) => r.path == '/api/games/test/scrape' && r.method == 'POST')
            .data,
        {'provider_id': 'public-result', 'provider': 'auto'});
    expect(find.text('Carátula actualizada'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('el diálogo de carátulas admite una ventana baja con teclado',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '')
      ..dio.httpClientAdapter = LibraryAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Mi juego'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Buscar carátula'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    tester.view.physicalSize = const Size(640, 360);
    tester.view.devicePixelRatio = 1;
    tester.view.viewInsets = const FakeViewPadding(bottom: 180);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetViewInsets);
    await tester.pump(const Duration(milliseconds: 300));
    expect(tester.takeException(), isNull);
    tester.view.resetViewInsets();
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('elige una consola una vez para todas las ROMs del lote',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    FilePicker.platform = BatchPicker([
      PlatformFile(name: 'First.zip', size: 3, path: '/test/First.zip'),
      PlatformFile(name: 'Second.zip', size: 3, path: '/test/Second.zip')
    ]);
    final api = BatchApi();
    api.dio.httpClientAdapter = LibraryAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Añadir juego'));
    await tester.pumpAndSettle();
    expect(find.text('Añadir 2 juegos'), findsOneWidget);
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Game Boy Advance').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Subir'));
    await tester.pumpAndSettle();
    expect(api.uploads, hasLength(2));
    expect(api.uploads.every((r) => r['endpoint'] == '/api/systems/gba/upload'),
        isTrue);
    expect(api.uploads.map((r) => r['filename']).toList(),
        ['First.zip', 'Second.zip']);
    expect(find.byType(AlertDialog), findsNothing);
    expect(find.text('2 de 2 juegos añadidos a gba'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
