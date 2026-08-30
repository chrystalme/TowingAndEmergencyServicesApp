import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import 'api_service.dart';

/// Push notifications.
///
/// The tracking socket only reaches a foregrounded app — the OS suspends it
/// within seconds of backgrounding. This covers the case that matters for a
/// tow: the phone is in a pocket, screen off, and the driver has just arrived.
///
/// Everything here degrades quietly. A build with no `google-services.json`, a
/// user who declines the permission, or a device with no Play Services all end
/// up with push disabled and the rest of the app working — losing a
/// notification must never cost someone the ability to request a tow.
class PushService {
  PushService._();

  static final PushService instance = PushService._();

  bool _ready = false;
  String? _token;

  String? get token => _token;
  bool get isReady => _ready;

  /// Initialize Firebase once at startup.
  Future<void> init() async {
    if (_ready) return;
    try {
      await Firebase.initializeApp();
      _ready = true;
    } catch (e) {
      debugPrint('push: Firebase unavailable, notifications disabled ($e)');
      _ready = false;
    }
  }

  /// Ask for permission and hand the resulting token to the backend.
  ///
  /// Called after sign-in, because a token is only useful once the server knows
  /// which user it belongs to.
  Future<void> registerForUser() async {
    if (!_ready) return;
    try {
      final messaging = FirebaseMessaging.instance;

      // iOS and Android 13+ both require an explicit grant.
      final settings = await messaging.requestPermission();
      if (settings.authorizationStatus == AuthorizationStatus.denied) {
        debugPrint('push: permission denied');
        return;
      }

      final token = await messaging.getToken();
      if (token == null) return;
      _token = token;
      await _send(token);

      // Tokens rotate on their own; re-register when they do or the device
      // silently stops receiving notifications.
      messaging.onTokenRefresh.listen((refreshed) {
        _token = refreshed;
        _send(refreshed);
      });
    } catch (e) {
      debugPrint('push: could not register ($e)');
    }
  }

  Future<void> _send(String token) async {
    try {
      await apiService.registerDevice(
        token,
        Platform.isIOS ? 'ios' : 'android',
      );
    } catch (e) {
      debugPrint('push: backend rejected the token ($e)');
    }
  }

  /// Drop the token on sign-out, so the next person to use this phone does not
  /// receive the previous user's job notifications.
  Future<void> unregister() async {
    final token = _token;
    _token = null;
    if (token == null) return;
    try {
      await apiService.unregisterDevice(
        token,
        Platform.isIOS ? 'ios' : 'android',
      );
    } catch (_) {
      // Signing out must not fail because the network did.
    }
  }

  /// Foreground messages. The OS does not draw a notification while the app is
  /// open, so the caller decides what to show.
  Stream<RemoteMessage> get onForegroundMessage =>
      _ready ? FirebaseMessaging.onMessage : const Stream.empty();
}

final pushService = PushService.instance;
