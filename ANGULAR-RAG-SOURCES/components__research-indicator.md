# research-indicator

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__research-indicator` |
| **Files** | 1 |
| **Total size** | 6,648 bytes |
| **Generated** | 2026-02-26 11:02 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/research-indicator/research-indicator.ts` (6,648 bytes, Source)

---

## `app/components/research-indicator/research-indicator.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-26 |
| **Size** | 6,648 bytes |
| **Exports** | `ResearchIndicatorComponent`, `EvidenceSource` |

```typescript
import {
  Component,
  ChangeDetectionStrategy,
  input,
  computed,
  inject,
} from '@angular/core';
import { StreamService } from '../../services/stream.service';

/**
 * Evidence source item — mirrors the StreamEvent sources shape.
 */
export interface EvidenceSource {
  title: string;
  docket?: string;
  snippet?: string;
}

/**
 * ResearchIndicatorComponent (REC-03)
 *
 * Shows the live research phase (Researching → Synthesizing) and the
 * list of sources found by the Paralegal, before the Partner finalizes
 * the response. Displayed inside the chat message thread as an
 * intermediate state while the backend streams ADK events.
 *
 * Angular MCP compliance:
 * - ChangeDetectionStrategy.OnPush
 * - input() signals — NOT @Input() decorators
 * - computed() for all derived state — no effect()
 * - Native control flow @if / @for — NOT *ngIf / *ngFor
 * - role="status" + aria-live="polite" for WCAG AA screen reader support
 * - No ngClass, ngStyle, @HostBinding, @HostListener
 * - Inline styles in component styles[] block
 */
@Component({
  selector: 'app-research-indicator',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (isVisible()) {
      <div
        class="research-indicator"
        role="status"
        aria-live="polite"
        [attr.aria-label]="ariaLabel()"
      >
        <div class="research-phase">
          <span class="phase-icon" aria-hidden="true">{{ phaseIcon() }}</span>
          <span class="phase-label">{{ phaseLabel() }}</span>
          @if (isStreaming()) {
            <span class="typing-dots" aria-hidden="true">
              <span></span><span></span><span></span>
            </span>
          }
        </div>

        @if (sources().length > 0) {
          <div class="evidence-sources" aria-label="Retrieved sources">
            <p class="sources-label">
              Found {{ sources().length }} source{{ sources().length === 1 ? '' : 's' }}:
            </p>
            <ul class="source-list">
              @for (source of sources(); track source.title) {
                <li class="source-item">
                  <span class="source-title">{{ source.title }}</span>
                  @if (source.docket) {
                    <span class="source-docket">{{ source.docket }}</span>
                  }
                </li>
              }
            </ul>
          </div>
        }
      </div>
    }
  `,
  styles: [`
    .research-indicator {
      padding: 12px 16px;
      border-left: 3px solid var(--color-accent, #4f46e5);
      background: var(--color-surface-muted, rgba(79, 70, 229, 0.05));
      border-radius: 0 8px 8px 0;
      margin-bottom: 8px;
      animation: fadeIn 0.3s ease;
    }

    .research-phase {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.875rem;
      color: var(--color-text-muted, #6b7280);
    }

    .phase-icon {
      font-size: 1rem;
      line-height: 1;
    }

    .phase-label {
      font-weight: 500;
    }

    .evidence-sources {
      margin-top: 10px;
    }

    .sources-label {
      font-size: 0.8rem;
      color: var(--color-text-muted, #9ca3af);
      margin: 0 0 6px;
    }

    .source-list {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .source-item {
      font-size: 0.8rem;
      padding: 3px 0;
      color: var(--color-text-secondary, #6b7280);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .source-title {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .source-docket {
      font-family: monospace;
      font-size: 0.75rem;
      opacity: 0.7;
      white-space: nowrap;
      flex-shrink: 0;
    }

    /* Animated typing dots — three dots pulse sequentially */
    .typing-dots {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      margin-left: 2px;
    }

    .typing-dots span {
      display: inline-block;
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: currentColor;
      animation: dot-pulse 1.2s infinite;
    }

    .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
    .typing-dots span:nth-child(3) { animation-delay: 0.4s; }

    @keyframes dot-pulse {
      0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
      40% { opacity: 1; transform: scale(1); }
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `],
})
export class ResearchIndicatorComponent {
  /** Item 3: injected to read activeSearchQuery and researchMessage signals */
  protected readonly stream = inject(StreamService);

  /** Current streaming phase from StreamService */
  readonly phase = input<'idle' | 'researching' | 'synthesizing' | 'done' | 'error'>('idle');
  /** Evidence sources from the Paralegal (emitted on evidence_found event) */
  readonly sources = input<EvidenceSource[]>([]);

  /** Show only during active research/synthesis phases */
  readonly isVisible = computed(() => {
    const p = this.phase();
    return p === 'researching' || p === 'synthesizing';
  });

  /** Show the typing dots during active streaming */
  readonly isStreaming = computed(() => this.isVisible());

  /** Icon for the current phase */
  readonly phaseIcon = computed(() => ({
    researching: '🔍',
    synthesizing: '⚖️',
  }[this.phase() as 'researching' | 'synthesizing'] ?? ''));

  /** Human-readable label for the current phase.
   * Item 3: during 'researching' phase, if StreamService has an active query,
   * show "Searching: \"<query>\"" instead of the generic label.
   */
  readonly phaseLabel = computed(() => {
    const p = this.phase();
    if (p === 'researching') {
      // Use the live researchMessage from StreamService (includes the query text)
      const msg = this.stream.researchMessage();
      return msg || 'Researching sources...';
    }
    return ({
      synthesizing: 'Drafting advisory from evidence...',
    }[p as 'synthesizing'] ?? '');
  });

  /** ARIA label that dynamically describes current research progress */
  readonly ariaLabel = computed(() => {
    const phase = this.phaseLabel();
    const count = this.sources().length;
    if (count > 0 && this.phase() === 'synthesizing') {
      return `${phase} ${count} source${count === 1 ? '' : 's'} found.`;
    }
    return phase;
  });
}
```
