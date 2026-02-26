# app

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `app` |
| **Files** | 2 |
| **Total size** | 35,603 bytes |
| **Generated** | 2026-02-26 11:08 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/app.css` (29,943 bytes, Styles)
- `app/app.ts` (5,660 bytes, Source)

---

## `app/app.css`

| Field | Value |
|-------|-------|
| **Role** | Styles |
| **Extension** | `.css` |
| **Last modified** | 2026-02-24 |
| **Size** | 29,943 bytes |

```css
﻿/* ========================================
   ALT AI Chat - App Component Styles
   Verbatim port from robsky-ai-vertex
   ======================================== */
/* -- Accessibility Utilities -- */
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

/* App Container */
.app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100vw;
    background: var(--bg-page);
    overflow: hidden;
}

/* ========================================
   Top Bar
   ======================================== */
.top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 56px;
    padding: 0 var(--spacing-md);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
    z-index: 100;
}

.top-bar-left {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    flex: 1;
}

.menu-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.menu-button:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
}

.brand {
    display: flex;
    align-items: center;
    gap: 4px;
    font-weight: 700;
    font-size: 1.25rem;
    font-family: 'Outfit', sans-serif;
    letter-spacing: -0.5px;
}

.brand-logo {
    color: var(--text-primary);
    letter-spacing: -0.5px;
}

.brand-ai {
    background: linear-gradient(135deg, #f59e0b, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.top-bar-center {
    flex: 2;
    display: flex;
    justify-content: center;
}

.conversation-title {
    font-size: 0.9375rem;
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 400px;
}

.top-bar-right {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    flex: 1;
    justify-content: flex-end;
}

/* Model Badge */
.model-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 12px;
    background: linear-gradient(135deg, rgba(79, 70, 229, 0.1), rgba(139, 92, 246, 0.1));
    border: 1px solid rgba(79, 70, 229, 0.2);
    border-radius: 9999px;
    color: var(--text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.2px;
    cursor: default;
    transition: all var(--transition-fast);
}

.model-badge:hover {
    background: linear-gradient(135deg, rgba(79, 70, 229, 0.16), rgba(139, 92, 246, 0.16));
    border-color: rgba(79, 70, 229, 0.35);
    box-shadow: 0 0 12px rgba(79, 70, 229, 0.15);
}

.model-badge .material-symbols-outlined {
    color: var(--accent-primary);
    opacity: 0.8;
}

.model-badge-label {
    white-space: nowrap;
}

.theme-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.theme-toggle:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
}

/* User Menu */
.user-menu-container {
    position: relative;
}

.profile-button {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 36px;
    padding: 0 8px;
    border: none;
    background: var(--bg-surface-hover);
    color: var(--text-secondary);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.profile-button:hover {
    background: var(--bg-surface-active);
    color: var(--text-primary);
}

.chevron {
    transition: transform var(--transition-fast);
    font-size: 16px !important;
}

.chevron.open {
    transform: rotate(180deg);
}

.user-dropdown {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    min-width: 200px;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    z-index: 200;
    animation: slideIn 0.15s ease-out;
}

.user-info {
    display: flex;
    flex-direction: column;
    padding: var(--spacing-md);
}

.user-name {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-primary);
}

.user-email {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 2px;
}

.dropdown-divider {
    height: 1px;
    background: var(--border-color);
    margin: 0;
}

.dropdown-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    width: 100%;
    padding: var(--spacing-sm) var(--spacing-md);
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: 0.875rem;
    cursor: pointer;
    transition: all var(--transition-fast);
}

.dropdown-item:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
}

.logout-button:hover {
    background: var(--error);
    color: white;
}

/* ========================================
   Main Layout - Four Columns
   ======================================== */
.main-layout {
    display: flex;
    flex: 1;
    overflow: hidden;
    height: calc(100vh - 56px);
}

.column {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    height: 100%;
}

.column-nav {
    width: 260px;
    min-width: 200px;
    max-width: 300px;
    background: var(--bg-surface);
    border-right: 1px solid var(--border-color);
    flex-shrink: 0;
}

.column-chat {
    flex: 1;
    min-width: 300px;
    background: var(--bg-chat);
}

.column-viewer {
    flex: 1;
    min-width: 300px;
    background: var(--bg-document);
    border-left: 1px solid var(--border-color);
    height: 100%;
    overflow: hidden;
}

.column-citations {
    width: 260px;
    min-width: 200px;
    max-width: 300px;
    background: var(--bg-surface);
    border-left: 1px solid var(--border-color);
    flex-shrink: 0;
}

/* ========================================
   Navigation Panel
   ======================================== */
