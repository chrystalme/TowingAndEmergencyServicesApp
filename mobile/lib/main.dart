import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'providers/auth_provider.dart';
import 'services/push_service.dart';
import 'providers/request_provider.dart';
import 'providers/driver_provider.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/request_screen.dart';
import 'screens/request_list_screen.dart';
import 'screens/driver_console_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Restore the session BEFORE the first frame. AuthProvider starts logged
  // out, and the router's redirect reads that flag, so without this a user
  // with a perfectly good token in secure storage is bounced to /login on
  // every cold start.
  // Firebase first: a restored session registers its push token straight
  // away, so a user who never signs in again still receives job updates.
  await pushService.init();

  final auth = AuthProvider();
  await auth.checkAuthStatus();
  if (auth.isLoggedIn) {
    await pushService.registerForUser();
  }

  runApp(TowingEmergencyApp(auth: auth));
}

class TowingEmergencyApp extends StatelessWidget {
  TowingEmergencyApp({super.key, required this.auth})
      : _router = _createRouter(auth);

  final AuthProvider auth;
  final GoRouter _router;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>.value(value: auth),
        ChangeNotifierProvider(create: (_) => RequestProvider()),
        ChangeNotifierProvider(create: (_) => DriverProvider()),
      ],
      child: MaterialApp.router(
        title: 'Towing & Emergency Services',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF1D4ED8), // primary-700
            brightness: Brightness.light,
          ),
          appBarTheme: const AppBarTheme(
            centerTitle: true,
            elevation: 0,
          ),
          elevatedButtonTheme: ElevatedButtonThemeData(
            style: ElevatedButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
          inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: Colors.white,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Colors.grey.shade300),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Colors.grey.shade300),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Color(0xFF1D4ED8), width: 2),
            ),
            errorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.red, width: 1),
            ),
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
          ),
        ),
        routerConfig: _router,
      ),
    );
  }
}

GoRouter _createRouter(AuthProvider auth) => GoRouter(
  initialLocation: '/',
  // Re-run the redirect whenever auth changes, so logging in or out moves
  // the user without each screen having to navigate by hand.
  refreshListenable: auth,
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const LoginScreen(),
    ),
    GoRoute(
      path: '/login',
      builder: (context, state) => const LoginScreen(),
    ),
    GoRoute(
      path: '/register',
      builder: (context, state) => const RegisterScreen(),
    ),
    GoRoute(
      path: '/dashboard',
      builder: (context, state) => const DashboardScreen(),
    ),
    GoRoute(
      path: '/request',
      builder: (context, state) => const RequestScreen(),
    ),
    GoRoute(
      path: '/requests',
      builder: (context, state) => const RequestListScreen(),
    ),
    GoRoute(
      path: '/driver',
      builder: (context, state) => const DriverConsoleScreen(),
    ),
  ],
  redirect: (context, state) {
    final isLoggedIn = auth.isLoggedIn;
    final location = state.matchedLocation;
    const authScreens = {'/login', '/register'};
    // '/' is the launch location and renders LoginScreen. It is NOT an auth
    // screen for the guard below (an unauthenticated visit must still be sent
    // to /login), but a restored session landing there has to be moved on —
    // otherwise a logged-in user stares at a login form on every cold start.
    const landingScreens = {'/', '/login', '/register'};

    // Not authenticated: everything except the auth screens goes to /login.
    if (!isLoggedIn && !authScreens.contains(location)) {
      return '/login';
    }

    // Authenticated: never sit on a landing screen.
    if (isLoggedIn && landingScreens.contains(location)) {
      return '/dashboard';
    }

    return null;
  },
);