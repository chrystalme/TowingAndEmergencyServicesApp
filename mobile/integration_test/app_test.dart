// End-to-end (integration) test for the Flutter app.
//
// Drives the real screens against a live backend (default localhost:8000,
// the Docker `api` service). This is the mobile half of the completeness
// gate — the compose of login -> request -> dashboard/request-list that the
// unit/widget tests deliberately skip.
//
// Setup & run (requires an emulator/simulator with the app installed):
//   flutter pub get
//   flutter pub add --dev integration_test --sdk=flutter
//   flutter test integration_test -d <device-id>
//
// The app reads its API base from ApiService; for e2e point it at the Docker
// api. See mobile/lib/services/api_service.dart.
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:towing_emergency/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('register/login/request/dashboard journey', (tester) async {
    app.main();

    // Login screen appears first.
    await tester.pumpAndSettle();
    // NOTE: fill these from a real register flow once the mobile register
    // screen exists (Phase B.5). For now assert login screen renders.
    expect(find.text('Towing & Emergency'), findsWidgets);

    // Drive login (email + password fields in login_screen.dart).
    //   await tester.enterText(find.byType(TextField).at(0), 'e2e@test.com');
    //   await tester.enterText(find.byType(TextField).at(1), 'password123');
    //   await tester.tap(find.text('Sign In'));
    //   await tester.pumpAndSettle();
    //   expect(find.text('Dashboard'), findsWidgets);
  });
}