.nav-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
}

.nav-panel-header {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--border-color-subtle);
}

.new-chat-button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-sm);
    width: 100%;
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--accent-primary);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
}

.new-chat-button:hover {
    background: var(--accent-primary-hover);
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
}

.selection-toggle {
    padding: var(--spacing-xs) var(--spacing-md);
    border-bottom: 1px solid var(--border-color-subtle);
}

.enter-selection-btn {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-xs) var(--spacing-sm);
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-tertiary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all var(--transition-fast);
}

.enter-selection-btn:hover {
    background: var(--bg-surface-hover);
    color: var(--text-secondary);
    border-color: var(--border-color-strong);
}

.nav-panel-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--spacing-sm) 0;
}

.session-group {
    margin-bottom: var(--spacing-sm);
}

.session-group-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    width: 100%;
    padding: var(--spacing-sm) var(--spacing-md);
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    cursor: pointer;
    transition: color var(--transition-fast);
}

.session-group-header:hover {
    color: var(--text-secondary);
}

.session-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.session-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm) var(--spacing-md);
    margin: 0 var(--spacing-sm);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    color: var(--text-secondary);
}

.session-item:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
}

.session-item.active {
    background: var(--bg-surface-active);
    color: var(--text-primary);
}

.session-title {
    font-size: 0.8125rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ========================================
   Document Viewer
   ======================================== */
.document-viewer {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
}

.document-viewer--empty {
    align-items: center;
    justify-content: center;
}

.document-viewer-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-xl);
    text-align: center;
    color: var(--text-muted);
}

.placeholder-icon {
    font-size: 48px;
    margin-bottom: var(--spacing-md);
    opacity: 0.4;
}

.document-viewer-placeholder h3 {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: var(--spacing-xs);
}

.document-viewer-placeholder p {
    font-size: 0.8125rem;
    max-width: 240px;
}

/* ========================================
   Citations Panel
   ======================================== */
.citations-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
}

.citations-panel-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--border-color-subtle);
}

.citations-panel-header h3 {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-primary);
}

.citation-count {
    margin-left: auto;
    padding: 2px 8px;
    background: var(--accent-primary);
    color: white;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 9999px;
}

.citations-panel-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--spacing-sm);
}

.empty-citations {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-xl);
    text-align: center;
    color: var(--text-muted);
}

.empty-icon {
    font-size: 32px;
    margin-bottom: var(--spacing-md);
    opacity: 0.4;
}

.empty-hint {
    font-size: 0.75rem;
    margin-top: var(--spacing-xs);
}

/* ========================================
   NavPanel - Selection Mode
   ======================================== */
.selection-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--spacing-xs) var(--spacing-md);
    border-bottom: 1px solid var(--border-color-subtle);
    background: var(--bg-surface-active);
}

.selection-info {
    font-size: 0.75rem;
    color: var(--text-secondary);
    font-weight: 500;
}

.selection-actions {
    display: flex;
    gap: 4px;
}

.selection-action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.selection-action-btn:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
}

.selection-action-btn.delete:hover {
    background: var(--error);
    color: white;
}

.selection-action-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}

.session-item.selected {
    background: rgba(79, 70, 229, 0.08);
    border-left: 2px solid var(--accent-primary);
}

.session-checkbox {
    display: flex;
    align-items: center;
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.session-item.selected .session-checkbox {
    color: var(--accent-primary);
}

/* Session Item Actions (hover) */
.session-item {
    position: relative;
}

.session-actions {
    display: flex;
    gap: 2px;
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    opacity: 0;
    transition: opacity 0.15s ease;
}

.session-item:hover .session-actions {
    opacity: 1;
}

.session-action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-tertiary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.session-action-btn:hover {
    color: var(--text-primary);
    background: var(--bg-surface-hover);
}

.session-action-btn.delete:hover {
    color: white;
    background: var(--error);
    border-color: var(--error);
}

/* Rename Input */
.rename-input-wrapper {
    display: flex;
    align-items: center;
    gap: 4px;
    flex: 1;
    min-width: 0;
}

.rename-input {
    flex: 1;
    min-width: 0;
    padding: 2px 6px;
    background: var(--bg-input);
    border: 1px solid var(--accent-primary);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-size: 0.8125rem;
    outline: none;
}

.rename-action {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--success);
    cursor: pointer;
    transition: color var(--transition-fast);
}

.rename-action.cancel {
    color: var(--text-muted);
}

.rename-action:hover {
    color: var(--accent-primary);
}

/* Nav Panel empty */
.empty-sessions {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--spacing-xl) var(--spacing-lg);
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8125rem;
}

