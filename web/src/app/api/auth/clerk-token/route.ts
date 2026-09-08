import { auth } from '@clerk/nextjs/server';
import { NextRequest, NextResponse } from 'next/server';

/**
 * Expose the Clerk session JWT to the app's axios client.
 *
 * The web app authenticates API calls with `Authorization: Bearer <token>`
 * from localStorage. When a user signs in through Clerk instead of the
 * built-in email/password form, their session lives in Clerk's `__session`
 * cookie — so this route hands that session's JWT to the front end, which
 * stores it in the same `access_token` slot the rest of the app already uses.
 * The backend accepts both token kinds (fastapi-users JWT and Clerk session
 * JWT), so whichever login the user picked keeps every downstream call
 * working.
 */
export async function GET(_request: NextRequest) {
  if (!process.env.CLERK_SECRET_KEY) {
    // Clerk is not configured in this environment: there is no session to
    // bridge. 404 (not 500) so the client treats it as "nothing to sync".
    return NextResponse.json({ token: null }, { status: 404 });
  }
  try {
    const { sessionId, getToken } = await auth();
    if (!sessionId) {
      return NextResponse.json({ token: null }, { status: 401 });
    }
    const token = await getToken();
    if (!token) {
      return NextResponse.json({ token: null }, { status: 401 });
    }
    return NextResponse.json({ token });
  } catch (_) {
    // Clerk middleware not active / misconfigured: same calm 404.
    return NextResponse.json({ token: null }, { status: 404 });
  }
}