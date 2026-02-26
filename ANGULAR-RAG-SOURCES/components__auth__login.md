# login

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__auth__login` |
| **Files** | 1 |
| **Total size** | 9,735 bytes |
| **Generated** | 2026-02-26 11:03 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/auth/login/login.ts` (9,735 bytes, Source)

---

## `app/components/auth/login/login.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-24 |
| **Size** | 9,735 bytes |
| **Exports** | `LoginComponent` |

```typescript
import {
  Component, inject, signal, ChangeDetectionStrategy
} from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';

import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-login',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule],
  styles: [`
    :host {
      display: contents;
    }

    .login-screen {
      height: 100vh;
      width: 100vw;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-page);
      position: relative;
      overflow: hidden;
    }

    .login-screen::before {
      content: '';
      position: absolute;
      top: 15%;
      left: 15%;
      width: 450px;
      height: 450px;
      background: radial-gradient(ellipse at center, rgba(79, 70, 229, 0.07) 0%, transparent 70%);
      pointer-events: none;
      border-radius: 50%;
      filter: blur(50px);
    }

    .login-screen::after {
      content: '';
      position: absolute;
      bottom: 10%;
      right: 10%;
      width: 400px;
      height: 400px;
      background: radial-gradient(ellipse at center, rgba(139, 92, 246, 0.06) 0%, transparent 70%);
      pointer-events: none;
      border-radius: 50%;
      filter: blur(50px);
    }

    .login-card {
      text-align: center;
      padding: 52px 48px;
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 24px;
      box-shadow: var(--shadow-lg);
      animation: slideUp 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
      max-width: 420px;
      width: 90%;
      position: relative;
      z-index: 1;
    }

    @keyframes slideUp {
      from { opacity: 0; transform: translateY(20px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .login-brand {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      font-weight: 700;
      font-size: 2.75rem;
      margin-bottom: 2px;
      letter-spacing: -1.5px;
      font-family: 'Outfit', sans-serif;
    }

    .brand-logo {
      color: var(--text-primary);
    }

    .brand-ai {
      background: linear-gradient(135deg, #f59e0b, #8b5cf6);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .login-tagline {
      font-size: 0.6875rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 8px;
    }

    .login-subtitle {
      color: var(--text-tertiary);
      margin-bottom: 36px;
      font-size: 0.875rem;
      line-height: 1.5;
      max-width: 300px;
      margin-inline: auto;
    }

    .google-login-btn {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      background: var(--bg-surface-hover);
      color: var(--text-primary);
      border: 1px solid var(--border-color);
      padding: 14px 28px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 15px;
      cursor: pointer;
      transition: all 0.2s ease;
      width: 100%;
      justify-content: center;
    }

    .google-login-btn:hover {
      border-color: rgba(66, 133, 244, 0.4);
      box-shadow: var(--shadow-md), 0 0 0 3px rgba(66, 133, 244, 0.08);
      transform: translateY(-1px);
    }

    .login-divider {
      display: flex;
      align-items: center;
      margin: 24px 0;
      color: var(--text-muted);
      font-size: 12px;
    }

    .login-divider::before,
    .login-divider::after {
      content: '';
      flex: 1;
      height: 1px;
      background: var(--border-color);
    }

    .login-divider span {
      padding: 0 12px;
    }

    .email-form {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .form-input {
      background: var(--bg-input);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 12px 16px;
      color: var(--text-primary);
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
      font-family: inherit;
    }

    .form-input::placeholder {
      color: var(--text-muted);
    }

    .form-input:focus {
      border-color: var(--accent-primary);
      box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
    }

    .email-login-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      background: var(--accent-primary);
      color: white;
      border: none;
      padding: 12px 24px;
      border-radius: 10px;
      font-weight: 600;
      font-size: 15px;
      cursor: pointer;
      transition: all 0.2s ease;
      margin-top: 4px;
      font-family: inherit;
    }

    .email-login-btn:hover {
      background: var(--accent-primary-hover);
      box-shadow: var(--shadow-md);
      transform: translateY(-1px);
    }

    .email-login-btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }

    .email-login-btn .material-symbols-outlined {
      font-size: 18px;
    }

    .error-msg {
      color: var(--error);
      font-size: 13px;
      margin: 0;
      text-align: left;
    }

    .login-footer-note {
      margin-top: 20px;
      font-size: 0.6875rem;
      color: var(--text-muted);
      text-align: center;
    }

    .visually-hidden {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
  `],
  template: `
    <main class="login-screen" aria-label="Sign in">
      <div class="login-card">
        <h1 class="visually-hidden">ALT AI — Sign In</h1>
        <div class="login-brand" aria-label="ALT AI">
          <span class="brand-logo" aria-hidden="true">ALT</span>
          <span class="brand-ai" aria-hidden="true">AI</span>
        </div>
        <p class="login-tagline" aria-hidden="true">Accounting · Legal · Tax</p>
        <p class="login-subtitle">Professional cross-domain research platform for Philippine law and regulations</p>

        <button class="google-login-btn" type="button" id="google-sign-in-btn" (click)="authService.loginWithGoogle()">
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg>
          Sign in with Google
        </button>

        @if (authService.authError()) {
          <p class="error-msg" role="alert">{{ authService.authError() }}</p>
        }

        <div class="login-divider" role="separator" aria-hidden="true">
          <span>or continue with email</span>
        </div>

        <form class="email-form" aria-label="Sign in with email" [formGroup]="loginForm" (ngSubmit)="loginWithEmail()">
          <input
            type="email"
            class="form-input"
            placeholder="Email address"
            formControlName="email"
            autocomplete="email"
            aria-label="Email address"
            id="email-input"
          />
          <input
            type="password"
            class="form-input"
            placeholder="Password"
            formControlName="password"
            autocomplete="current-password"
            aria-label="Password"
            id="password-input"
          />
          @if (loginError()) {
            <p class="error-msg" role="alert">{{ loginError() }}</p>
          }
          <button
            type="submit"
            class="email-login-btn"
            id="email-sign-in-btn"
            [disabled]="loginForm.invalid || authService.isLoading()"
          >
            <span class="material-symbols-outlined" aria-hidden="true">mail</span>
            Sign in with Email
          </button>
        </form>

        <p class="login-footer-note">
          Your queries are processed securely in the Philippines.
        </p>
      </div>
    </main>
  `
})
export class LoginComponent {
  protected readonly authService = inject(AuthService);
  private readonly fb = inject(FormBuilder);

  protected readonly loginForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
  });

  protected readonly loginError = signal('');

  async loginWithEmail() {
    if (this.loginForm.invalid || this.authService.isLoading()) return;

    this.loginError.set('');
    const { email, password } = this.loginForm.value;

    try {
      await this.authService.loginWithEmail(email!, password!);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Login failed';
      this.loginError.set(message);
    }
  }
}
```
