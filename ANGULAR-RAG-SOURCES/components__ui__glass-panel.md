# glass-panel

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__ui__glass-panel` |
| **Files** | 1 |
| **Total size** | 1,416 bytes |
| **Generated** | 2026-02-26 11:04 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/ui/glass-panel/glass-panel.ts` (1,416 bytes, Source)

---

## `app/components/ui/glass-panel/glass-panel.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-24 |
| **Size** | 1,416 bytes |
| **Exports** | `GlassPanelComponent` |

```typescript
import { Component, input, ChangeDetectionStrategy } from '@angular/core';

@Component({
  selector: 'app-glass-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="glass-panel" [class.hover-effect]="hoverable()">
      <ng-content></ng-content>
    </div>
  `,
  styles: [`
    :host {
      display: block;
    }
    .glass-panel {
      background: var(--panel-bg);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--glass-border);
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
      padding: 1rem;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      overflow: hidden;
      position: relative;
      
      &.hover-effect:hover {
        border-color: rgba(255, 255, 255, 0.2);
        box-shadow: 0 12px 48px rgba(0, 0, 0, 0.5);
        transform: translateY(-2px);
      }

      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(
          135deg,
          rgba(255, 255, 255, 0.05) 0%,
          rgba(255, 255, 255, 0) 100%
        );
        pointer-events: none;
      }
    }
  `]
})
export class GlassPanelComponent {
  // Input signals (Angular 19+)
  readonly hoverable = input<boolean>(false);
}
```
