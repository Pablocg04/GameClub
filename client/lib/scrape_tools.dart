import 'dart:async';
import 'package:flutter/material.dart';
import 'api.dart';

class ScrapeTools extends StatefulWidget {
  const ScrapeTools(
      {super.key,
      required this.api,
      required this.settings,
      required this.onCompleted,
      this.enabled = true});
  final GameClubApi api;
  final Json settings;
  final VoidCallback onCompleted;
  final bool enabled;
  @override
  State<ScrapeTools> createState() => _ScrapeToolsState();
}

class _ScrapeToolsState extends State<ScrapeTools> {
  Json job = {'status': 'idle'};
  Timer? timer;
  bool busy = false, polling = false, overwrite = false;
  String message = '';
  bool get active => {'running', 'cancelling'}.contains(job['status']);
  bool get enabled => widget.enabled && !busy;

  @override
  void initState() {
    super.initState();
    job =
        Json.from(widget.settings['scrape_job'] as Map? ?? {'status': 'idle'});
    timer = Timer.periodic(const Duration(seconds: 3), (_) => poll());
    poll();
  }

  @override
  void didUpdateWidget(covariant ScrapeTools oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.api != widget.api) {
      job = {'status': 'idle'};
      message = '';
      poll();
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  Future<void> poll() async {
    if (polling) return;
    polling = true;
    final api = widget.api;
    try {
      final response = await api.dio.get<Json>('/api/scrape/job');
      if (!mounted || widget.api != api) return;
      final wasActive = active;
      setState(() => job = response.data!);
      if (wasActive && !active) widget.onCompleted();
    } catch (_) {
      // El trabajo continúa en el servidor aunque se pierda la conexión.
    } finally {
      polling = false;
    }
  }

  Future<void> run(Future<void> Function() action) async {
    setState(() {
      busy = true;
      message = '';
    });
    try {
      await action();
    } catch (error) {
      if (mounted) setState(() => message = GameClubApi.error(error));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> start({bool resume = false}) => run(() async {
        final response = await widget.api.dio.post<Json>('/api/scrape/job',
            data: {
              'overwrite': overwrite,
              'resume': resume,
              'provider': 'auto'
            });
        if (mounted) setState(() => job = response.data!);
      });

  Future<void> cancel() => run(() async {
        final response =
            await widget.api.dio.post<Json>('/api/scrape/job/cancel');
        if (mounted) setState(() => job = response.data!);
      });

  @override
  Widget build(BuildContext context) {
    final total = job['total'] as int? ?? 0;
    final processed = job['processed'] as int? ?? 0;
    const statuses = {
      'idle': 'Sin iniciar',
      'running': 'En curso',
      'cancelling': 'Cancelando',
      'cancelled': 'Cancelado',
      'completed': 'Terminado',
      'paused': 'En pausa',
      'interrupted': 'Interrumpido',
      'failed': 'Interrumpido por un error'
    };
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(Icons.image_search),
          title: Text('Libretro → LaunchBox → GameTDB'),
          subtitle: Text(
              'Se consulta la siguiente fuente si no se encuentra una carátula compatible. Sin cuenta ni claves; la subida manual sigue disponible.')),
      if (message.isNotEmpty)
        Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(message)),
      const SizedBox(height: 16),
      const Text('Scrape de toda la biblioteca',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
      CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Actualizar también juegos que ya tengan carátula'),
          value: overwrite,
          onChanged: enabled && !active
              ? (value) => setState(() => overwrite = value!)
              : null),
      Wrap(spacing: 12, runSpacing: 8, children: [
        FilledButton.icon(
            key: const ValueKey('scrape-all'),
            onPressed: enabled && !active ? () => start() : null,
            icon: const Icon(Icons.image_search),
            label: const Text('Scrapear todos los juegos')),
        if (job['can_resume'] == true)
          OutlinedButton(
              onPressed: enabled && !active ? () => start(resume: true) : null,
              child: const Text('Continuar pendientes')),
        if (active)
          OutlinedButton(
              onPressed:
                  enabled && job['status'] != 'cancelling' ? cancel : null,
              child: const Text('Cancelar scrape')),
      ]),
      const SizedBox(height: 12),
      const Text(
          'El trabajo continúa en la Raspberry aunque cierres la app. Las coincidencias ambiguas se dejan para el scrape individual.'),
      if (job['status'] != 'idle') ...[
        const SizedBox(height: 12),
        Text(
            '${statuses[job['status']] ?? job['status']}: $processed de $total juegos'),
        const SizedBox(height: 8),
        LinearProgressIndicator(value: total == 0 ? 0 : processed / total),
        if ((job['current_title'] as String? ?? '').isNotEmpty)
          Text(job['current_title'] as String),
        Text(
            'Actualizados: ${job['updated'] ?? 0} · Omitidos: ${job['skipped'] ?? 0} · Errores: ${job['failed'] ?? 0}'),
        if ((job['message'] as String? ?? '').isNotEmpty)
          Text(job['message'] as String),
        if ((job['already_covered'] as int? ?? 0) > 0)
          Text(
              '${job['already_covered']} juegos con carátula ya existente fuera del lote.'),
        if ((job['recent'] as List? ?? []).isNotEmpty)
          ExpansionTile(
              title: const Text('Resultados recientes'),
              children: (job['recent'] as List)
                  .reversed
                  .map((item) => ListTile(
                      title: Text(item['title'] as String),
                      subtitle: Text(item['message'] as String)))
                  .toList()),
      ],
    ]);
  }
}
