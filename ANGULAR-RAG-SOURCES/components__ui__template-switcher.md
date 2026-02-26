# template-switcher

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__ui__template-switcher` |
| **Files** | 1 |
| **Total size** | 13,162 bytes |
| **Generated** | 2026-02-26 11:02 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/ui/template-switcher/template-switcher.ts` (13,162 bytes, Source)

---

## `app/components/ui/template-switcher/template-switcher.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-24 |
| **Size** | 13,162 bytes |
| **Exports** | `TemplateSwitcherComponent` |

```typescript
import { Component, inject, signal, computed, ElementRef, viewChild, ChangeDetectionStrategy } from '@angular/core';
import {
  TemplateService,
  TEMPLATE_COLORS,
  TEMPLATE_ICONS,
  formatModelName,
  type TemplateOption
} from '../../../services/template.service';

@Component({
  selector: 'app-template-switcher',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="tpl-switcher-container" #menuRef>
      <button
        class="tpl-switcher-btn"
        [class.just-switched]="templateService.justSwitched()"
        (click)="isOpen.set(!isOpen())"
        aria-label="Switch pipeline template"
        [attr.aria-expanded]="isOpen()"
        [title]="currentTitle()"
      >
        <div class="tpl-switcher-icon"
             [class]="colorClass()">
          <span class="material-symbols-outlined" style="font-size:14px">
            {{ currentIcon() }}
          </span>
        </div>
        <span class="tpl-switcher-label">{{ templateService.current()?.label || 'Balanced' }}</span>
        <span class="material-symbols-outlined tpl-switcher-chevron"
              [class.open]="isOpen()"
              style="font-size:12px">expand_more</span>
      </button>

      @if (isOpen()) {
        <div class="tpl-switcher-dropdown">
          <div class="tpl-switcher-header">
            <span class="tpl-switcher-header-label">Pipeline Template</span>
            <span class="tpl-switcher-header-hint">All 3 roles configured atomically</span>
          </div>
          <div class="tpl-switcher-options">
            @for (tpl of enrichedTemplates(); track tpl.id) {
              <button
                [class]="'tpl-option' + (tpl.id === templateService.currentId() ? ' active' : '') + ' ' + tpl.colorClass"
                (click)="switchTo(tpl.id)"
                [disabled]="templateService.isLoading()"
                [attr.aria-label]="tpl.label + ': ' + tpl.description"
              >
                <div class="tpl-option-left">
                  <div [class]="'tpl-option-icon ' + tpl.colorClass">
                    @if (templateService.isLoading() && tpl.id !== templateService.currentId()) {
                      <span class="material-symbols-outlined spinning" style="font-size:16px">progress_activity</span>
                    } @else {
                      <span class="material-symbols-outlined" style="font-size:16px">{{ tpl.iconName }}</span>
                    }
                  </div>
                  <div class="tpl-option-info">
                    <div class="tpl-option-name">
                      {{ tpl.label }}
                      @if (tpl.recommended) {
                        <span class="tpl-recommended-badge">
                          <span class="material-symbols-outlined" style="font-size:10px">star</span>
                          Recommended
                        </span>
                      }
                      @if (tpl.id === templateService.currentId()) {
                        <span class="material-symbols-outlined tpl-option-check" style="font-size:14px">check</span>
                      }
                    </div>
                    <div class="tpl-option-desc">{{ tpl.description }}</div>
                    <div class="tpl-option-models">
                      <span title="Partner">P: {{ tpl.partnerLabel }}</span>
                      <span class="tpl-model-sep">·</span>
                      <span title="Paralegal">L: {{ tpl.paralegalLabel }}</span>
                      <span class="tpl-model-sep">·</span>
                      <span title="Quick Synthesis">Q: {{ tpl.quickSynthesisLabel }}</span>
                    </div>
                  </div>
                </div>
                <div class="tpl-option-meta">
                  <span class="tpl-option-cost">{{ tpl.estimatedCost }}</span>
                  <span class="tpl-option-latency">{{ tpl.estimatedLatency }}</span>
                </div>
              </button>
            }
          </div>
        </div>
      }

      @if (templateService.warningMsg()) {
        <div class="tpl-switcher-warning" role="alert">
          ⚠️ {{ templateService.warningMsg() }}
        </div>
      }
    </div>
  `,
  styles: [`
    /* Container */
    .tpl-switcher-container { position: relative; }

    /* Trigger button */
    .tpl-switcher-btn {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px 4px 6px;
      background: var(--bg-surface-hover);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      cursor: pointer;
      transition: all var(--transition-fast);
      font-family: inherit;
    }
    .tpl-switcher-btn:hover {
      background: var(--bg-surface-active);
      border-color: var(--border-color-strong);
    }
    .tpl-switcher-btn.just-switched {
      border-color: var(--success);
      box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.15);
    }

    /* Icon circle */
    .tpl-switcher-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      transition: all var(--transition-fast);
    }
    .tpl-switcher-icon.dev { background: linear-gradient(135deg, #66BB6A, #43A047); color: #fff; }
    .tpl-switcher-icon.eco { background: linear-gradient(135deg, #FFD54F, #FFA726); color: #5D4037; }
    .tpl-switcher-icon.bal { background: linear-gradient(135deg, #42A5F5, #1E88E5); color: #fff; }
    .tpl-switcher-icon.perf { background: linear-gradient(135deg, #AB47BC, #7B1FA2); color: #fff; }
    .tpl-switcher-icon.tuned { background: linear-gradient(135deg, #26A69A, #00897B); color: #fff; }

    .tpl-switcher-label {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-secondary);
      white-space: nowrap;
      letter-spacing: -0.01em;
    }

    .tpl-switcher-chevron {
      color: var(--text-muted);
      transition: transform var(--transition-fast);
    }
    .tpl-switcher-chevron.open { transform: rotate(180deg); }

    /* Dropdown */
    .tpl-switcher-dropdown {
      position: absolute;
      top: calc(100% + 8px);
      right: 0;
      width: 360px;
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-lg);
      z-index: 200;
      animation: slideIn 0.15s ease-out;
      overflow: hidden;
    }

    .tpl-switcher-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 14px;
      border-bottom: 1px solid var(--border-color-subtle);
    }
    .tpl-switcher-header-label {
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--text-primary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .tpl-switcher-header-hint {
      font-size: 0.6875rem;
      color: var(--text-muted);
    }

    .tpl-switcher-options { padding: 6px; }

    /* Warning toast */
    .tpl-switcher-warning {
      position: absolute;
      top: calc(100% + 6px);
      right: 0;
      padding: 8px 12px;
      background: rgba(255, 180, 50, 0.15);
      border: 1px solid rgba(255, 180, 50, 0.3);
      border-radius: 8px;
      color: #f5c842;
      font-size: 11px;
      line-height: 1.4;
      white-space: nowrap;
      backdrop-filter: blur(12px);
      animation: fadeInDown 0.3s ease;
      z-index: 1001;
    }

    /* Template option row */
    .tpl-option {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
      width: 100%;
      padding: 10px;
      background: transparent;
      border: 1px solid transparent;
      border-radius: var(--radius-md);
      cursor: pointer;
      transition: all var(--transition-fast);
      font-family: inherit;
      text-align: left;
    }
    .tpl-option:hover {
      background: var(--bg-surface-hover);
      border-color: var(--border-color);
    }
    .tpl-option.active {
      background: rgba(76, 175, 80, 0.06);
      border-color: rgba(76, 175, 80, 0.25);
    }

    .tpl-option-left {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      flex: 1;
      min-width: 0;
    }

    .tpl-option-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      border-radius: 8px;
      flex-shrink: 0;
      margin-top: 2px;
    }
    .tpl-option-icon.dev { background: linear-gradient(135deg, #66BB6A, #43A047); color: #fff; }
    .tpl-option-icon.eco { background: linear-gradient(135deg, #FFD54F, #FFA726); color: #5D4037; }
    .tpl-option-icon.bal { background: linear-gradient(135deg, #42A5F5, #1E88E5); color: #fff; }
    .tpl-option-icon.perf { background: linear-gradient(135deg, #AB47BC, #7B1FA2); color: #fff; }
    .tpl-option-icon.tuned { background: linear-gradient(135deg, #26A69A, #00897B); color: #fff; }

    .tpl-option-info { flex: 1; min-width: 0; }

    .tpl-option-name {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8125rem;
      font-weight: 600;
      color: var(--text-primary);
    }
    .tpl-option-check { color: var(--success); flex-shrink: 0; }

    .tpl-recommended-badge {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      font-size: 0.5625rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 1px 6px;
      border-radius: 10px;
      background: linear-gradient(135deg, rgba(255, 193, 7, 0.15), rgba(255, 152, 0, 0.15));
      color: #F57C00;
      border: 1px solid rgba(255, 152, 0, 0.25);
      white-space: nowrap;
    }

    .tpl-option-desc {
      font-size: 0.6875rem;
      color: var(--text-muted);
      margin-top: 1px;
    }

    .tpl-option-models {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-top: 4px;
      font-size: 0.5625rem;
      font-weight: 500;
      color: var(--text-tertiary);
      font-family: 'Cascadia Code', 'Fira Code', monospace;
      letter-spacing: -0.01em;
    }
    .tpl-model-sep { color: var(--text-muted); opacity: 0.5; }

    .tpl-option-meta {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 2px;
      flex-shrink: 0;
      margin-top: 2px;
    }
    .tpl-option-cost {
      font-size: 0.625rem;
      font-weight: 600;
      color: var(--text-tertiary);
      font-variant-numeric: tabular-nums;
    }
    .tpl-option-latency {
      font-size: 0.625rem;
      color: var(--text-muted);
      font-variant-numeric: tabular-nums;
    }

    .spinning { animation: spin 1s linear infinite; }

    @keyframes slideIn {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeInDown {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }

    @media (max-width: 640px) {
      .tpl-switcher-label { display: none; }
      .tpl-switcher-btn { padding: 4px 8px 4px 4px; }
      .tpl-switcher-dropdown { width: 300px; }
    }
  `],
  host: {
    '(document:mousedown)': 'onClickOutside($event)',
  },
})
export class TemplateSwitcherComponent {
  protected readonly templateService = inject(TemplateService);
  protected readonly isOpen = signal(false);

