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
  const { sessionId, getToken } = await auth();
  if (!sessionId) {
    return NextResponse.json({ token: null }, { status: 401 });
  }
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ token: null }, { status: 401 });
  }
  return NextResponse.json({ token });
}