/* ========================================
   Document Viewer â€” Active State
   ======================================== */
.viewer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-color-subtle);
    background: var(--bg-surface);
    flex-shrink: 0;
}

.viewer-header-content {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    min-width: 0;
    flex: 1;
}

.viewer-title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin: 0;
}

.viewer-header-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
}

.viewer-action-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-tertiary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.viewer-action-button:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
}

.viewer-close-button:hover {
    background: var(--error);
    color: white;
}

.viewer-content {
    flex: 1;
    overflow: hidden;
    position: relative;
}

.viewer-iframe {
    width: 100%;
    height: 100%;
    border: none;
    background: white;
}

.viewer-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-md);
    height: 100%;
    color: var(--text-tertiary);
    font-size: 0.875rem;
}

.viewer-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-md);
    height: 100%;
    color: var(--error);
    padding: var(--spacing-lg);
    text-align: center;
}

.viewer-error button {
    padding: 8px 20px;
    background: var(--accent-primary);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 0.875rem;
    transition: background 0.2s;
}

.viewer-error button:hover {
    background: var(--accent-primary-hover);
}

@keyframes spin {
    from {
        transform: rotate(0deg);
    }

    to {
        transform: rotate(360deg);
    }
}

.animate-spin {
    animation: spin 1s linear infinite;
}

/* ========================================
   Citations Panel â€” Cards & Tiers
   ======================================== */
.tier-group {
    margin-bottom: var(--spacing-sm);
}

.tier-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    width: 100%;
    padding: var(--spacing-sm) var(--spacing-xs);
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: color var(--transition-fast);
}

.tier-header:hover {
    color: var(--text-primary);
}

.tier-icon {
    font-size: 0.875rem;
}

.tier-label {
    flex: 1;
    text-align: left;
}

.tier-count {
    margin-left: auto;
    padding: 1px 6px;
    background: var(--bg-surface-active);
    border-radius: 9999px;
    font-size: 0.6875rem;
    color: var(--text-muted);
}

.tier-citations {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-left: 4px;
}

.citation-card {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px;
    background: var(--bg-surface);
    border: 1px solid var(--border-color-subtle);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all 0.2s ease;
    width: 100%;
    text-align: left;
    font-family: inherit;
    font-size: inherit;
    color: inherit;
}

.citation-card:hover {
    background: var(--bg-surface-hover);
    border-color: var(--border-color);
    box-shadow: var(--shadow-sm);
    transform: translateY(-1px);
}

.citation-card.tier-1 {
    border-left: 3px solid var(--tier-1);
    box-shadow: -1px 0 0 0 rgba(217, 119, 6, 0.08);
}

.citation-card.tier-2 {
    border-left: 3px solid var(--tier-2);
    box-shadow: -1px 0 0 0 rgba(37, 99, 235, 0.08);
}

.citation-card.tier-3 {
    border-left: 3px solid var(--tier-3);
    box-shadow: -1px 0 0 0 rgba(124, 58, 237, 0.08);
}

.citation-card.tier-4 {
    border-left: 3px solid var(--tier-4);
}

.citation-card-header {
    display: flex;
    align-items: center;
    gap: 6px;
}

.citation-card-header .source-number {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-primary);
}

.citation-card-header .tier-badge {
    font-size: 0.75rem;
}

.citation-card-title {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-primary);
    line-height: 1.4;
}

.citation-card-title .material-symbols-outlined {
    color: var(--text-muted);
    flex-shrink: 0;
}

.citation-snippet {
    font-size: 0.6875rem;
    color: var(--text-tertiary);
    font-style: italic;
    line-height: 1.4;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.citation-card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
}

.domain-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: capitalize;
    background: var(--bg-surface-active);
    color: var(--text-secondary);
}

.domain-badge.domain-legal {
    background: rgba(217, 119, 6, 0.1);
    color: #d97706;
}

.domain-badge.domain-accounting {
    background: rgba(16, 185, 129, 0.1);
    color: #10b981;
}

.domain-badge.domain-tax {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
}

.confidence-score {
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--text-muted);
}

.citations-panel-footer {
    padding: 8px var(--spacing-md);
    border-top: 1px solid var(--border-color-subtle);
    text-align: center;
}

.citations-panel-footer p {
    font-size: 0.6875rem;
    color: var(--text-muted);
    margin: 0;
}

/* ========================================
   Login Screen
   ======================================== */
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

