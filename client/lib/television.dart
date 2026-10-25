import 'dart:io';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class DevicePlatform {
  static const channel = MethodChannel('gameclub/device');
  static bool television = false;
  static bool nativeGamepads = false;
  static bool fastTelevision = true;
  static bool directTelevisionView = true;
  static bool tvVsync = true;
  static String mobileOrientation = 'auto';
  static double touchScale = 1;
  static bool get mobile =>
      info['variant'] == 'mobile' || (Platform.isAndroid && !television);
  static Map<String, dynamic> info = {};
  // A connected controller changes navigation, not the device's catalog policy.
  static bool get visualPinballVisible => info['variant'] != 'tv';
  static final gamepadConnected = ValueNotifier<bool>(false);
  static Future<void> initialize() async {
    const forced = bool.fromEnvironment('GAMECLUB_TV');
    if (Platform.isAndroid) {
      try {
        info = await channel.invokeMapMethod<String, dynamic>('info') ?? {};
        television = info['television'] == true;
        nativeGamepads = info['nativeGamepads'] == true;
        gamepadConnected.value = info['gamepadConnected'] == true;
        channel.setMethodCallHandler((call) async {
          if (call.method == 'gamepadConnected') {
            gamepadConnected.value = call.arguments == true;
          }
        });
      } on PlatformException {
        /* Se mantiene la interfaz móvil si no hay canal. */
      } on MissingPluginException {
        /* Windows y pruebas no necesitan el canal. */
      }
    }
    television = television || forced;
  }
}

class TelevisionScope extends InheritedWidget {
  const TelevisionScope(
      {super.key, required this.enabled, required super.child});
  final bool enabled;
  static bool of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<TelevisionScope>()?.enabled ??
      DevicePlatform.television;
  @override
  bool updateShouldNotify(TelevisionScope oldWidget) =>
      enabled != oldWidget.enabled;
}

class TelevisionBackIntent extends Intent {
  const TelevisionBackIntent();
}

/// Fila de filtros con recorrido explícito y elementos construidos fuera de pantalla.
class TelevisionFilters extends StatefulWidget {
  const TelevisionFilters(
      {super.key,
      required this.labels,
      required this.selected,
      required this.firstFocus,
      required this.onSelected,
      required this.onDown,
      required this.onUp,
      required this.onMenu,
      this.enabled = true});
  final List<String> labels;
  final int selected;
  final FocusNode firstFocus;
  final ValueChanged<int> onSelected;
  final VoidCallback onDown, onUp, onMenu;
  final bool enabled;
  @override
  State<TelevisionFilters> createState() => _TelevisionFiltersState();
}

class _TelevisionFiltersState extends State<TelevisionFilters> {
  final nodes = <FocusNode>[];
  @override
  void initState() {
    super.initState();
    syncNodes();
  }

  void refresh() {
    if (mounted) setState(() {});
  }

  void syncNodes() {
    if (nodes.isEmpty) {
      nodes.add(widget.firstFocus);
      widget.firstFocus.addListener(refresh);
    }
    while (nodes.length < widget.labels.length) {
      final node = FocusNode(debugLabel: 'Filtro TV ${nodes.length}');
      node.addListener(refresh);
      nodes.add(node);
    }
    while (nodes.length > widget.labels.length) {
      final node = nodes.removeLast();
      node.removeListener(refresh);
      node.dispose();
    }
  }

  @override
  void didUpdateWidget(covariant TelevisionFilters oldWidget) {
    super.didUpdateWidget(oldWidget);
    syncNodes();
  }

