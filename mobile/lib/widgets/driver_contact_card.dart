import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

/// Who is coming, in what, and how to reach them.
///
/// Renders nothing until the API discloses the details, which it only does once
/// a driver has accepted the job — so this widget never has to decide the
/// privacy question itself. Before that, `driver_phone` is simply absent.
class DriverContactCard extends StatelessWidget {
  const DriverContactCard({super.key, required this.request});

  final Map<String, dynamic> request;

  @override
  Widget build(BuildContext context) {
    final phone = request['driver_phone'] as String?;
    final make = request['driver_vehicle_make'] as String?;
    final model = request['driver_vehicle_model'] as String?;
    final plate = request['driver_vehicle_plate'] as String?;

    if (phone == null && plate == null) return const SizedBox.shrink();

    final vehicle = [make, model].whereType<String>().join(' ');

    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1D4ED8).withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF1D4ED8).withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (vehicle.isNotEmpty || plate != null)
            Row(
              children: [
                Icon(Icons.local_shipping_outlined,
                    size: 15, color: Colors.grey.shade700),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    // The plate is what actually identifies the truck pulling
                    // up, so it is never abbreviated away.
                    plate == null ? vehicle : '$vehicle · $plate'.trim(),
                    style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      color: Colors.grey.shade800,
                    ),
                  ),
                ),
              ],
            ),
          if (phone != null) ...[
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => _call(context, phone),
                icon: const Icon(Icons.call, size: 16),
                label: Text('Call driver  $phone',
                    style: const TextStyle(fontSize: 12.5)),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF1D4ED8),
                  side: const BorderSide(color: Color(0xFF1D4ED8)),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _call(BuildContext context, String phone) async {
    final uri = Uri(scheme: 'tel', path: phone);
    // A device with no dialler (a tablet, an emulator) must not throw an
    // unhandled exception at someone who is already having a bad day.
    final launched = await launchUrl(uri).catchError((_) => false);
    if (!launched && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not open the dialler. Driver: $phone')),
      );
    }
  }
}
