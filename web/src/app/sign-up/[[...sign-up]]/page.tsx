import { SignUp } from "@clerk/nextjs";
import Link from "next/link";

export default function SignUpPage() {
  // Mirror of the sign-in page: no Clerk keys -> plain fallback instead of
  // a runtime error from the Clerk component.
  if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-lg text-gray-700">
            Clerk sign-up is not enabled in this environment.
          </p>
          <Link
            href="/register"
            className="text-primary-600 hover:text-primary-500 font-medium"
          >
            Use the email and password sign-up instead
          </Link>
        </div>
      </div>
    );
  }
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignUp />
    </div>
  );
}