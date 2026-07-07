import { cn } from '@/lib/utils';

describe('cn utility', () => {
  it('merges class names correctly', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('handles conditional classes', () => {
    expect(cn('base', true && 'conditional')).toBe('base conditional');
    expect(cn('base', false && 'conditional')).toBe('base');
  });

  it('merges tailwind classes with twMerge', () => {
    expect(cn('p-2 p-4')).toBe('p-4');
    expect(cn('text-red-500 text-blue-500')).toBe('text-blue-500');
  });

  it('handles objects and arrays', () => {
    expect(cn(['foo', 'bar'])).toBe('foo bar');
    expect(cn({ foo: true, bar: false })).toBe('foo');
  });
});