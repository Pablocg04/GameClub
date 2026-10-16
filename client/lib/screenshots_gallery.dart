import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'api.dart';

class ScreenshotsGallery extends StatefulWidget {
  const ScreenshotsGallery(
      {super.key, required this.api, required this.gameId});
  final GameClubApi api;
  final String gameId;
  @override
  State<ScreenshotsGallery> createState() => _ScreenshotsGalleryState();
}

class _ScreenshotsGalleryState extends State<ScreenshotsGallery> {
  List<Json> images = [];
  bool loading = true;
  String message = '';
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load({bool refresh = false}) async {
    setState(() {
      loading = true;
      message = '';
    });
    try {
      final path = '/api/games/${widget.gameId}/screenshots';
      var data = (await widget.api.dio.get<Json>(path)).data!;
      if (refresh ||
          ((data['images'] as List).isEmpty && data['checked'] != true)) {
        data = (await widget.api.dio.post<Json>('$path/refresh')).data!;
      }
      if (mounted) {
        setState(() {
          images = (data['images'] as List)
              .map((value) => Json.from(value as Map))
              .toList();
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          message = GameClubApi.error(error);
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          loading = false;
        });
      }
    }
  }

  Future<void> upload() async {
    final selected = await FilePicker.platform
        .pickFiles(type: FileType.image, allowMultiple: true);
    if (selected == null || !mounted) return;
    setState(() {
      loading = true;
      message = '';
    });
    try {
      for (final file in selected.files) {
        if (file.path == null) continue;
        await widget.api.upload('/api/games/${widget.gameId}/screenshots',
            file.path!, file.name, (_, __) {});
      }
      await load();
    } catch (error) {
      if (mounted) {
        setState(() {
          message = GameClubApi.error(error);
          loading = false;
        });
      }
    }
  }

  Widget image(Json item, {BoxFit fit = BoxFit.contain}) =>
      Image.network(widget.api.imageUrl(item['url'] as String),
          headers: widget.api.dio.options.headers
              .map((key, value) => MapEntry(key, value.toString())),
          fit: fit,
          errorBuilder: (_, __, ___) =>
              const Center(child: Icon(Icons.broken_image_outlined)));

  void enlarge(Json item) => showDialog<void>(
      context: context,
      builder: (context) => Dialog(
          child: SizedBox(
              width: 1000,
              height: 650,
              child: Column(children: [
                Row(children: [
                  Expanded(
                      child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(item['label'] as String))),
                  IconButton(
                      tooltip: 'Cerrar captura',
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close))
                ]),
                Expanded(
                    child: InteractiveViewer(
                        minScale: .5,
                        maxScale: 5,
                        child: Center(child: image(item)))),
              ]))));

  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Capturas del juego',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        if (loading) const LinearProgressIndicator(),
        if (message.isNotEmpty) Text(message),
        if (!loading && images.isEmpty)
          const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text(
                  'Todavía no hay capturas disponibles. Puedes añadir imágenes propias.')),
        if (images.isNotEmpty)
          SizedBox(
              height: 155,
              child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: images.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 10),
                  itemBuilder: (context, index) => SizedBox(
                      width: 220,
                      child: Card(
                          clipBehavior: Clip.antiAlias,
                          child: InkWell(
                              onTap: () => enlarge(images[index]),
                              child: image(images[index])))))),
        Wrap(spacing: 8, children: [
          TextButton.icon(
              onPressed: loading ? null : () => load(refresh: true),
              icon: const Icon(Icons.refresh),
              label: const Text('Buscar capturas')),
          TextButton.icon(
              onPressed: loading ? null : upload,
              icon: const Icon(Icons.add_photo_alternate_outlined),
              label: const Text('Añadir capturas')),
        ]),
      ]);
}
