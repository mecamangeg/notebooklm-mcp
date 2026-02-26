# citations-panel

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__citations-panel` |
| **Files** | 1 |
| **Total size** | 15,622 bytes |
| **Generated** | 2026-02-26 11:02 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/citations-panel/citations-panel.ts` (15,622 bytes, Source)

---

## `app/components/citations-panel/citations-panel.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 15,622 bytes |
| **Exports** | `CitationsPanelComponent` |

```typescript
import {
  Component, inject, signal, computed, ChangeDetectionStrategy
} from '@angular/core';

import { SessionService } from '../../services/session.service';
import { DocumentViewerService } from '../../services/document-viewer.service';
import { Citation } from '../../models/types';
import { TruncateSnippetPipe } from '../../pipes/truncate-snippet.pipe';

// Pure module-level helpers — no class exposure needed
const TIER_CONFIG: Record<number, { label: string; icon: string }> = {
  1: { label: 'Supreme Authority', icon: 'account_balance' },
  2: { label: 'Primary Sources', icon: 'star' },
  3: { label: 'Supporting Sources', icon: 'circle' },
  4: { label: 'Reference Material', icon: 'radio_button_unchecked' },
};

const DOMAIN_ICONS: Record<string, string> = {
  legal: 'gavel',
  accounting: 'calculate',
  tax: 'receipt_long',
  general: 'description'
};

function getDomainIcon(domain?: string): string {
  return domain ? (DOMAIN_ICONS[domain] || 'description') : 'description';
}

// Note: Snippet sanitization (stripping [[FN...]] + HTML) happens at extraction time
// in citation-extractor.ts sanitizeSnippet(). Display truncation to 280 chars is
// handled by TruncateSnippetPipe in the template.

@Component({
  selector: 'app-citations-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TruncateSnippetPipe],
  styles: [`
    :host {
      display: contents;
    }

    /* ── Panel Shell ── */
    .citations-panel {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      background: var(--bg-surface);
      font-size: 13px;
    }

    /* ── Header ── */
    .citations-panel-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--border-color-subtle);
      flex-shrink: 0;
    }

    .citations-panel-header h3 {
      font-size: 0.9375rem;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0;
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

    /* ── Scrollable content ── */
    .citations-panel-content {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
      scrollbar-width: thin;
      scrollbar-color: var(--border-color) transparent;
    }

    /* ── Empty state ── */
    .empty-citations {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 32px 16px;
      text-align: center;
      color: var(--text-muted);
    }

    .empty-icon {
      font-size: 32px;
      margin-bottom: 12px;
      opacity: 0.4;
    }

    .empty-hint {
      font-size: 0.75rem;
      margin-top: 4px;
    }

    /* ── Tier Groups ── */
    .tier-group {
      margin-bottom: 8px;
    }

    .tier-header {
      display: flex;
      align-items: center;
      gap: 4px;
      width: 100%;
      padding: 6px 4px;
      background: transparent;
      border: none;
      color: var(--text-secondary);
      font-size: 0.6875rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      cursor: pointer;
      transition: color 150ms ease;
      text-align: left;
      font-family: inherit;
    }

    .tier-header:hover { color: var(--text-primary); }
    .tier-icon { font-size: 14px; }
    .tier-label { flex: 1; text-align: left; }

    .tier-count {
      padding: 1px 6px;
      background: var(--bg-surface-active);
      border-radius: 9999px;
      font-size: 0.625rem;
      color: var(--text-muted);
      font-weight: 600;
    }

    /* Tier-colored headers */
    .tier-group.tier-1 .tier-header { color: var(--tier-1); }
    .tier-group.tier-1 .tier-header:hover { opacity: 0.8; }
    .tier-group.tier-2 .tier-header { color: var(--tier-2); }
    .tier-group.tier-2 .tier-header:hover { opacity: 0.8; }
    .tier-group.tier-3 .tier-header { color: var(--tier-3); }
    .tier-group.tier-3 .tier-header:hover { opacity: 0.8; }
    .tier-group.tier-4 .tier-header { color: var(--text-muted); }
    .tier-group.tier-4 .tier-header:hover { color: var(--text-secondary); }

    .tier-citations {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding-left: 4px;
    }

    /* ── Citation Cards ── */
    .citation-card {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 10px;
      background: var(--bg-surface);
      border: 1px solid var(--border-color-subtle);
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.18s ease;
      width: 100%;
      text-align: left;
      font-family: inherit;
      font-size: inherit;
      color: inherit;
    }

    .citation-card:hover {
      background: var(--bg-surface-hover);
      border-color: var(--border-color);
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
      transform: translateY(-1px);
    }

    /* Tier left-accent bars (Stitch design) */
    .citation-card.tier-1 {
      border-left: 3px solid var(--tier-1);
    }
    .citation-card.tier-2 {
      border-left: 3px solid var(--tier-2);
    }
    .citation-card.tier-3 {
      border-left: 3px solid var(--tier-3);
    }
    .citation-card.tier-4 {
      border-left: 3px solid var(--tier-4);
    }

    /* Tier badge icon colors */
    .tier-badge.tier-1 { color: var(--tier-1); }
    .tier-badge.tier-2 { color: var(--tier-2); }
    .tier-badge.tier-3 { color: var(--tier-3); }
    .tier-badge.tier-4 { color: var(--text-muted); }

    .citation-card-header {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .source-number {
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--text-primary);
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

    /* ── Domain badges ── */
    .domain-badge {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 0.625rem;
      font-weight: 600;
      text-transform: capitalize;
      background: var(--bg-surface-active);
      color: var(--text-secondary);
    }

    .domain-badge.domain-legal {
      background: rgba(245, 158, 11, 0.1);
      color: var(--tier-1);
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

    /* ── Year-based YELLOW flag (Signal & Citator pattern) ── */
    .year-flag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 6px;
      background: rgba(251, 140, 0, 0.08);
      border: 1px solid rgba(251, 140, 0, 0.25);
      border-radius: 4px;
      color: #e65100;
      font-size: 0.6rem;
      font-weight: 600;
      line-height: 1.3;
    }
    :host-context(.dark) .year-flag {
      background: rgba(251, 140, 0, 0.10);
      border-color: rgba(251, 140, 0, 0.22);
      color: #ffb74d;
    }
    .year-flag-icon { font-size: 11px; }

    /* ── Footer ── */
    .citations-panel-footer {
      padding: 8px 14px;
      border-top: 1px solid var(--border-color-subtle);
      text-align: center;
      flex-shrink: 0;
    }

    .citations-panel-footer p {
      font-size: 0.6875rem;
      color: var(--text-muted);
      margin: 0;
    }
  `],
  template: `
    <aside class="citations-panel" aria-label="Citations and sources">
      <section style="display:contents" aria-labelledby="citations-heading">
      <div class="citations-panel-header">
        <span class="material-symbols-outlined" style="font-size:18px" aria-hidden="true">menu_book</span>
        <h3 id="citations-heading">Sources</h3>
        @if (sessionService.currentCitations().length > 0) {
          <span class="citation-count"
                [attr.aria-label]="sessionService.currentCitations().length + ' sources'">
            {{ sessionService.currentCitations().length }}
          </span>
        }
      </div>
      <div class="citations-panel-content">
        @if (sessionService.currentCitations().length === 0) {
          <div class="empty-citations" aria-live="polite" aria-atomic="true">
            <span class="material-symbols-outlined empty-icon" aria-hidden="true">menu_book</span>
            <p>No sources yet</p>
            <p class="empty-hint">Sources will appear here when AI provides citations</p>
          </div>
        } @else {
        @for (tierGroup of citationTierGroups(); track tierGroup.tier) {
            @if (tierGroup.citations.length > 0) {
              <div class="tier-group" [class]="'tier-' + tierGroup.tier">
                <button class="tier-header" type="button" (click)="toggleTier(tierGroup.tier)"
                  [attr.aria-label]="tierGroup.label + ' sources'"
                  [attr.aria-expanded]="expandedTiers()[tierGroup.tier] ? 'true' : 'false'"
                  [attr.aria-controls]="'tier-' + tierGroup.tier + '-content'">
                  <span class="material-symbols-outlined" style="font-size:14px" aria-hidden="true">
                    {{ expandedTiers()[tierGroup.tier] ? 'expand_more' : 'chevron_right' }}
                  </span>
                  <span class="tier-icon material-symbols-outlined" aria-hidden="true" style="font-size:14px">{{ tierGroup.icon }}</span>
                  <span class="tier-label">{{ tierGroup.label }}</span>
                  <span class="tier-count" aria-hidden="true">{{ tierGroup.citations.length }}</span>
                </button>

                @if (expandedTiers()[tierGroup.tier]) {
                  <div class="tier-citations" [id]="'tier-' + tierGroup.tier + '-content'">
                    @for (citation of tierGroup.citations; track citation.id) {
                      <button
                        type="button"
                        class="citation-card"
                        [class]="'tier-' + citation.tier + ' domain-' + citation.domain"
                        (click)="openCitationDoc(citation)"
                        [attr.aria-label]="'Open source: ' + citation.title"
                      >
                        <div class="citation-card-header">
                          <span class="source-number">[{{ citation.sourceNumber }}]</span>
                          <span class="tier-badge material-symbols-outlined" [class]="'tier-' + citation.tier" style="font-size:14px" aria-hidden="true">
                            {{ citation.tierBadge }}
                          </span>
                        </div>
                        <div class="citation-card-title">
                          <span class="material-symbols-outlined" style="font-size:14px" aria-hidden="true">description</span>
                          <span>{{ citation.title }}</span>
                        </div>
                        @if (citation.snippet) {
                          <p class="citation-snippet">"{{ citation.snippet | truncateSnippet:280 }}"</p>
                        }
                        @if (citation.yearFlag) {
                          <span class="year-flag" [attr.title]="'Case decided ' + citation.year + ' — verify currency before citing'">
                            <span class="material-symbols-outlined year-flag-icon" aria-hidden="true">history</span>
                            ⚠️ {{ citation.year }} — verify currency
                          </span>
                        }
                        <div class="citation-card-footer">
                          <span class="domain-badge" [class]="'domain-' + citation.domain">
                            <span class="material-symbols-outlined" style="font-size:12px" aria-hidden="true">{{ citation.domainIcon }}</span>
                            {{ citation.domain }}
                          </span>
                          @if (citation.confidenceLabel) {
                            <span class="confidence-score">{{ citation.confidenceLabel }}</span>
                          }
                        </div>
                      </button>
                    }
                  </div>
                }
              </div>
            }
          }
        }
      </div>

      @if (sessionService.currentCitations().length > 0) {
        <div class="citations-panel-footer">
          <p aria-hidden="true">Click any source to view the original document</p>
        </div>
      }
      </section>
    </aside>
  `
})
export class CitationsPanelComponent {
  protected readonly sessionService = inject(SessionService);
  private readonly docViewer = inject(DocumentViewerService);

  protected readonly expandedTiers = signal<Record<number, boolean>>({
    1: true,
    2: true,
    3: true,
    4: false
  });

  // All display data pre-computed — no Math/helper calls in template
  protected readonly citationTierGroups = computed(() => {
    const citations = this.sessionService.currentCitations();
    return [1, 2, 3, 4].map(tier => ({
      tier,
      label: TIER_CONFIG[tier]?.label || 'Other',
      icon: TIER_CONFIG[tier]?.icon || 'radio_button_unchecked',
      citations: citations
        .filter(c => c.tier === tier)
        .map(c => ({
          ...c,
          tierBadge: TIER_CONFIG[c.tier ?? 4]?.icon || 'radio_button_unchecked',
          domainIcon: getDomainIcon(c.domain),
          // confidence is undefined for Gemini 2.5+ — show no badge when absent
          confidenceLabel: c.confidence ? `${Math.round(c.confidence * 100)}%` : null,
          // yearFlag and year passed through from Citation — rendered as YELLOW flag
          yearFlag: c.yearFlag ?? false,
          year: c.year,
        }))
    }));
  });

  toggleTier(tier: number) {
    this.expandedTiers.update(prev => ({ ...prev, [tier]: !prev[tier] }));
  }

  openCitationDoc(citation: Citation) {
    if (citation.uri) {
      // Use highlightText (full verbatim text) for best treewalk match.
      // Falls back to snippet if highlightText not set (older citations).
      this.docViewer.openDocument(
        citation.uri,
        citation.title,
        citation.highlightText || citation.snippet
      );
    }
  }
}
```