  private readonly menuRef = viewChild<ElementRef>('menuRef');

  protected readonly currentTitle = computed(() => {
    const c = this.templateService.current();
    return c ? `${c.label} — ${c.description}` : 'Pipeline Template';
  });

  protected readonly colorClass = computed(() =>
    TEMPLATE_COLORS[this.templateService.currentId()] || 'bal'
  );

  protected readonly currentIcon = computed(() => {
    const c = this.templateService.current();
    return TEMPLATE_ICONS[c?.icon || 'Scale'] || 'balance';
  });

  /** Pre-computed per-template display data for the dropdown list */
  protected readonly enrichedTemplates = computed(() =>
    this.templateService.templates().map(tpl => ({
      ...tpl,
      colorClass: TEMPLATE_COLORS[tpl.id] || 'bal',
      iconName: TEMPLATE_ICONS[tpl.icon] || 'balance',
      partnerLabel: formatModelName(tpl.partner),
      paralegalLabel: formatModelName(tpl.paralegal),
      quickSynthesisLabel: formatModelName(tpl.quickSynthesis),
    }))
  );

  switchTo(templateId: string) {
    this.templateService.switchTemplate(templateId);
    this.isOpen.set(false);
  }

  onClickOutside(event: MouseEvent) {
    const el = this.menuRef()?.nativeElement;
    if (el && !el.contains(event.target as Node)) {
      this.isOpen.set(false);
    }
  }
}
```
