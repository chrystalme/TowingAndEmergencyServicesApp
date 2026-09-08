import { clerkMiddleware } from "@clerk/nextjs/server";
import type { NextMiddleware } from "next/server";
import { NextResponse } from "next/server";

/**
 * Clerk middleware, enabled only when the instance is configured.
 *
 * `clerkMiddleware()` throws "Missing secretKey" when CLERK_SECRET_KEY is
 * unset. Clerk is optional in this app (the built-in email/password login is
 * the baseline), so without a key the middleware must pass every request
 * straight through rather than 500ing the whole site.
 */
const clerkMiddlewareOptional: NextMiddleware = (request, event) => {
  if (!process.env.CLERK_SECRET_KEY) {
    return NextResponse.next({ request });
  }
  return clerkMiddleware()(request, event);
};

export default clerkMiddlewareOptional;

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};