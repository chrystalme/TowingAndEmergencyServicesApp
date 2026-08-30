import 'package:intl/intl.dart';

/// Format a server-quoted amount with its currency.
///
/// The apps were printing the raw number — a job showed as `Price 19464.0`,
/// with no unit at all, which is the figure a customer is quoted. The API sends
/// an ISO 4217 code alongside the price; this renders that rather than assuming
/// a symbol, so the same helper keeps working if the rate card ever moves
/// currency.
String formatMoney(Object? amount, [String? currency]) {
  if (amount == null) return '—';

  final value = amount is num ? amount.toDouble() : double.tryParse('$amount');
  if (value == null) return '—';

  final code = (currency == null || currency.isEmpty) ? 'NGN' : currency;

  try {
    return NumberFormat.simpleCurrency(locale: 'en_NG', name: code)
        .format(value);
  } catch (_) {
    // Unknown code: show the amount with the code rather than a wrong symbol.
    return '${value.toStringAsFixed(2)} $code';
  }
}