/* Ambient glow blobs behind the login card */
.login-screen::before {
    content: '';
    position: absolute;
    top: 20%;
    left: 20%;
    width: 400px;
    height: 400px;
    background: radial-gradient(ellipse at center, rgba(79, 70, 229, 0.08) 0%, transparent 70%);
    pointer-events: none;
    border-radius: 50%;
    filter: blur(40px);
}

.login-screen::after {
    content: '';
    position: absolute;
    bottom: 15%;
    right: 15%;
    width: 350px;
    height: 350px;
    background: radial-gradient(ellipse at center, rgba(139, 92, 246, 0.07) 0%, transparent 70%);
    pointer-events: none;
    border-radius: 50%;
    filter: blur(40px);
}

.login-card {
    text-align: center;
    padding: 52px 48px;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 24px;
    box-shadow: var(--shadow-lg), 0 0 0 1px rgba(255, 255, 255, 0.03) inset;
    animation: slideUp 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
    max-width: 420px;
    width: 90%;
    position: relative;
    z-index: 1;
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

.login-brand .brand-logo {
    color: var(--text-primary);
}

.login-brand .brand-ai {
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

.login-footer-note {
    margin-top: 20px;
    font-size: 0.6875rem;
    color: var(--text-muted);
    text-align: center;
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
    position: relative;
    overflow: hidden;
}

.google-login-btn::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(66, 133, 244, 0.05), rgba(234, 67, 53, 0.03));
    opacity: 0;
    transition: opacity 0.2s ease;
}

.google-login-btn:hover::before {
    opacity: 1;
}

.google-login-btn:hover {
    background: var(--bg-surface-hover);
    border-color: rgba(66, 133, 244, 0.35);
    box-shadow: var(--shadow-md), 0 0 0 3px rgba(66, 133, 244, 0.08);
    transform: translateY(-1px);
}

.google-login-btn .material-symbols-outlined {
    color: #4285F4;
}

.login-divider {
    display: flex;
    align-items: center;
    margin: 24px 0;
    color: var(--text-muted);
    font-size: 13px;
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
    transition: border-color 0.2s ease;
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
}

.email-login-btn:hover {
    background: var(--accent-primary-hover);
    box-shadow: var(--shadow-md);
}

.email-login-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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

/* ========================================
   Responsive Design
   ======================================== */
@media (max-width: 1200px) {
    .column-citations {
        display: none;
    }
}

@media (max-width: 900px) {
    .column-viewer {
        display: none;
    }
}

@media (max-width: 640px) {
    .column-nav {
        position: absolute;
        left: 0;
        top: 56px;
        height: calc(100vh - 56px);
        z-index: 90;
        transform: translateX(-100%);
        transition: transform var(--transition-normal);
    }

    .column-nav.open {
        transform: translateX(0);
    }

    .conversation-title {
        max-width: 200px;
    }
}

/* ========================================
   Focus & Print Styles
   ======================================== */
button:focus-visible,
textarea:focus-visible,
[role="button"]:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
}

@media print {

    .top-bar,
    .column-nav,
    .column-citations {
        display: none !important;
    }

    .column-chat {
        width: 100% !important;
    }
}

/*  Inline Confirmation Dialog (Task 4.5)  */
.confirm-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(3px);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.15s ease;
}

.confirm-dialog {
    background: var(--surface, #1e2433);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 24px 28px;
    min-width: 300px;
    max-width: 420px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
    animation: slideUp 0.15s ease;
}

.confirm-title {
    margin: 0 0 8px;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary, #fff);
}

.confirm-message {
    margin: 0 0 20px;
    font-size: 0.875rem;
    color: var(--text-secondary, rgba(255, 255, 255, 0.7));
    line-height: 1.5;
}

.confirm-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
}

.confirm-btn-cancel,
.confirm-btn-delete {
    padding: 8px 18px;
    border-radius: 8px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.15s ease;
}

.confirm-btn-cancel {
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-primary, #fff);
}

.confirm-btn-cancel:hover {
    background: rgba(255, 255, 255, 0.14);
}

.confirm-btn-delete {
    background: #ef4444;
    color: #fff;
}

.confirm-btn-delete:hover {
    background: #dc2626;
}

@keyframes slideUp {
    from {
        transform: translateY(12px);
        opacity: 0;
    }

    to {
        transform: translateY(0);
        opacity: 1;
    }
}
```

---

## `app/app.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 5,660 bytes |
| **Exports** | `App` |

