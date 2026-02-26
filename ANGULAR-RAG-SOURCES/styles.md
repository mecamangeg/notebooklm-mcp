# styles

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `styles` |
| **Files** | 1 |
| **Total size** | 6,898 bytes |
| **Generated** | 2026-02-26 10:40 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `styles.scss` (6,898 bytes, Styles)

---

## `styles.scss`

| Field | Value |
|-------|-------|
| **Role** | Styles |
| **Extension** | `.scss` |
| **Last modified** | 2026-02-24 |
| **Size** | 6,898 bytes |

```scss
@use '@angular/material' as mat;

@include mat.core();

$light-theme: mat.define-theme((color: (theme-type: light,
        primary: mat.$violet-palette,
        tertiary: mat.$blue-palette,
      )));

/* ========================================
   ALT AI Chat - Global Styles
   NotebookLM-inspired Four-Column Layout
   Verbatim port from robsky-ai-vertex/src/styles/index.css
   ======================================== */

/* CSS Variables for Theming */
:root {
  @include mat.all-component-themes($light-theme);

  /* Light Mode - Warm, paper-like backgrounds */
  --bg-page: #f8f6f3;
  --bg-surface: #ffffff;
  --bg-surface-hover: #f5f3f0;
  --bg-surface-active: #ede9e4;
  --bg-chat: #faf9f7;
  --bg-document: #fdfcfa;
  --bg-input: #ffffff;
  --bg-code: #f4f2ef;

  /* Text Colors - Dark but not pure black */
  --text-primary: #1a1a1a;
  --text-secondary: #4a4a4a;
  --text-tertiary: #6b6b6b;
  --text-muted: #8a8a8a;
  --text-inverse: #ffffff;

  /* Border Colors */
  --border-color: #e0dcd5;
  --border-color-strong: #c8c4bd;
  --border-color-subtle: #f0ede8;

  /* Accent Colors - Domain specific */
  --accent-legal: #d97706;
  --accent-legal-light: #fef3c7;
  --accent-accounting: #059669;
  --accent-accounting-light: #d1fae5;
  --accent-tax: #dc2626;
  --accent-tax-light: #fee2e2;

  /* Tier Colors — Authority Hierarchy */
  --tier-1: #d97706;        /* Gold Amber  — Constitutions, Primary Statutes */
  --tier-2: #2563eb;        /* Azure Blue  — Supreme Court Decisions         */
  --tier-3: #7c3aed;        /* Violet      — Regulations, Revenue Regulations*/
  --tier-4: #6b7280;        /* Stone Gray  — Secondary Doctrine              */

  /* UI Colors */
  --accent-primary: #4f46e5;
  --accent-primary-hover: #4338ca;
  --accent-secondary: #6b7280;
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);

  /* Spacing */
  --spacing-xs: 0.25rem;
  --spacing-sm: 0.5rem;
  --spacing-md: 1rem;
  --spacing-lg: 1.5rem;
  --spacing-xl: 2rem;

  /* Border Radius */
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
  --transition-slow: 350ms ease;

  /* Legacy vars for backward compat */
  --app-bg: var(--bg-page);
  --panel-bg: var(--bg-surface);
  --glass-border: var(--border-color);
  --accent-gradient: linear-gradient(135deg, var(--accent-primary), var(--tier-3));
  --glow-primary: rgba(79, 70, 229, 0.3);
}

/* Dark Mode — Deep Charcoal (Stitch Design System, Feb 2026) */
.dark {
  /* Backgrounds — Abyss Charcoal palette */
  --bg-page: #0b0c0f;
  --bg-surface: #121418;
  --bg-surface-hover: #1a1d24;
  --bg-surface-active: #22262f;
  --bg-chat: #0f1013;
  --bg-document: #0e0f12;
  --bg-input: #161920;
  --bg-code: #1a1d24;

  /* Text — Warm Cream palette */
  --text-primary: #e7e5e4;
  --text-secondary: #b0adaa;
  --text-tertiary: #78756f;
  --text-muted: #50504a;
  --text-inverse: #0b0c0f;

  /* Borders — Coal palette */
  --border-color: #2a2d35;
  --border-color-strong: #363b47;
  --border-color-subtle: #1e2128;

  /* Domain Accents — dark-tuned */
  --accent-legal: #fbbf24;
  --accent-legal-light: #451a03;
  --accent-accounting: #34d399;
  --accent-accounting-light: #064e3b;
  --accent-tax: #f87171;
  --accent-tax-light: #450a0a;

  /* Tier Colors — dark-mode variants */
  --tier-1: #f59e0b;        /* Gold Amber     — illuminated on dark bg */
  --tier-2: #137fec;        /* Azure Blue     — court decisions         */
  --tier-3: #8b5cf6;        /* Amethyst Violet — regulations             */
  --tier-4: #6b7280;        /* Stone Gray     — secondary doctrine       */

  /* UI Colors — dark-tuned */
  --accent-primary: #6c63ff;
  --accent-primary-hover: #8b83ff;
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;

  /* Shadows — deeper on dark */
  --shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.5);
  --shadow-md: 0 4px 8px -1px rgba(0, 0, 0, 0.6), 0 2px 4px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 12px 20px -3px rgba(0, 0, 0, 0.7), 0 4px 8px rgba(0, 0, 0, 0.5);

  /* Accent gradient — bright indigo to amethyst */
  --accent-gradient: linear-gradient(135deg, #6c63ff, #8b5cf6);
  --glow-primary: rgba(108, 99, 255, 0.35);
}

/* ========================================
   Base Styles
   ======================================== */

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  background-color: var(--bg-page);
  color: var(--text-primary);
  min-height: 100vh;
  overflow: hidden;
}

/* ========================================
   Animation Keyframes
   ======================================== */

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {

  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.5;
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}

.animate-fadeIn {
  animation: fadeIn 0.3s ease-out;
}

.animate-slideIn {
  animation: slideIn 0.3s ease-out;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* ========================================
   Scrollbar Styles
   ======================================== */

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--border-color-strong);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

/* ========================================
   Selection Styles
   ======================================== */

::selection {
  background: var(--accent-primary);
  color: var(--text-inverse);
}

.dark ::selection {
  background: var(--accent-primary);
  color: var(--text-inverse);
}
```
