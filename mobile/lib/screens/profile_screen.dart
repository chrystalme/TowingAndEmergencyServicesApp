import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';

/// The profile tab: who is signed in and what they can do from here.
///
/// Deliberately small — account display, the role badge, logout, and (for
/// approved drivers) the console entry point. Sign-out previously lived in
/// the dashboard AppBar where it kept company with request statistics; it
/// belongs with the account, so this is now the only place it is offered.
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  static String _roleLabel(String role) {
    switch (role) {
      case 'admin':
        return 'Administrator';
      case 'company':
        return 'Company account';
      case 'driver':
        return 'Driver';
      default:
        return 'Commuter';
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final scheme = Theme.of(context).colorScheme;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  Container(
                    width: 56,
                    height: 56,
                    decoration: BoxDecoration(
                      color: scheme.primary.withValues(alpha: 0.12),
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Icon(
                        Icons.person,
                        color: scheme.primary,
                        size: 28,
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _roleLabel(auth.role),
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Signed in',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),

          if (auth.canDrive) ...[
            Card(
              child: ListTile(
                contentPadding: const EdgeInsets.all(16),
                leading:
                    Icon(Icons.local_shipping, color: scheme.primary, size: 22),
                title: Text(
                  'Driver Console',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                subtitle: const Text(
                  'Go online, manage assignments and complete jobs.',
                  style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                ),
                trailing: Icon(
                  Icons.keyboard_arrow_right,
                  color: Colors.grey.shade500,
                ),
                onTap: () => context.push('/driver'),
              ),
            ),
            const SizedBox(height: 20),
          ],

          Card(
            child: ListTile(
              contentPadding: const EdgeInsets.all(16),
              leading: Icon(Icons.logout, color: AppColors.danger, size: 22),
              title: Text(
                'Sign out',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: AppColors.danger,
                ),
              ),
              trailing: Icon(
                Icons.keyboard_arrow_right,
                color: Colors.grey.shade500,
              ),
              onTap: () async {
                await auth.logout();
                if (context.mounted) context.go('/login');
              },
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Towing & Emergency Services',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
          ),
          const SizedBox(height: 2),
          Text(
            'v1.0 · Fuel-indexed, locked at dispatch',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey.shade500, fontSize: 11),
          ),
        ],
      ),
    );
  }
}