# template.service

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `services__template.service` |
| **Files** | 1 |
| **Total size** | 5,566 bytes |
| **Generated** | 2026-02-26 11:02 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/services/template.service.ts` (5,566 bytes, Service)

---

## `app/services/template.service.ts`

| Field | Value |
|-------|-------|
| **Role** | Service |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-23 |
| **Size** | 5,566 bytes |
| **Exports** | `TemplateService`, `TemplateOption`, `formatModelName`, `TEMPLATE_COLORS`, `TEMPLATE_ICONS` |

```typescript
import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** Template option shown in the UI */
export interface TemplateOption {
    id: string;
    label: string;
    icon: string;
    description: string;
    estimatedCost: string;
    estimatedLatency: string;
    recommended: boolean;
    partner: { model: string; displayModel?: string };
    paralegal: { model: string; displayModel?: string };
    quickSynthesis: { model: string; displayModel?: string };
}

/** Color class per template */
export const TEMPLATE_COLORS: Record<string, string> = {
    development: 'dev',
    tuned: 'tuned',
    economy: 'eco',
    balanced: 'bal',
    performance: 'perf',
};

/** Material icon per template (mapped from lucide names) */
export const TEMPLATE_ICONS: Record<string, string> = {
    Code: 'code',
    Coins: 'toll',
    Scale: 'balance',
    Rocket: 'rocket_launch',
    Dna: 'genetics',
};

/** Show displayModel when available, otherwise clean up gemini- prefix */
export function formatModelName(role: { model: string; displayModel?: string }): string {
    if (role.displayModel) return role.displayModel;
    return role.model.replace('gemini-', '').replace('-preview', '');
}

const DEFAULT_TEMPLATES: TemplateOption[] = [
    {
        id: 'development', label: 'Development', icon: 'Code',
        description: 'Cheapest all-Flash-Lite stack for testing & iteration',
        estimatedCost: '~$0.001/query', estimatedLatency: '~15-25s', recommended: false,
        partner: { model: 'gemini-2.5-flash-lite' },
        paralegal: { model: 'gemini-2.5-flash-lite' },
        quickSynthesis: { model: 'gemini-2.5-flash-lite' },
    },
    {
        id: 'tuned', label: 'Tuned', icon: 'Dna',
        description: 'Development + SFT-tuned Partner (robsky-partner-v1)',
        estimatedCost: '~$0.001/query', estimatedLatency: '~15-25s', recommended: false,
        partner: { model: 'robsky-partner-v1', displayModel: 'robsky-partner-v1' },
        paralegal: { model: 'gemini-2.5-flash-lite' },
        quickSynthesis: { model: 'gemini-2.5-flash-lite' },
    },
    {
        id: 'economy', label: 'Economy', icon: 'Coins',
        description: 'All-Flash stack for high-volume production',
        estimatedCost: '~$0.008/query', estimatedLatency: '~25-40s', recommended: false,
        partner: { model: 'gemini-2.5-flash' },
        paralegal: { model: 'gemini-2.5-flash' },
        quickSynthesis: { model: 'gemini-2.5-flash' },
    },
    {
        id: 'balanced', label: 'Balanced', icon: 'Scale',
        description: 'Best quality-to-cost ratio for production',
        estimatedCost: '~$0.018/query', estimatedLatency: '~35-70s', recommended: true,
        partner: { model: 'gemini-3-flash' },
        paralegal: { model: 'gemini-2.5-flash' },
        quickSynthesis: { model: 'gemini-2.5-flash' },
    },
    {
        id: 'performance', label: 'Performance', icon: 'Rocket',
        description: 'Maximum quality with Gemini 3 Pro + Flash',
        estimatedCost: '~$0.068/query', estimatedLatency: '~80-150s', recommended: false,
        partner: { model: 'gemini-3-pro' },
        paralegal: { model: 'gemini-3-flash' },
        quickSynthesis: { model: 'gemini-3-flash' },
    },
];

/** API response shapes (backend only) */
interface TemplateListResponse {
    current?: string;
    templates?: TemplateOption[];
}
interface TemplateSwitchResponse {
    warning?: boolean;
}

@Injectable({ providedIn: 'root' })
export class TemplateService {
    readonly templates = signal<TemplateOption[]>(DEFAULT_TEMPLATES);
    readonly currentId = signal<string>('tuned');
    readonly isLoading = signal(false);
    readonly justSwitched = signal(false);
    readonly warningMsg = signal<string | null>(null);

    private readonly http = inject(HttpClient);

    readonly current = computed(() =>
        this.templates().find(t => t.id === this.currentId())
    );

    constructor() {
        this.fetchTemplates();
    }

    private async fetchTemplates() {
        try {
            const data = await firstValueFrom(
                this.http.get<TemplateListResponse>('/api/settings/pipeline-template')
            );
            if (data.current) this.currentId.set(data.current);
            if (data.templates) this.templates.set(data.templates);
        } catch {
            // Silent fail — DEFAULT_TEMPLATES already loaded
        }
    }

    async switchTemplate(templateId: string) {
        if (templateId === this.currentId() || this.isLoading()) return;

        this.isLoading.set(true);
        this.warningMsg.set(null);

        try {
            const data = await firstValueFrom(
                this.http.post<TemplateSwitchResponse>(
                    '/api/settings/pipeline-template',
                    { template: templateId }
                )
            );

            this.currentId.set(templateId);
            this.justSwitched.set(true);
            setTimeout(() => this.justSwitched.set(false), 2000);

            if (data.warning) {
                this.warningMsg.set('In-flight queries will finish with the previous template.');
                setTimeout(() => this.warningMsg.set(null), 5000);
            }
        } catch {
            /* silent fail */
        } finally {
            this.isLoading.set(false);
        }
    }
}
```
