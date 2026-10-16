import 'dart:io';
import 'package:flutter/material.dart';
import 'api.dart';
import 'arcade_loader.dart';
import 'integrated_player.dart';
import 'player_host.dart';
import 'television.dart';

class ArcadePlayer extends StatefulWidget {
  const ArcadePlayer(
      {super.key,
      required this.game,
      required this.loader,
      required this.host,
      required this.api,
      required this.plans,
      this.rejected = const []});
  final Json game;
  final ArcadeLoader loader;
  final PlayerHost host;
  final GameClubApi api;
  final List<Json> plans;
  final List<Json> rejected;

  @override
  State<ArcadePlayer> createState() => _ArcadePlayerState();
}

class _ArcadePlayerState extends State<ArcadePlayer> {
  Uri? uri;
  Json? activePlan;
  int index = -1;
  bool switching = false, exhausted = false;
  String status = 'Preparando arcade…';
  final errors = <String>[];

  @override
  void initState() {
    super.initState();
    next();
  }

  Future<void> next([String? reason]) async {
    if (switching || exhausted || !mounted) return;
    switching = true;
    if (reason != null && index >= 0) {
      debugPrint('Arcade ${widget.plans[index]['core']}: $reason');
      errors.add('${widget.plans[index]['core_name']}: $reason');
      await widget.loader.forget(widget.game);
    }
    while (++index < widget.plans.length && mounted) {
      final plan = widget.plans[index];
      setState(() {
        status =
            'Probando ${plan['core_name']} (${index + 1}/${widget.plans.length})…';
      });
      try {
        final files = await widget.loader.prepare(widget.game, plan: plan);
        if (!mounted) return;
        final primary = '${plan['game_code']}.zip';
        final previous = uri;
        final opened = widget.host.open(
            {...widget.game, 'filename': primary}, files[primary]!, widget.api,
            mobile: Platform.isAndroid,
            arcadeCore: plan['core'] as String,
            mameDriver: plan['driver'] as String?,
            fastTelevision: DevicePlatform.fastTelevision,
            tvVsync: DevicePlatform.tvVsync,
            autoStart: index > 0,
            television: TelevisionScope.of(context),
            nativeGamepad:
                TelevisionScope.of(context) && DevicePlatform.nativeGamepads,
            auxiliary: Map.fromEntries(
                files.entries.where((entry) => entry.key != primary)));
        setState(() {
          uri = opened;
          activePlan = plan;
          switching = false;
        });
        if (previous != null) widget.host.release(previous);
        return;
      } catch (error) {
        errors.add('${plan['core_name']}: ${GameClubApi.error(error)}');
      }
    }
    if (mounted) {
      setState(() {
        switching = false;
        exhausted = true;
      });
    }
  }

  @override
  void dispose() {
    if (uri != null) widget.host.release(uri!);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (exhausted || uri == null) {
      final unsupported = widget.plans.isEmpty &&
          widget.rejected.isNotEmpty &&
          widget.rejected
              .every((item) => item['reason_code'] == 'unsupported_game');
      return Scaffold(
          appBar: AppBar(title: Text(widget.game['title'] as String)),
          body: Padding(
              padding: const EdgeInsets.all(20),
              child: exhausted
                  ? ListView(children: [
                      Text(unsupported
                          ? 'Este juego no está soportado por los núcleos integrados actuales.'
                          : 'Ningún núcleo disponible pudo iniciar este romset.'),
                      const SizedBox(height: 12),
                      ...errors.map(Text.new),
                      ...widget.rejected.map((item) =>
                          Text('${item['core_name']}: ${item['reason']}'))
                    ])
                  : Column(children: [
                      const LinearProgressIndicator(),
                      const SizedBox(height: 12),
                      Text(status)
                    ])));
    }
    final plan = activePlan!;
    return Stack(children: [
      IntegratedPlayer(
          uri: uri!,
          title: widget.game['title'] as String,
          coreLabel: plan['core_name'] as String,
          mameWebControls: plan['engine'] == 'mame_web',
          onCoreFailed: next,
          onCoreStarted: () {
            if (!switching) widget.loader.remember(widget.game, plan);
          }),
      if (switching)
        Positioned(
            left: 0,
            right: 0,
            top: 90,
            child: Material(
                child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(children: [
                      const LinearProgressIndicator(),
                      Text(status)
                    ]))))
    ]);
  }
}
