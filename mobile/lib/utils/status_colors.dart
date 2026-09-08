import 'package:flutter/material.dart';

/// A single mapping from a server status string to its accent colour.
///
/// Every screen paints the same status the same way: amber while it is
/// waiting for a driver, blue while a job is moving, green when done and
/// red when cancelled or declined. Keeping it in one place stops each
/// screen from drifting into its own interpretation.
Color statusColorFor(String? status) {
  switch (status) {
    case 'pending':
    case 'assigned':
      return const Color(0xFFD97706); // amber-600
    case 'in_progress':
    case 'accepted':
    case 'enroute':
    case 'arrived':
      return const Color(0xFF2563EB); // blue-600
    case 'completed':
      return const Color(0xFF16A34A); // green-600
    case 'cancelled':
    case 'declined':
      return const Color(0xFFDC2626); // red-600
    default:
      return const Color(0xFF6B7280); // slate-500
  }
}