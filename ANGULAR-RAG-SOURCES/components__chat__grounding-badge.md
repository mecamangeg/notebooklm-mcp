# grounding-badge

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__chat__grounding-badge` |
| **Files** | 1 |
| **Total size** | 7,325 bytes |
| **Generated** | 2026-02-26 11:07 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/chat/grounding-badge/grounding-badge.ts` (7,325 bytes, Source)

---

## `app/components/chat/grounding-badge/grounding-badge.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 7,325 bytes |
| **Exports** | `GroundingBadgeComponent` |

```typescript
import { Component, ChangeDetectionStrategy, computed, input, signal } from '@angular/core';
import type { GroundingAudit, Citation } from '../../../models/types';

/**
 * GroundingBadgeComponent — Layer 2 per-response trust badge.
 *
 * Implements the Signal & Citator pattern (2026-02-25 architectural decision):
 *
 *   🔴 RED warning  → Any claim un-grounded (AI hallucinated text not in retrieved sources)
 *   ℹ️ GREY info    → No RED condition; neutral source count (non-evaluative)
 *   ~~✅ GREEN~~    → NEVER SHOWN (Citator Paradox — would imply legal accuracy)
 *
 * The Citator Paradox: `checkGrounding` is closed-loop — it validates the response
 * against the snippets WE supply. An overturned 1995 case accurately summarised
 * still scores GREEN. Industry standard (Westlaw KeyCite / Lexis Shepard's) never
 * shows a GREEN "correct law" badge — only absence of warning means no problems found.
 *
 * The YELLOW per-citation year flag (for decisions > 15 years old) is rendered
 * separately in ParsedContent/tooltip — not here. This component is response-level only.
 *
 * Usage:
 *   <app-grounding-badge [audit]="message().audit" [citations]="message().citations || []" />
 *
 * Angular MCP-validated (2026-02-25):
 *   - Standalone, OnPush, input() signals
 *   - @if control flow (not *ngIf)
 *   - No constructor injection — inject() in field
 *   - computed() for derived state
 */
@Component({
    selector: 'app-grounding-badge',
    changeDetection: ChangeDetectionStrategy.OnPush,
    template: `
        @if (showRedWarning()) {
            <!-- RED: Hallucination detected — AI text not found in retrieved sources -->
            <div
                class="grounding-badge grounding-red"
                role="alert"
                aria-live="assertive"
                [attr.title]="redTooltip()"
            >
                <span class="material-symbols-outlined grounding-icon" aria-hidden="true">warning</span>
                <span class="grounding-label">Claims unverified — review before relying</span>
                @if (ungroundedCount() > 0) {
                    <span class="grounding-detail">{{ ungroundedCount() }} unverified</span>
                }
            </div>
        } @else if (audit()) {
            <!-- GREY: Neutral source count — non-evaluative, does NOT imply legal correctness -->
            <!-- Clicking expands to show the snippet panel (future enhancement) -->
            <div
                class="grounding-badge grounding-grey"
                [attr.title]="greyTooltip()"
                role="status"
                aria-live="polite"
                (click)="toggleSnippets()"
                (keydown.enter)="toggleSnippets()"
                (keydown.space)="$event.preventDefault(); toggleSnippets()"
                tabindex="0"
                style="cursor: pointer"
            >
                <span class="material-symbols-outlined grounding-icon" aria-hidden="true">info</span>
                <span class="grounding-label">{{ greyLabel() }}</span>
                <span class="grounding-detail">· {{ scorePercent() }}% support</span>
            </div>
            <!-- NO GREEN badge — Citator Paradox: GREEN implies legal accuracy,
                 which checkGrounding cannot guarantee. Industry standard (Westlaw KeyCite,
                 Lexis Shepard's) uses absence of warning, not presence of green. -->
        }
    `,
    styles: [`
        .grounding-badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            margin-top: 10px;
            padding: 4px 10px 4px 8px;
            border-radius: 20px;
            font-size: 11.5px;
            font-weight: 500;
            width: fit-content;
            animation: badgeFadeIn 0.35s ease both;
            outline-offset: 2px;
        }

        .grounding-badge:focus-visible {
            outline: 2px solid currentColor;
        }

        @keyframes badgeFadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        /* ── GREY: neutral, non-evaluative — "no warning" signal ── */
        .grounding-grey {
            background: rgba(158, 158, 158, 0.08);
            border: 1px solid rgba(158, 158, 158, 0.28);
            color: #616161;
        }
        :host-context(.dark) .grounding-grey {
            background: rgba(200, 200, 200, 0.08);
            border-color: rgba(200, 200, 200, 0.20);
            color: #9e9e9e;
        }

        /* ── RED: hallucination warning — clear problem signal ── */
        .grounding-red {
            background: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.35);
            color: rgb(185, 28, 28);
        }
        :host-context(.dark) .grounding-red {
            background: rgba(239, 68, 68, 0.12);
            border-color: rgba(239, 68, 68, 0.40);
            color: rgb(252, 129, 129);
        }

        .grounding-icon {
            font-size: 13px;
            flex-shrink: 0;
        }

        .grounding-label {
            font-weight: 600;
        }

        .grounding-detail {
            font-weight: 400;
            opacity: 0.75;
        }
    `],
})
export class GroundingBadgeComponent {
    readonly audit = input<GroundingAudit | undefined>(undefined);
    readonly citations = input<Citation[]>([]);

    /** Snippet panel toggle state (for future expand-on-click feature) */
    protected readonly snippetsOpen = signal(false);

    /**
     * RED fires when: any factual claim is grounded=false AND score < 0.5.
     * This is the primary value of checkGrounding — catching text the AI invented.
     */
    protected readonly showRedWarning = computed(() => {
        const a = this.audit();
        if (!a) return false;
        return a.claims?.some(c => !c.grounded && (c.score ?? 0) < 0.5) ?? false;
    });

    protected readonly ungroundedCount = computed(() => {
        const a = this.audit();
        if (!a?.claims) return 0;
        return a.claims.filter(c => !c.grounded && (c.score ?? 0) < 0.5).length;
    });

    protected readonly scorePercent = computed(() => {
        const a = this.audit();
        return a ? Math.round(a.confidence * 100) : 0;
    });

    protected readonly greyLabel = computed(() => {
        const count = this.citations().length || this.audit()?.docsUsed || 0;
        return `Sources: ${count} verified citation${count !== 1 ? 's' : ''}`;
    });

    protected readonly greyTooltip = computed(() =>
        'Sources confirmed present in retrieved documents. ' +
        'This does not verify legal currency — always confirm case standing.'
    );

    protected readonly redTooltip = computed(() =>
        'One or more claims could not be verified in retrieved sources. ' +
        'The AI may have generated text beyond what was retrieved. Review before relying.'
    );

    protected toggleSnippets(): void {
        this.snippetsOpen.update(v => !v);
        // Future: emit event to parent to expand a snippet panel
    }
}
```
