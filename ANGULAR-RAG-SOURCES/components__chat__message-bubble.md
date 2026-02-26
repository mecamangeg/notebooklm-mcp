# message-bubble

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__chat__message-bubble` |
| **Files** | 1 |
| **Total size** | 9,429 bytes |
| **Generated** | 2026-02-26 11:08 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/chat/message-bubble/message-bubble.ts` (9,429 bytes, Source)

---

## `app/components/chat/message-bubble/message-bubble.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 9,429 bytes |
| **Exports** | `MessageBubbleComponent` |

```typescript
import { Component, input, signal, computed, output, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Message } from '../../../models/types';
import { ParsedContentComponent } from '../parsed-content/parsed-content';
import { PipelineDebugPanelComponent } from '../pipeline-debug-panel/pipeline-debug-panel';
import { GroundingBadgeComponent } from '../grounding-badge/grounding-badge';

@Component({
  selector: 'app-message-bubble',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ParsedContentComponent, PipelineDebugPanelComponent, GroundingBadgeComponent],
  template: `
    <article 
      class="message-bubble" 
      [class.message-user]="isUser()" 
      [class.message-assistant]="!isUser()"
      [class.streaming-cursor]="isStreaming()"
      [attr.aria-label]="isUser() ? 'Your message' : 'ALT AI response'"
      [attr.aria-busy]="isStreaming() ? 'true' : null"
    >
      <div class="message-avatar" aria-hidden="true">
        <span class="material-symbols-outlined">
          {{ isUser() ? 'person' : 'cognition' }}
        </span>
      </div>

      <div class="message-content-wrapper">
        <div class="message-header">
          <span class="message-author" aria-hidden="true">{{ isUser() ? 'You' : 'ALT AI' }}</span>
          <time class="message-time" [attr.datetime]="message().timestamp.toISOString()">
            {{ message().timestamp | date:'shortTime' }}
          </time>
        </div>

        <div class="message-content">
          <app-parsed-content 
            [content]="message().content" 
            [citations]="message().citations || []"
          ></app-parsed-content>

          <!-- Copy button -->
          <button
            class="message-copy-btn"
            type="button"
            [class.copied]="copied()"
            (click)="handleCopy()"
            [attr.aria-label]="copied() ? 'Message copied' : 'Copy message'"
          >
            <span class="material-symbols-outlined" aria-hidden="true">
              {{ copied() ? 'check' : 'content_copy' }}
            </span>
          </button>
        </div>

        @if (!isUser() && message().citations?.length) {
          <!-- Grounding badge (Layer 2): appears ~500ms after stream ends
               Falls back to static trail while waiting for audit to resolve -->
          @if (message().audit) {
            <app-grounding-badge [audit]="message().audit" [citations]="message().citations || []" />
          } @else {
            <div class="research-trail">
               <span class="material-symbols-outlined" aria-hidden="true">search_check</span>
               <span>Grounded in {{ message().citations?.length }} sources</span>
            </div>
          }
        }

        @if (!isUser() && message().debugData) {
          <app-pipeline-debug-panel [debugData]="message().debugData"></app-pipeline-debug-panel>
        }

        @if (!isUser() && message().relatedQuestions?.length) {
          <section class="related-questions" aria-label="Related questions">
            <span class="related-label" aria-hidden="true">
              <span class="material-symbols-outlined">lightbulb</span>
              Related questions
            </span>
            <div class="related-chips" role="list">
              @for (q of message().relatedQuestions!; track q) {
                <div role="listitem">
                  <button class="related-chip" type="button"
                          (click)="onSuggestionClick.emit(q)"
                          [attr.aria-label]="'Ask: ' + q">
                    <span class="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
                    {{ q }}
                  </button>
                </div>
              }
            </div>
          </section>
        }
      </div>
    </article>
  `,
  styles: [`
    .message-bubble {
      display: flex;
      gap: 16px;
      padding: 16px;
      margin-bottom: 8px;
      transition: background 0.2s ease;
      position: relative;
      border-radius: 12px;

      &:hover {
        background: var(--bg-surface-hover);
        .message-copy-btn { opacity: 1; }
      }

      &.message-user {
        .message-avatar { background: var(--bg-surface-active); color: var(--text-primary); }
        .message-author { color: var(--text-primary); }
      }

      &.message-assistant {
        background: var(--bg-surface);
        border: 1px solid var(--border-color-subtle);
        .message-avatar { background: var(--accent-gradient); color: white; }
        .message-author {
          background: var(--accent-gradient);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          font-weight: 600;
        }
      }
    }

    .message-avatar {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      span { font-size: 18px; }
    }

    .message-content-wrapper {
      flex: 1;
      min-width: 0;
    }

    .message-header {
      display: flex;
      align-items: baseline;
      gap: 8px;
      margin-bottom: 6px;
    }

    .message-author {
      font-size: 14px;
      font-weight: 500;
    }

    .message-time {
      font-size: 11px;
      color: var(--text-muted);
    }

    .message-content {
      position: relative;
      line-height: 1.6;
      color: var(--text-secondary);
      font-size: 15px;
    }

    .message-copy-btn {
      position: absolute;
      top: -24px;
      right: 0;
      opacity: 0;
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      width: 28px;
      height: 28px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        background: var(--bg-surface-hover);
        color: var(--text-primary);
      }

      &.copied {
        color: var(--success);
        opacity: 1;
      }

      span { font-size: 16px; }
    }

    .research-trail {
      margin-top: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: var(--accent-primary);
      background: rgba(79, 70, 229, 0.05);
      padding: 4px 10px;
      border-radius: 20px;
      width: fit-content;
      
      span.material-symbols-outlined { font-size: 14px; }
    }

    .related-questions {
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid var(--border-color-subtle);
    }

    .related-label {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;

      .material-symbols-outlined {
        font-size: 14px;
        color: #f59e0b;
      }
    }

    .related-chips {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .related-chip {
      display: flex;
      align-items: center;
      gap: 8px;
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      padding: 8px 12px;
      border-radius: var(--radius-md, 8px);
      color: var(--text-secondary);
      font-size: 13px;
      text-align: left;
      cursor: pointer;
      transition: all 0.2s ease;
      animation: chipFadeIn 0.3s ease both;

      .material-symbols-outlined {
        font-size: 14px;
        color: var(--accent-primary);
        flex-shrink: 0;
      }

      &:hover {
        background: var(--bg-surface-hover);
        border-color: var(--accent-primary);
        transform: translateX(4px);
        color: var(--text-primary);
      }

      &:nth-child(1) { animation-delay: 0.1s; }
      &:nth-child(2) { animation-delay: 0.2s; }
      &:nth-child(3) { animation-delay: 0.3s; }
    }

    @keyframes chipFadeIn {
      from {
        opacity: 0;
        transform: translateY(6px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .streaming-cursor .message-content::after {
      content: '▊';
      animation: cursorBlink 0.8s step-end infinite;
      color: var(--accent-primary);
      margin-left: 2px;
      font-size: 0.9em;
    }

    @keyframes cursorBlink {
      50% { opacity: 0; }
    }
  `]
})
export class MessageBubbleComponent {
  readonly message = input.required<Message>();
  readonly isStreaming = input<boolean>(false);

  protected readonly isUser = computed(() => this.message().role === 'user');
  protected readonly copied = signal(false);
  readonly onSuggestionClick = output<string>();

  async handleCopy() {
    if (typeof navigator === 'undefined' || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(this.message().content);
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    } catch (err: unknown) {
      console.error('Copy failed', err);
    }
  }
}
```