  @override
  void dispose() {
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].removeListener(refresh);
      if (i > 0) nodes[i].dispose();
    }
    super.dispose();
  }

  void move(int delta) {
    var current = nodes.indexWhere((node) => node.hasFocus);
    if (current < 0) current = widget.selected;
    final target = (current + delta).clamp(0, nodes.length - 1);
    nodes[target].requestFocus();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final context = nodes[target].context;
      if (mounted && context != null) {
        Scrollable.ensureVisible(context,
            alignment: .5, duration: const Duration(milliseconds: 120));
      }
    });
  }

  @override
  Widget build(BuildContext context) => Focus(
      onKeyEvent: (_, event) {
        if (event is! KeyDownEvent && event is! KeyRepeatEvent) {
          return KeyEventResult.ignored;
        }
        final key = event.logicalKey;
        if (key == LogicalKeyboardKey.arrowLeft) {
          move(-1);
          return KeyEventResult.handled;
        }
        if (key == LogicalKeyboardKey.arrowRight) {
          move(1);
          return KeyEventResult.handled;
        }
        if (key == LogicalKeyboardKey.arrowDown) {
          widget.onDown();
          return KeyEventResult.handled;
        }
        if (key == LogicalKeyboardKey.arrowUp) {
          widget.onUp();
          return KeyEventResult.handled;
        }
        if (key == LogicalKeyboardKey.gameButtonB ||
            key == LogicalKeyboardKey.escape) {
          widget.onMenu();
          return KeyEventResult.handled;
        }
        if (event is KeyDownEvent &&
            {
              LogicalKeyboardKey.gameButtonA,
              LogicalKeyboardKey.enter,
              LogicalKeyboardKey.select,
              LogicalKeyboardKey.space
            }.contains(key)) {
          final index = nodes.indexWhere((node) => node.hasFocus);
          if (widget.enabled && index >= 0) widget.onSelected(index);
          return KeyEventResult.handled;
        }
        return KeyEventResult.ignored;
      },
      child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
              children: List.generate(
                  widget.labels.length,
                  (index) => Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                          focusNode: nodes[index],
                          label: Text(widget.labels[index]),
                          selected: widget.selected == index,
                          side: nodes[index].hasFocus
                              ? const BorderSide(color: Colors.white, width: 2)
                              : null,
                          onSelected: widget.enabled
                              ? (_) {
                                  nodes[index].requestFocus();
                                  widget.onSelected(index);
                                }
                              : null))))));
}

/// Lista de ajustes accesible por orden de operaciones, incluida su parte no visible.
class TelevisionSettings extends StatefulWidget {
  const TelevisionSettings({super.key, required this.children});
  final List<Widget> children;
  @override
  State<TelevisionSettings> createState() => _TelevisionSettingsState();
}

class _TelevisionSettingsState extends State<TelevisionSettings> {
  final scope = FocusScopeNode(debugLabel: 'Operaciones de ajustes TV');
  @override
  void dispose() {
    scope.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FocusScope(
      node: scope,
      child: FocusTraversalGroup(
          policy: OrderedTraversalPolicy(),
          child: CallbackShortcuts(
              bindings: MediaQuery.viewInsetsOf(context).bottom == 0
                  ? {
                      const SingleActivator(LogicalKeyboardKey.arrowDown): () =>
                          scope.nextFocus(),
                      const SingleActivator(LogicalKeyboardKey.arrowUp): () =>
                          scope.previousFocus(),
                    }
                  : const {},
              child: SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: List.generate(
                          widget.children.length,
                          (index) => FocusTraversalOrder(
                              order: NumericFocusOrder(index.toDouble()),
                              child: widget.children[index])))))));
}

/// La cuadrícula TV conserva una posición por índice, también fuera de pantalla.
class TelevisionGrid extends StatefulWidget {
  const TelevisionGrid(
      {super.key,
      required this.count,
      required this.builder,
      this.onMenu,
      this.onFilters,
      this.autofocus = true,
      this.identity});
  final int count;
  final Widget Function(BuildContext, int, FocusNode, bool) builder;
  final VoidCallback? onMenu;
  final VoidCallback? onFilters;
  final bool autofocus;
  final Object? identity;
  @override
  TelevisionGridState createState() => TelevisionGridState();
}

class TelevisionGridState extends State<TelevisionGrid> {
  final scroll = ScrollController();
  final nodes = <int, FocusNode>{};
  int selected = 0;
  FocusNode node(int index) =>
      nodes.putIfAbsent(index, () => FocusNode(debugLabel: 'Juego TV $index'));
  void focusSelected() {
    if (widget.count > 0) {
      node(selected.clamp(0, widget.count - 1)).requestFocus();
    }
  }

