# auth.service

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `services__auth.service` |
| **Files** | 1 |
| **Total size** | 6,481 bytes |
| **Generated** | 2026-02-26 11:01 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/services/auth.service.ts` (6,481 bytes, Service)

---

## `app/services/auth.service.ts`

| Field | Value |
|-------|-------|
| **Role** | Service |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 6,481 bytes |
| **Exports** | `AuthService` |

```typescript
import { Injectable, inject, signal } from '@angular/core';
import { Auth, GoogleAuthProvider, signInWithPopup, signInWithEmailAndPassword, signOut, user, User } from '@angular/fire/auth';
import { toSignal } from '@angular/core/rxjs-interop';

/** Only these emails can access the app. Enforced at both frontend and backend. */
const ALLOWED_EMAILS = ['mecamangeg@gmail.com'];

/** sessionStorage keys for GCP token persistence across page reloads */
const GCP_TOKEN_KEY = 'robsky_gcp_token';
const GCP_TOKEN_EXPIRY_KEY = 'robsky_gcp_token_expiry';

@Injectable({
    providedIn: 'root'
})
export class AuthService {
    private readonly auth = inject(Auth);

    readonly user = toSignal(user(this.auth));
    readonly isLoading = signal(false);
    readonly authError = signal<string | null>(null);

    // ── GCP token state (for direct Agent Engine calls) ──
    // The cloud-platform access token is obtained from Google Sign-In and
    // used directly as a Bearer token for Vertex AI Agent Engine REST calls.
    // Token lifetime: ~60 min. We cache with a 55-min expiry to be safe.
    //
    // PERSISTENCE: stored in sessionStorage so it survives page reloads.
    // Firebase Auth auto-restores the Firebase session via onAuthStateChanged,
    // but does NOT re-provide the GCP accessToken — that only comes from
    // signInWithPopup. So we persist it ourselves.
    private _gcpToken = signal<string | null>(this.loadCachedToken());
    private _gcpTokenExpiry = this.loadCachedExpiry();

    async loginWithGoogle() {
        this.isLoading.set(true);
        this.authError.set(null);
        try {
            const provider = new GoogleAuthProvider();
            // Request cloud-platform scope for direct Agent Engine REST access.
            // Without this scope, the access token won't have permission to call
            // Vertex AI APIs directly from the browser.
            provider.addScope('https://www.googleapis.com/auth/cloud-platform');
            const result = await signInWithPopup(this.auth, provider);
            await this.enforceWhitelist(result.user);

            // Store the GCP access token for Agent Engine calls.
            // credentialFromResult() extracts the OAuth credential including accessToken
            // (confirmed by Firebase docs: Google provider always returns accessToken).
            const credential = GoogleAuthProvider.credentialFromResult(result);
            if (credential?.accessToken) {
                this.storeGcpToken(credential.accessToken);
            }
        } catch (error: unknown) {
            console.error('Login failed', error);
            throw error;
        } finally {
            this.isLoading.set(false);
        }
    }

    async loginWithEmail(email: string, password: string) {
        this.isLoading.set(true);
        this.authError.set(null);
        try {
            const result = await signInWithEmailAndPassword(this.auth, email, password);
            await this.enforceWhitelist(result.user);
        } catch (error: unknown) {
            console.error('Email login failed', error);
            throw error;
        } finally {
            this.isLoading.set(false);
        }
    }

    async logout() {
        try {
            await signOut(this.auth);
            this._gcpToken.set(null);
            this._gcpTokenExpiry = 0;
            this.authError.set(null);
            // Clear persisted token
            sessionStorage.removeItem(GCP_TOKEN_KEY);
            sessionStorage.removeItem(GCP_TOKEN_EXPIRY_KEY);
        } catch (error) {
            console.error('Logout failed', error);
        }
    }

    /** Get the current user's Firebase ID token (for documentContent calls) */
    async getIdToken(): Promise<string | null> {
        return this.auth.currentUser?.getIdToken() || null;
    }

    /**
     * Get a valid GCP OAuth2 access token for direct Agent Engine REST calls.
     *
     * Returns the cached token if still valid (< 55 min old).
     * Returns null if token is expired or unavailable (user must re-login with Google).
     *
     * Token is persisted in sessionStorage so it survives page reloads.
     * Firebase Auth auto-restores the Firebase session but NOT the GCP accessToken,
     * so we persist it ourselves and restore on service init.
     *
     * devknowledge validated: Google OAuth2 access tokens from signInWithPopup
     * are returned via GoogleAuthProvider.credentialFromResult(result).accessToken
     * and are valid for ~60 minutes.
     */
    async getGcpToken(): Promise<string | null> {
        // Return cached token if still within the 55-min safe window
        if (this._gcpToken() && Date.now() < this._gcpTokenExpiry) {
            return this._gcpToken();
        }
        // Token expired or was never obtained — user must sign in with Google again
        // (can't silently re-fetch without another popup)
        return null;
    }

    // ── Private helpers ──

    private storeGcpToken(token: string): void {
        const expiry = Date.now() + 55 * 60 * 1000; // 55 min
        this._gcpToken.set(token);
        this._gcpTokenExpiry = expiry;
        try {
            sessionStorage.setItem(GCP_TOKEN_KEY, token);
            sessionStorage.setItem(GCP_TOKEN_EXPIRY_KEY, String(expiry));
        } catch {
            // sessionStorage unavailable (private browsing extreme mode) — no-op
        }
    }

    private loadCachedToken(): string | null {
        try {
            const token = sessionStorage.getItem(GCP_TOKEN_KEY);
            const expiry = Number(sessionStorage.getItem(GCP_TOKEN_EXPIRY_KEY) ?? '0');
            if (token && Date.now() < expiry) return token;
        } catch { /* unavailable */ }
        return null;
    }

    private loadCachedExpiry(): number {
        try {
            return Number(sessionStorage.getItem(GCP_TOKEN_EXPIRY_KEY) ?? '0');
        } catch { return 0; }
    }

    /** Kick out users not in the whitelist */
    private async enforceWhitelist(user: User) {
        if (!user.email || !ALLOWED_EMAILS.includes(user.email.toLowerCase())) {
            await signOut(this.auth);
            this.authError.set(`Access denied. ${user.email} is not authorized.`);
            throw new Error(`Unauthorized email: ${user.email}`);
        }
    }
}
```
