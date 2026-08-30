import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import 'api_service.dart';

/// Live updates for one service request.
///
/// The backend has had a tracking socket since the WebSocket work, but nothing
/// ever connected to it — so a client filed a request and then learned nothing
/// until they reopened the app. Their tow could accept, drive over, arrive and
/// finish without a word.
///
/// The socket carries two kinds of event:
///   * `dispatch_status`  — accepted / enroute / arrived / completed
///   * `driver_position`  — where the van is right now
///
/// Connect with the JWT as a query parameter: browsers cannot set headers on a
/// WebSocket handshake, so the server reads it from the URL and verifies it with
/// the same strategy the REST endpoints use.
class TrackingService {
  TrackingService._();

  static final TrackingService instance = TrackingService._();

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  int? _requestId;

  /// Close codes the server uses to say *why* it refused, so the app can tell
  /// "sign in again" from "this is not your job".
  static const unauthenticated = 4401;
  static const forbidden = 4403;
  static const notFound = 4404;

  bool get isConnected => _channel != null;
  int? get watchingRequestId => _requestId;

  /// Watch one request. Reconnecting to the same request is a no-op.
  Future<void> watch(
    int requestId, {
    required void Function(Map<String, dynamic> event) onEvent,
    void Function(Object error)? onError,
  }) async {
    if (_requestId == requestId && _channel != null) return;
    await stop();

    final token = await apiService.getToken();
    if (token == null) return;

    // Derive the ws:// URL from the configured API base so a single
    // --dart-define drives both, rather than a second thing to keep in sync.
    final base = Uri.parse(ApiService.baseUrl);
    final uri = base.replace(
      scheme: base.scheme == 'https' ? 'wss' : 'ws',
      path: '${base.path}/ws/track/$requestId',
      queryParameters: {'token': token},
    );

    try {
      final channel = WebSocketChannel.connect(uri);
      _channel = channel;
      _requestId = requestId;
      _sub = channel.stream.listen(
        (raw) {
          try {
            final decoded = jsonDecode(raw as String);
            if (decoded is Map) {
              onEvent(decoded.cast<String, dynamic>());
            }
          } catch (_) {
            // One malformed frame must not tear down the subscription.
          }
        },
        onError: (Object e) => onError?.call(e),
        onDone: () {
          _channel = null;
          _requestId = null;
        },
        cancelOnError: true,
      );
    } catch (e) {
      _channel = null;
      _requestId = null;
      onError?.call(e);
    }
  }

  Future<void> stop() async {
    await _sub?.cancel();
    _sub = null;
    await _channel?.sink.close();
    _channel = null;
    _requestId = null;
  }
}

final trackingService = TrackingService.instance;
