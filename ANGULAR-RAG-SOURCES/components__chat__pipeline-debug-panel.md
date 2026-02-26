# pipeline-debug-panel

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__chat__pipeline-debug-panel` |
| **Files** | 1 |
| **Total size** | 12,949 bytes |
| **Generated** | 2026-02-26 11:07 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/chat/pipeline-debug-panel/pipeline-debug-panel.ts` (12,949 bytes, Source)

---

## `app/components/chat/pipeline-debug-panel/pipeline-debug-panel.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-24 |
| **Size** | 12,949 bytes |
| **Exports** | `PipelineDebugPanelComponent` |

```typescript
import { Component, input, computed, signal, ChangeDetectionStrategy } from '@angular/core';
import { DebugData } from '../../../services/chat.service';

@Component({
  selector: 'app-pipeline-debug-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [],
  template: `
    @if (debugData()) {
      <div class="debug-panel" [class.collapsed]="collapsed()" id="pipeline-debug-panel">
        <button class="debug-toggle" type="button"
          id="debug-panel-toggle"
          [attr.aria-expanded]="collapsed() ? 'false' : 'true'"
          aria-controls="debug-panel-content"
          aria-label="Pipeline debug information"
          (click)="collapsed.set(!collapsed())">
          <span class="material-symbols-outlined toggle-icon" aria-hidden="true">
            {{ collapsed() ? 'bug_report' : 'expand_more' }}
          </span>
          <span class="toggle-label">Pipeline Debug</span>
          @if (collapsed() && totalLatency()) {
            <span class="latency-badge" aria-hidden="true">{{ totalLatency() }}ms</span>
          }
        </button>

        @if (!collapsed()) {
          <div class="debug-content" id="debug-panel-content">
            <!-- Trace ID & Intent Row -->
            <div class="debug-row">
              <div class="debug-item">
                <span class="debug-label">Trace</span>
                <span class="debug-value mono">{{ debugData()!.traceId }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-label">Intent</span>
                <span class="debug-value intent-badge" [class]="'intent-' + debugData()!.intent.toLowerCase()">
                  {{ debugData()!.intent }}
                </span>
              </div>
              <div class="debug-item">
                <span class="debug-label">Path</span>
                <span class="debug-value">{{ debugData()!.path }}</span>
              </div>
            </div>

            <!-- Latency Breakdown -->
            <div class="debug-section">
              <span class="section-title">
                <span class="material-symbols-outlined" aria-hidden="true">timer</span>
                Latency
              </span>
              <div class="latency-bars">
                @for (item of latencyItems(); track item.label) {
                  <div class="latency-item">
                    <span class="latency-label">{{ item.label }}</span>
                    <div class="latency-bar-track">
                      <div
                        class="latency-bar-fill"
                        [style.width.%]="item.percent"
                        [class]="'bar-' + item.color"
                      ></div>
                    </div>
                    <span class="latency-ms">{{ item.ms }}ms</span>
                  </div>
                }
              </div>
            </div>

            <!-- Search & Grounding Row -->
            <div class="debug-row">
              <div class="debug-item">
                <span class="debug-label">Search Results</span>
                <span class="debug-value">{{ debugData()!.search.resultCount }}</span>
              </div>
              @if (debugData()!.search.rerankerOrderChanged) {
                <div class="debug-item">
                  <span class="debug-label">Reranked</span>
                  <span class="debug-value reranked">
                    <span class="material-symbols-outlined" aria-hidden="true">swap_vert</span>
                    Yes
                  </span>
                </div>
              }
              @if (debugData()!.grounding.score !== null) {
                <div class="debug-item">
                  <span class="debug-label">Grounding</span>
                  <span
                    class="debug-value grounding-badge"
                    [class]="'grounding-' + debugData()!.grounding.level?.toLowerCase()"
                  >
                    {{ (debugData()!.grounding.score! * 100).toFixed(0) }}%
                    ({{ debugData()!.grounding.groundedClaims }}/{{ debugData()!.grounding.totalClaims }})
                  </span>
                </div>
              }
            </div>

            <!-- Cost & Model Row -->
            <div class="debug-row">
              <div class="debug-item">
                <span class="debug-label">Model</span>
                <span class="debug-value mono">{{ debugData()!.model }}</span>
              </div>
              <div class="debug-item">
                <span class="debug-label">Tokens</span>
                <span class="debug-value">
                  {{ debugData()!.cost.inputTokens }}&darr; / {{ debugData()!.cost.outputTokens }}&uarr;
                </span>
              </div>
              <div class="debug-item">
                <span class="debug-label">Cost</span>
                <span class="debug-value cost">
                  {{'$'}}{{ debugData()!.cost.totalUsd.toFixed(6) }}
                </span>
              </div>
            </div>

            <!-- Cloud Console Link -->
            @if (debugData()!.logUrl) {
              <a
                class="console-link"
                [href]="debugData()!.logUrl"
                target="_blank"
                rel="noopener"
                id="debug-cloud-console-link"
                aria-label="View in Cloud Logging (opens in new tab)"
              >
                <span class="material-symbols-outlined" aria-hidden="true">open_in_new</span>
                View in Cloud Logging
              </a>
            }

            <!-- Error -->
            @if (debugData()!.error) {
              <div class="debug-error" role="alert">
                <span class="material-symbols-outlined" aria-hidden="true">error</span>
                {{ debugData()!.error }}
              </div>
            }
          </div>
        }
      </div>
    }
  `,
  styles: [`
    /*
     * All colours use the app's global CSS custom properties from styles.scss.
     * :root defines light-mode values; .dark overrides them automatically.
     * No hardcoded hex values here — the panel inherits the current theme.
     */

    .debug-panel {
      margin-top: 8px;
      border: 1px solid var(--border-color-subtle);
      border-radius: 8px;
      background: var(--bg-surface-active);
      font-size: 12px;
      overflow: hidden;
      animation: debugFadeIn 0.3s ease;
    }

    @keyframes debugFadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to   { opacity: 1; transform: translateY(0);   }
    }

    .debug-toggle {
      width: 100%;
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      background: transparent;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 11px;
      transition: all 0.2s ease;

      &:hover {
        color: var(--text-secondary);
        background: var(--bg-surface-hover);
      }
    }

    .toggle-icon { font-size: 16px; }

    .toggle-label {
      font-weight: 600;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      font-size: 10px;
    }

    .latency-badge {
      margin-left: auto;
      background: rgba(99, 102, 241, 0.12);
      color: var(--accent-primary);
      padding: 1px 6px;
      border-radius: 4px;
      font-variant-numeric: tabular-nums;
      font-weight: 600;
    }

    .debug-content {
      padding: 8px 10px 10px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      border-top: 1px solid var(--border-color-subtle);
    }

    .debug-row {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }

    .debug-item {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .debug-label {
      font-size: 10px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.4px;
      font-weight: 600;
    }

    .debug-value {
      color: var(--text-secondary);
      font-weight: 500;
    }

    .debug-value.mono {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 11px;
      color: var(--text-tertiary);
    }

    /* Intent badge — colours stay vivid in both themes */
    .intent-badge {
      padding: 1px 6px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }

    .intent-lookup       { background: rgba(59,130,246,0.12);  color: #60a5fa; }
    .intent-drafting     { background: rgba(168,85,247,0.12);  color: #c084fc; }
    .intent-conversational { background: rgba(34,197,94,0.12); color: #4ade80; }

    /* ── Latency section ── */
    .debug-section {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .section-title {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 10px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.4px;
      font-weight: 600;

      .material-symbols-outlined { font-size: 13px; }
    }

    .latency-bars { display: flex; flex-direction: column; gap: 4px; }

    .latency-item {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .latency-label {
      width: 70px;
      text-align: right;
      font-size: 11px;
      color: var(--text-muted);
    }

    .latency-bar-track {
      flex: 1;
      height: 6px;
      background: var(--border-color-subtle);
      border-radius: 3px;
      overflow: hidden;
    }

    .latency-bar-fill {
      height: 100%;
      border-radius: 3px;
      transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
      min-width: 2px;
    }

    /* Bar fills keep their accent colours in both themes */
    .bar-blue   { background: var(--accent-primary); }
    .bar-purple { background: var(--tier-4); }
    .bar-amber  { background: var(--warning); }
    .bar-teal   { background: var(--success); }

    .latency-ms {
      width: 50px;
      text-align: right;
      font-size: 11px;
      font-variant-numeric: tabular-nums;
      color: var(--text-secondary);
      font-weight: 500;
    }

    /* Reranked pill */
    .reranked {
      display: flex;
      align-items: center;
      gap: 2px;
      color: var(--warning);
      .material-symbols-outlined { font-size: 14px; }
    }

    /* Grounding badge — theme-aware via accent */
    .grounding-badge {
      padding: 1px 6px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }

    .grounding-green  { background: rgba(16,185,129,0.12); color: var(--success); }
    .grounding-yellow { background: rgba(245,158,11,0.12); color: var(--warning); }
    .grounding-red    { background: rgba(239,68,68,0.12);  color: var(--error);   }

    /* Cost — use muted text so it looks subdued */
    .cost {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      color: var(--text-muted);
    }

    /* Cloud Logging link */
    .console-link {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      color: var(--accent-primary);
      text-decoration: none;
      padding: 4px 0;
      transition: opacity 0.2s;

      .material-symbols-outlined { font-size: 14px; }

      &:hover { opacity: 0.75; text-decoration: underline; }
    }

    /* Error pill */
    .debug-error {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 8px;
      background: rgba(239,68,68,0.08);
      border-radius: 4px;
      color: var(--error);
      font-size: 11px;

      .material-symbols-outlined { font-size: 14px; }
    }
  `]
})
export class PipelineDebugPanelComponent {
  /** Pass the per-message debug data directly — no longer depends on global ChatService signal */
  readonly debugData = input<DebugData | null | undefined>(null);
  protected readonly collapsed = signal(true);

  protected readonly totalLatency = computed(() => this.debugData()?.latency.total || 0);

  protected readonly latencyItems = computed(() => {
    const d = this.debugData();
    if (!d) return [];
    const total = d.latency.total || 1;
    return [
      { label: 'Classifier', ms: d.latency.classifier, percent: (d.latency.classifier / total) * 100, color: 'teal' },
      { label: 'LLM', ms: d.latency.llm, percent: (d.latency.llm / total) * 100, color: 'purple' },
      { label: 'Grounding', ms: d.latency.grounding, percent: (d.latency.grounding / total) * 100, color: 'amber' },
      { label: 'Reranker', ms: d.latency.reranker, percent: (d.latency.reranker / total) * 100, color: 'blue' },
    ].filter(i => i.ms > 0);
  });
}
```