```typescript
﻿import {
  Component, inject, signal,
  ChangeDetectionStrategy
} from '@angular/core';
import { DOCUMENT } from '@angular/common';

import { ChatAreaComponent } from './components/chat/chat-area/chat-area';
import { DocumentViewerComponent } from './components/document-viewer/document-viewer';
import { CitationsPanelComponent } from './components/citations-panel/citations-panel';
import { NavPanelComponent } from './components/nav-panel/nav-panel';
import { LoginComponent } from './components/auth/login/login';

import { AuthService } from './services/auth.service';
import { SessionService } from './services/session.service';
import { AGENT_ENGINE } from './config/agent-engine.config';
import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    LoginComponent,
    NavPanelComponent,
    ChatAreaComponent,
    DocumentViewerComponent,
    CitationsPanelComponent,
  ],
  template: `
    @if (authService.user() || isDevBypass) {
      <!-- Authenticated: Four-column layout -->
      <div class="app app-layout">
        <!-- Top Bar -->
        <header class="top-bar">
          <div class="top-bar-left">
            <button class="menu-button" type="button" aria-label="Open menu">
              <span class="material-symbols-outlined" aria-hidden="true">menu</span>
            </button>
            <div class="brand" aria-label="ALT AI">
              <span class="brand-logo" aria-hidden="true">ALT</span>
              <span class="brand-ai" aria-hidden="true">AI</span>
            </div>
          </div>
          <div class="top-bar-center">
            <h2 class="conversation-title">{{ sessionService.conversationTitle() }}</h2>
          </div>
          <div class="top-bar-right">
            <div class="model-badge"
                 role="status"
                 [attr.aria-label]="'AI model: ' + modelName()"
                 title="Powered by Vertex AI Agent Engine">
              <span class="material-symbols-outlined" style="font-size:16px" aria-hidden="true">neurology</span>
              <span class="model-badge-label" aria-hidden="true">{{ modelName() }}</span>
            </div>
            <button class="theme-toggle" type="button" (click)="toggleTheme()"
                    [attr.aria-label]="isDark() ? 'Switch to light mode' : 'Switch to dark mode'">
              <span class="material-symbols-outlined" aria-hidden="true">{{ isDark() ? 'light_mode' : 'dark_mode' }}</span>
            </button>
            <div class="user-menu-container">
              <button class="profile-button" type="button"
                      (click)="showUserMenu.set(!showUserMenu())"
                      aria-label="User profile"
                      aria-haspopup="true"
                      [attr.aria-expanded]="showUserMenu() ? 'true' : 'false'">
                <span class="material-symbols-outlined" aria-hidden="true">person</span>
                <span class="material-symbols-outlined chevron" aria-hidden="true" [class.open]="showUserMenu()">expand_more</span>
              </button>
              @if (showUserMenu()) {
                <div class="user-dropdown" role="menu" aria-label="User options">
                  <div class="user-info" role="none">
                    <span class="user-name">{{ authService.user()?.displayName || 'User' }}</span>
                    <span class="user-email">{{ authService.user()?.email }}</span>
                  </div>
                  <div class="dropdown-divider" role="separator"></div>
                  <button class="dropdown-item logout-button" type="button" role="menuitem" (click)="authService.logout()">
                    <span class="material-symbols-outlined" style="font-size:16px" aria-hidden="true">logout</span>
                    <span>Sign Out</span>
                  </button>
                </div>
              }
            </div>
          </div>
        </header>

        <!-- Main Four-Column Layout -->
        <main class="main-layout" aria-label="Application">
          <div class="column column-nav">
            <app-nav-panel></app-nav-panel>
          </div>
          <div class="column column-chat" role="region" aria-label="Chat">
            <app-chat-area></app-chat-area>
          </div>
          <div class="column column-viewer" role="region" aria-label="Document viewer">
            <app-document-viewer></app-document-viewer>
          </div>
          <div class="column column-citations" role="region" aria-label="Citations">
            <app-citations-panel></app-citations-panel>
          </div>
        </main>
      </div>
    } @else {
      <app-login></app-login>
    }
  `,
  styleUrl: './app.css'
})
export class App {
  protected readonly authService = inject(AuthService);
  protected readonly sessionService = inject(SessionService);

  protected readonly isDevBypass = !environment.production && environment.devBypassAuth === true;

  protected readonly showUserMenu = signal(false);
  protected readonly isDark = signal(false);
  // Model name — read from the same config used by AgentEngineService.
  // Previously fetched from a /model Cloud Function (now deleted).
  protected readonly modelName = signal(`gemini-2.5-flash (Engine ${AGENT_ENGINE.ENGINE_ID.slice(-6)})`);

  private readonly document = inject(DOCUMENT);

  toggleTheme() {
    this.isDark.update(v => !v);
    this.document.documentElement.classList.toggle('dark', this.isDark());
  }

}
```
