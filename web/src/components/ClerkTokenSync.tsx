'use client';

import { useEffect } from 'react';

/**
 * Bridges a Clerk session into the app's existing auth storage.
 *
 * The rest of the app (axios in src/lib/api.ts) authenticates API calls with
 * the token it finds in `localStorage['access_token']`. After a Clerk
 * sign-in the session lives in Clerk's own cookie, so on every page load we
 * ask the server for the current session JWT and, when there is one, drop it
 * into that same slot. This is what makes "either login works, whichever the
 * user wants" hold end to end: the whole app keeps working after a Clerk
 * sign-in without any of the existing auth code changing.
 *
 * The token is only written when the app does not already have one — an
 * email/password session must never be stomped by a Clerk lookup failing.
 */
export default function ClerkTokenSync() {
  useEffect(() => {
    if (localStorage.getItem('access_token')) return;

    fetch('/api/auth/clerk-token')
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then(({ token }) => {
        if (typeof token === 'string' && token.length > 0) {
          localStorage.setItem('access_token', token);
          window.location.reload();
        }
      })
      .catch(() => {
        /* Signed out of Clerk (or it isn't configured) — nothing to bridge. */
      });
  }, []);

  return null;
}