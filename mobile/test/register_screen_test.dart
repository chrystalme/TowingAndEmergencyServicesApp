// Widget tests for the RegisterScreen.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';

import 'package:towing_emergency/providers/auth_provider.dart';
import 'package:towing_emergency/screens/register_screen.dart';
import 'package:towing_emergency/screens/login_screen.dart';

Widget _wrap(Widget child) {
  final router = GoRouter(
    initialLocation: '/register',
    routes: [
      GoRoute(path: '/register', builder: (_, _) => child),
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
    ],
  );
  return MultiProvider(
    providers: [ChangeNotifierProvider(create: (_) => AuthProvider())],
    child: MaterialApp.router(routerConfig: router),
  );
}

// The submit button renders the label "Create Account"; target it specifically
// (the page heading uses the same string).
final createButton = find.widgetWithText(ElevatedButton, 'Create Account');

void main() {
  testWidgets('renders all form fields and the submit button', (tester) async {
    await tester.pumpWidget(_wrap(const RegisterScreen()));

    expect(find.text('Create Account'), findsWidgets);
    expect(find.text('Email'), findsWidgets);
    expect(find.text('Password'), findsWidgets);
    expect(find.text('Confirm Password'), findsWidgets);
    await tester.ensureVisible(createButton);
    expect(createButton, findsOneWidget);
  });

  testWidgets('validates mismatched passwords', (tester) async {
    await tester.pumpWidget(_wrap(const RegisterScreen()));

    final fields = find.byType(TextFormField);
    await tester.enterText(fields.at(0), 'user@example.com');
    await tester.enterText(fields.at(1), 'password123');
    await tester.enterText(fields.at(2), 'different123');
    await tester.ensureVisible(createButton);
    await tester.tap(createButton);
    await tester.pumpAndSettle();

    expect(find.text("Passwords don't match"), findsOneWidget);
  });

  testWidgets('navigates to login via Sign In link', (tester) async {
    await tester.pumpWidget(_wrap(const RegisterScreen()));

    final signIn = find.widgetWithText(TextButton, 'Sign In');
    await tester.ensureVisible(signIn);
    await tester.tap(signIn);
    await tester.pumpAndSettle();

    expect(find.text('Sign in to request roadside assistance'), findsOneWidget);
  });
}
