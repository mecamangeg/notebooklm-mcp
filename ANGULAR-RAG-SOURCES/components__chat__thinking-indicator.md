# thinking-indicator

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__chat__thinking-indicator` |
| **Files** | 1 |
| **Total size** | 8,163 bytes |
| **Generated** | 2026-02-26 11:03 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/chat/thinking-indicator/thinking-indicator.ts` (8,163 bytes, Source)

---

## `app/components/chat/thinking-indicator/thinking-indicator.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-24 |
| **Size** | 8,163 bytes |
| **Exports** | `ThinkingIndicatorComponent` |

```typescript
import { Component, input, computed, signal, inject, ChangeDetectionStrategy, DestroyRef } from '@angular/core';

@Component({
  selector: 'app-thinking-indicator',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [],
  template: `
    <div class="thinking-container"
         role="status"
         aria-live="polite"
         aria-atomic="true"
         [attr.aria-label]="'ALT AI is ' + (label() || phaseLabel())">
      <div class="avatar-container" aria-hidden="true">
        <div class="avatar">
           <span class="material-symbols-outlined">cognition</span>
        </div>
      </div>
      <div class="content">
        <div class="phase-info">
          <div class="phase-badge">
            <span class="dot"></span>
            {{ label() || phaseLabel() }}
          </div>
          @if (phaseIndex() > 0 && totalPhases() > 0) {
            <div class="phase-progress" aria-hidden="true">
              @for (i of phaseSteps(); track i) {
                <div
                  class="progress-step"
                  [class.active]="i <= phaseIndex()"
                  [class.current]="i === phaseIndex()"
                ></div>
              }
            </div>
          }
        </div>

        @if (showMeta()) {
          <div class="meta-info" role="status" aria-live="polite">
            <span class="material-symbols-outlined" aria-hidden="true">search</span>
            {{ metaLabel() }}
          </div>
        }

        <div class="skeleton-lines" aria-hidden="true">
          <div class="line"></div>
          <div class="line short"></div>
        </div>

        @if (showSlowWarning()) {
          <div class="slow-warning" role="alert" aria-live="assertive">
            <span class="material-symbols-outlined" aria-hidden="true">schedule</span>
            Taking longer than expected...
          </div>
        }

        @if (elapsedLabel()) {
          <div class="elapsed-time" aria-hidden="true">{{ elapsedLabel() }}</div>
        }
      </div>
    </div>
  `,
  styles: [`
    .thinking-container {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 14px 18px;
      margin: 4px 0 8px 0;
      border-radius: var(--radius-lg);
      background: rgba(79, 70, 229, 0.04);
      border: 1px solid rgba(79, 70, 229, 0.08);
      border-left: 3px solid var(--accent-primary);
      animation: thinkingSlideIn 0.35s cubic-bezier(0.22, 1, 0.36, 1);
    }

    .avatar {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: var(--accent-gradient);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      flex-shrink: 0;
      span { font-size: 20px; }
    }

    .content {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .phase-info {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .phase-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8125rem;
      font-weight: 500;
      color: var(--text-secondary);
      letter-spacing: 0.01em;

      .dot {
        width: 6px;
        height: 6px;
        background: var(--accent-primary);
        border-radius: 50%;
        animation: thinkingPulse 1.4s ease-in-out infinite;
      }
    }

    /* ── Phase progress dots ── */
    .phase-progress {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    .progress-step {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--border-color-strong);
      transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);

      &.active {
        background: var(--accent-primary);
        transform: scale(1.1);
      }

      &.current {
        background: var(--accent-primary);
        animation: thinkingPulse 1.4s ease-in-out infinite;
        transform: scale(1.2);
      }
    }

    /* ── Meta info (e.g. "5 sources found") ── */
    .meta-info {
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: 0.75rem;
      color: var(--accent-primary);
      background: rgba(79, 70, 229, 0.06);
      padding: 3px 10px;
      border-radius: 12px;
      width: fit-content;
      animation: metaSlideIn 0.3s ease;

      .material-symbols-outlined {
        font-size: 13px;
      }
    }

    /* ── Skeleton lines ── */
    .skeleton-lines {
      display: flex;
      flex-direction: column;
      gap: 6px;

      .line {
        height: 12px;
        background: var(--bg-surface-hover);
        border-radius: 4px;
        position: relative;
        overflow: hidden;

        &::after {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          height: 100%;
          width: 50%;
          background: linear-gradient(90deg, transparent, var(--bg-surface-active), transparent);
          animation: shimmer 1.5s infinite;
        }

        &.short { width: 60%; }
      }
    }

    /* ── Slow warning ── */
    .slow-warning {
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: 0.75rem;
      color: #f59e0b;
      margin-top: 2px;
      animation: fadeIn 0.4s ease;

      .material-symbols-outlined {
        font-size: 14px;
      }
    }

    /* ── Elapsed time ── */
    .elapsed-time {
      font-size: 0.6875rem;
      color: var(--text-muted);
      font-variant-numeric: tabular-nums;
    }

    @keyframes thinkingPulse {
      0%, 80%, 100% { opacity: 0.25; transform: scale(0.8); }
      40% { opacity: 1; transform: scale(1.15); }
    }

    @keyframes shimmer {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(200%); }
    }

    @keyframes thinkingSlideIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @keyframes metaSlideIn {
      from { opacity: 0; transform: translateX(-6px); }
      to { opacity: 1; transform: translateX(0); }
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
  `]
})
export class ThinkingIndicatorComponent {
  // Phase inputs
  phase = input<'searching' | 'analyzing' | 'synthesizing' | 'idle'>('searching');
  label = input<string>('');
  phaseIndex = input<number>(0);
  totalPhases = input<number>(3);

  // Meta & slow inputs
  searchResultCount = input<number>(0);
  citationCount = input<number>(0);
  showSlowWarning = input<boolean>(false);

  // Computed
  protected readonly phaseSteps = computed(() =>
    Array.from({ length: this.totalPhases() }, (_, i) => i + 1)
  );

  protected readonly showMeta = computed(() => this.searchResultCount() > 0 || this.citationCount() > 0);

  protected readonly metaLabel = computed(() => {
    const results = this.searchResultCount();
    const citations = this.citationCount();
    if (citations > 0) return `${citations} sources cited`;
    if (results > 0) return `${results} sources found`;
    return '';
  });

  protected readonly phaseLabel = computed(() => {
    const labels: Record<string, string> = {
      searching: 'Searching sources...',
      analyzing: 'Analyzing documents...',
      synthesizing: 'Synthesizing response...',
      idle: 'Preparing...',
    };
    return labels[this.phase()] || 'Researching...';
  });

  // Elapsed timer
  protected readonly elapsedLabel = signal('');

  // Inject DestroyRef for cleanup
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    const start = Date.now();
    const id = setInterval(() => {
      const sec = Math.floor((Date.now() - start) / 1000);
      if (sec >= 3) {
        this.elapsedLabel.set(`${sec}s`);
      }
    }, 1000);

    // DestroyRef automatically cleans up when component is destroyed
    this.destroyRef.onDestroy(() => clearInterval(id));
  }
}
```
