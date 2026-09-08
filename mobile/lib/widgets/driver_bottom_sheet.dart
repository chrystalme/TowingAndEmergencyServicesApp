import 'package:flutter/material.dart';

import '../models/driver_candidate.dart';
import '../utils/money.dart';

/// Slide the driver detail sheet up. Pops with the [DriverCandidate] when the
/// user taps "Request service", or null when dismissed.
Future<DriverCandidate?> showDriverBottomSheet(
  BuildContext context, {
  required DriverCandidate driver,
}) {
  return showModalBottomSheet<DriverCandidate>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (context) => DriverBottomSheet(driver: driver),
  );
}

/// "Someone is on the way" — the details and the decision, in one sheet.
///
/// Rendered without its own scaffold so it can live in any modal host.
class DriverBottomSheet extends StatelessWidget {
  const DriverBottomSheet({super.key, required this.driver});

  final DriverCandidate driver;

  String get _vehicleLine {
    final vehicle = [driver.vehicleMake, driver.vehicleModel]
        .whereType<String>()
        .join(' ');
    if (driver.vehiclePlate != null && driver.vehiclePlate!.isNotEmpty) {
      return vehicle.isEmpty ? driver.vehiclePlate! : '$vehicle · ${driver.vehiclePlate}';
    }
    return vehicle.isEmpty ? 'Vehicle details unavailable' : vehicle;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Driver identity.
            Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: scheme.primary.withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  child:
                      Icon(Icons.local_shipping, color: scheme.primary, size: 26),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        driver.name?.isNotEmpty == true
                            ? driver.name!
                            : (driver.email.isNotEmpty
                                ? driver.email
                                : 'Nearby driver'),
                        style: theme.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _vehicleLine,
                        style: theme.textTheme.bodySmall
                            ?.copyWith(color: scheme.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFF16A34A).withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.check_circle, size: 14, color: Color(0xFF16A34A)),
                      SizedBox(width: 4),
                      Text(
                        'Available',
                        style: TextStyle(
                          color: Color(0xFF16A34A),
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            // Distance / ETA / price at a glance.
            Row(
              children: [
                Expanded(
                  child: _metric(context, scheme, Icons.route_outlined, 'Distance',
                      '${driver.distanceKm.toStringAsFixed(1)} km'),
                ),
                Expanded(
                  child: _metric(context, scheme, Icons.schedule, 'ETA',
                      driver.etaMinutes == null
                          ? '—'
                          : '~${driver.etaMinutes!.round()} min'),
                ),
                Expanded(
                  child: _metric(context, scheme, Icons.payments_outlined, 'Price',
                      formatMoney(driver.priceEstimate),
                      emphasized: true),
                ),
              ],
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: FilledButton(
                onPressed: () => Navigator.of(context).pop(driver),
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF1D4ED8),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Request service',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'The fare above is the price quoted now and is locked when the '
              'driver is dispatched.',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: scheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }

  Widget _metric(BuildContext context, ColorScheme scheme, IconData icon,
      String label, String value, {bool emphasized = false}) {
    return Column(
      children: [
        Icon(icon, size: 20, color: scheme.onSurfaceVariant),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: emphasized ? FontWeight.w700 : FontWeight.w500,
            color: emphasized ? const Color(0xFF1D4ED8) : null,
          ),
        ),
        Text(
          label,
          style: Theme.of(context)
              .textTheme
              .labelSmall
              ?.copyWith(color: scheme.onSurfaceVariant),
        ),
      ],
    );
  }
}