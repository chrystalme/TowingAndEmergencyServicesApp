import { render, screen } from '@testing-library/react';
import Providers from './Providers';

describe('Providers', () => {
  it('renders children correctly', () => {
    render(
      <Providers>
        <div data-testid="child">Hello World</div>
      </Providers>
    );

    expect(screen.getByTestId('child')).toBeInTheDocument();
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('renders the Toaster component', () => {
    const { container } = render(
      <Providers>
        <div>Content</div>
      </Providers>
    );

    // Sonner's Toaster renders a section with aria-label containing "Notifications"
    const toasterRegion = container.querySelector('[aria-label*="Notifications"]');
    expect(toasterRegion).toBeInTheDocument();
  });

  it('renders multiple children', () => {
    render(
      <Providers>
        <div data-testid="first">First</div>
        <div data-testid="second">Second</div>
      </Providers>
    );

    expect(screen.getByTestId('first')).toBeInTheDocument();
    expect(screen.getByTestId('second')).toBeInTheDocument();
  });
});