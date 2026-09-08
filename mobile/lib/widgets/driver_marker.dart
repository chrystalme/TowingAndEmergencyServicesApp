import 'package:flutter/material.dart';

import '../models/driver_candidate.dart';
import '../utils/money.dart';

/// Brand blue, kept local so the marker keeps its identity until the global
/// theme lands (the theme is owned by main.dart).
const _brandBlue = Color(0xFF1D4ED8);

/// The map marker for one nearby driver: a tow-truck icon in a 40px white
/// circle, with a price chip floating above it once the driver is selected.
///
/// This is the *content* of a `flutter_map` `Marker`; the map screen decides
/// the point, width/height and alignment. Tapping runs [onTap].
class DriverMarker extends StatelessWidget {
  const DriverMarker({
    super.key,
    required this.candidate,
    this.selected = false,
    this.onTap,
  });

  final DriverCandidate candidate;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final circle = Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
        border: Border.all(
          color: selected ? _brandBlue : scheme.outlineVariant,
          width: selected ? 2.5 : 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.18),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Icon(
        Icons.local_shipping,
        size: 22,
        color: selected ? _brandBlue : scheme.onSurfaceVariant,
      ),
    );

    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (selected) _priceChip(context),
          const SizedBox(height: 2),
          circle,
        ],
      ),
    );
  }

  /// The upfront fare, shown so the user can price-shop without opening the
  /// sheet. Only rendered for the selected driver to keep the map uncluttered.
  Widget _priceChip(BuildContext context) {
    final price = candidate.priceEstimate;
    if (price == null) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.25),
            blurRadius: 4,
          ),
        ],
      ),
      child: Text(
        formatMoney(price),
        style: const TextStyle(
          color: Colors.white,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}