  @override
  void dispose() {
    scroll.dispose();
    for (final value in nodes.values) {
      value.dispose();
    }
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant TelevisionGrid oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.identity != widget.identity) {
      selected = 0;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && scroll.hasClients) {
          scroll.jumpTo(0);
        }
      });
    }
    if (selected >= widget.count) selected = 0;
  }

  void move(int target, int columns, double cellHeight, double viewport) {
    selected = target;
    final top = (target ~/ columns) * cellHeight;
    final bottom = top + cellHeight;
    var offset = scroll.offset;
    if (top < offset) offset = top;
    if (bottom > offset + viewport - 24) offset = bottom - viewport + 24;
    scroll.jumpTo(offset.clamp(0, scroll.position.maxScrollExtent));
    setState(() {});
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) node(target).requestFocus();
    });
  }

  @override
  Widget build(BuildContext context) =>
      LayoutBuilder(builder: (context, space) {
        final columns = ((space.maxWidth - 32) / 210).floor().clamp(2, 8);
        final cellWidth = (space.maxWidth - 32 - 16 * (columns - 1)) / columns;
        final cardHeight =
            math.min(cellWidth / .72, math.max(160.0, space.maxHeight - 32));
        final height = cardHeight + 16;
        return Focus(
            onKeyEvent: (_, event) {
              if (event is! KeyDownEvent && event is! KeyRepeatEvent) {
                return KeyEventResult.ignored;
              }
              final focused = nodes.entries
                  .where((entry) => entry.value.hasFocus)
                  .firstOrNull;
              if (focused == null) return KeyEventResult.ignored;
              selected = focused.key;
              final key = event.logicalKey;
              if ((key == LogicalKeyboardKey.arrowLeft &&
                      selected % columns == 0) ||
                  key == LogicalKeyboardKey.gameButtonB ||
                  key == LogicalKeyboardKey.escape) {
                widget.onMenu?.call();
                return KeyEventResult.handled;
              }
              if (key == LogicalKeyboardKey.arrowUp && selected < columns) {
                widget.onFilters?.call();
                return KeyEventResult.handled;
              }
              if (key == LogicalKeyboardKey.arrowDown &&
                  selected + columns >= widget.count) {
                widget.onMenu?.call();
                return KeyEventResult.handled;
              }
              int? target;
              if (key == LogicalKeyboardKey.arrowRight &&
                  selected % columns < columns - 1) {
                target = selected + 1;
              }
              if (key == LogicalKeyboardKey.arrowLeft &&
                  selected % columns > 0) {
                target = selected - 1;
              }
              if (key == LogicalKeyboardKey.arrowDown &&
                  selected + columns < widget.count) {
                target = selected + columns;
              }
              if (key == LogicalKeyboardKey.arrowUp && selected >= columns) {
                target = selected - columns;
              }
              if (target == null || target >= widget.count) {
                return KeyEventResult.ignored;
              }
              move(target, columns, height, space.maxHeight);
              return KeyEventResult.handled;
            },
            child: GridView.builder(
                controller: scroll,
                padding: const EdgeInsets.all(16),
                itemCount: widget.count,
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: columns,
                    mainAxisSpacing: 16,
                    crossAxisSpacing: 16,
                    childAspectRatio: cellWidth / cardHeight),
                itemBuilder: (context, index) => widget.builder(context, index,
                    node(index), widget.autofocus && index == selected)));
      });
}

class FocusGameCard extends StatefulWidget {
  const FocusGameCard(
      {super.key,
      required this.child,
      required this.onTap,
      this.focusNode,
      this.autofocus = false});
  final Widget child;
  final VoidCallback? onTap;
  final FocusNode? focusNode;
  final bool autofocus;
  @override
  State<FocusGameCard> createState() => _FocusGameCardState();
}

class _FocusGameCardState extends State<FocusGameCard> {
  bool focused = false;
  @override
  Widget build(BuildContext context) => Card(
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(
              color: focused ? Colors.white : Colors.transparent, width: 3)),
      child: InkWell(
          focusNode: widget.focusNode,
          autofocus: widget.autofocus,
          onFocusChange: (value) => setState(() => focused = value),
          focusColor: const Color(0x668c7aff),
          onTap: widget.onTap,
          child: widget.child));
}
