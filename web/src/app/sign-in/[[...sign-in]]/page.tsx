import { SignIn } from "@clerk/nextjs";
import Link from "next/link";

export default function SignInPage() {
  // The SignIn component needs a configured ClerkProvider. Without the
  // publishable key it throws, so fall back to a plain sign-in prompt
  // rather than 500ing the page.
  if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-lg text-gray-700">
            Clerk sign-in is not enabled in this environment.
          </p>
          <Link
            href="/login"
            className="text-primary-600 hover:text-primary-500 font-medium"
          >
            Use the email and password sign-in instead
          </Link>
        </div>
      </div>
    );
  }
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn />
    </div>
  );
}