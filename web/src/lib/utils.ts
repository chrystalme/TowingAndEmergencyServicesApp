import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
/**
 * Format a server-quoted amount.
 *
 * The UI used to print a bare `$` in front of the number while the backend
 * priced in naira, so the same figure was labelled with two currencies
 * depending on where you looked. The API now sends an ISO 4217 code with the
 * price; this renders it rather than assuming one.
 */
export function formatMoney(
  amount: number | string | null | undefined,
  // Nullable because the API omits it until a job is priced.
  currency: string | null | undefined = 'NGN',
): string {
  if (amount === null || amount === undefined || amount === '') return '—';
  const code = currency || 'NGN';
  const value = typeof amount === 'string' ? Number(amount) : amount;
  if (Number.isNaN(value)) return '—';
  try {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: code,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    // Unknown code: show the number with the code rather than a wrong symbol.
    return `${value.toFixed(2)} ${code}`;
  }
}
