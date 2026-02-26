# chat-area

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__chat__chat-area` |
| **Files** | 1 |
| **Total size** | 17,164 bytes |
| **Generated** | 2026-02-26 11:07 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/chat/chat-area/chat-area.ts` (17,164 bytes, Source)

---

## `app/components/chat/chat-area/chat-area.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 17,164 bytes |
| **Exports** | `ChatAreaComponent` |

```typescript
import { Component, effect, inject, signal, computed, ElementRef, viewChild, ChangeDetectionStrategy } from '@angular/core';

import { ChatService } from '../../../services/chat.service';
import { AuthService } from '../../../services/auth.service';
import { MessageBubbleComponent } from '../message-bubble/message-bubble';
import { ThinkingIndicatorComponent } from '../thinking-indicator/thinking-indicator';

@Component({
  selector: 'app-chat-area',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    MessageBubbleComponent,
    ThinkingIndicatorComponent,
  ],
  host: { style: 'display: flex; flex-direction: column; height: 100%;' },
  template: `
    <div class="chat-container">
      <!-- Messages List -->
      <div class="messages-container" #scrollViewport
           role="log"
           aria-live="polite"
           aria-relevant="additions"
           aria-label="Chat messages">
        @if (chatService.messages().length === 0) {
          <div class="empty-chat">
            <div class="welcome-card">
              <div class="icon-wrapper">
                <span class="material-symbols-outlined large-icon" aria-hidden="true">cognition</span>
              </div>
              <h2>Welcome to ALT AI</h2>
              <p>Ask about accounting, legal, or tax matters. Every response includes verifiable sources.</p>

              <button class="drop-hint" type="button" aria-label="Browse files to upload">
                <strong>Tip:</strong> Drag and drop PDFs or images to chat about your documents.
                <span class="click-hint">Click here to browse files</span>
              </button>
              
              <div class="suggestion-chips">
                @for (hint of suggestionHints; track hint) {
                  <button class="hint-btn" type="button" (click)="setInputValue(hint)" [attr.aria-label]="'Suggestion: ' + hint">
                    {{ hint }}
                  </button>
                }
              </div>
            </div>
          </div>
        } @else {
          <div class="messages-list">
             @for (msg of chatService.messages(); track msg.id) {
               <app-message-bubble 
                 [message]="msg"
                 [isStreaming]="msg.isStreaming || false"
                 (onSuggestionClick)="handleRelatedQuestion($event)"
               ></app-message-bubble>
             }
             
             @if (showThinkingIndicator()) {
               <app-thinking-indicator
                 [phase]="chatService.streamingPhase().type"
                 [label]="chatService.streamingPhase().label"
                 [phaseIndex]="chatService.streamingPhase().phaseIndex"
                 [totalPhases]="chatService.streamingPhase().totalPhases"
                 [searchResultCount]="chatService.streamMeta()?.searchResultCount || 0"
                 [citationCount]="chatService.streamMeta()?.citationCount || 0"
                 [showSlowWarning]="chatService.isSlowResponse()"
               ></app-thinking-indicator>
             }

             <!-- Grounding hint: shown when RED gate refusal is the last response  -->
             <!-- MCP: role="status" (not "alert") — non-urgent, informational only -->
             @if (chatService.lastMessageIsGroundingRefusal()) {
               <div class="grounding-hint"
                    role="status"
                    aria-live="polite"
                    aria-atomic="true">
                 <span class="material-symbols-outlined"
                       [attr.aria-hidden]="'true'">tips_and_updates</span>
                 <span>Try rephrasing with more specific terms, a G.R. number, or a statute name.</span>
               </div>
             }
          </div>
        }
        <div #anchor></div>
      </div>

      <!-- Input Fixed at Bottom -->
      <div class="input-area" role="form" aria-label="Send a message">

        <!-- Retry banner: shown when the last SSE request failed (angular.dev/ai pattern) -->
        <!-- MCP: role="alert" + aria-live="assertive" for WCAG AA urgent announcements   -->
        @if (chatService.retryQuery()) {
          <div class="retry-banner"
               role="alert"
               aria-live="assertive"
               aria-atomic="true">
             <span class="material-symbols-outlined retry-icon"
                   aria-hidden="true">warning</span>
            <p class="retry-msg" id="retry-msg">{{ chatService.aiErrorMessage() }}</p>
            <div class="retry-actions">
              <button
                type="button"
                class="retry-btn"
                [attr.aria-describedby]="'retry-msg'"
                [disabled]="chatService.isProcessing()"
                (click)="retryMessage()"
              >
                Retry
              </button>
              <button
                type="button"
                class="dismiss-btn"
                [attr.aria-label]="'Dismiss retry notification'"
                (click)="chatService.clearRetry()"
              >
                Dismiss
              </button>
            </div>
          </div>
        }

        <div class="input-container">
          <div class="input-wrapper" [class.focused]="isInputFocused()">
            <textarea
              [value]="inputValue()"
              (input)="onInput($event)"
              (keydown.enter)="handleEnter($event)"
              (focus)="isInputFocused.set(true)"
              (blur)="isInputFocused.set(false)"
              placeholder="Ask about accounting, legal, or tax..."
              aria-label="Chat message input"
              rows="1"
              #inputBox
              data-gramm="false"
              data-gramm_editor="false"
              data-enable-grammarly="false"
              spellcheck="false"
            ></textarea>
            
            <button 
              class="send-btn"
              type="button"
              [disabled]="!inputValue().trim() || chatService.isProcessing()"
              (click)="sendMessage()"
              aria-label="Send message"
            >
              <span class="material-symbols-outlined" aria-hidden="true">send</span>
            </button>
          </div>
          <div class="footer-msg">
            ALT AI may produce inaccurate information. Always verify with original sources.
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .chat-container {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: var(--bg-chat);
    }

    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: 24px 0;
      scrollbar-width: thin;
      scrollbar-color: var(--border-color-strong) transparent;
    }

    .messages-list {
      max-width: 900px;
      margin: 0 auto;
      width: 100%;
      padding: 0 20px;
    }

    .empty-chat {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }

    .welcome-card {
      text-align: center;
      max-width: 520px;
      padding: 32px;
      background: var(--bg-surface);
      border: 1px solid var(--border-color-subtle);
      border-radius: 20px;
      box-shadow: var(--shadow-lg);

      .icon-wrapper {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 72px;
        height: 72px;
        border-radius: 50%;
        background: linear-gradient(135deg, rgba(108, 99, 255, 0.12), rgba(139, 92, 246, 0.12));
        border: 1px solid rgba(108, 99, 255, 0.15);
        margin-bottom: 20px;
      }

      .large-icon {
        font-size: 40px;
        background: var(--accent-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }

      h2 {
        font-family: 'Outfit', sans-serif;
        font-size: 1.625rem;
        margin-bottom: 10px;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.5px;
      }

      p {
        color: var(--text-tertiary);
        font-size: 0.875rem;
        margin-bottom: 24px;
        line-height: 1.6;
        max-width: 380px;
        margin-inline: auto;
      }
    }

    .drop-hint {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 14px 20px;
      margin-bottom: 20px;
      border-radius: var(--radius-lg);
      border: 1px dashed rgba(16, 185, 129, 0.35);
      background: rgba(16, 185, 129, 0.05);
      color: var(--text-secondary);
      font-size: 0.8125rem;
      cursor: pointer;
      transition: all 0.2s ease;

      strong {
        color: var(--success);
      }

      .click-hint {
        font-size: 0.75rem;
        color: var(--success);
        opacity: 0.8;
      }

      &:hover {
        background: rgba(16, 185, 129, 0.09);
        border-color: rgba(16, 185, 129, 0.55);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.08);
      }
    }

    .suggestion-chips {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .hint-btn {
      width: 100%;
      background: var(--bg-surface-hover);
      border: 1px solid var(--border-color);
      border-left: 3px solid rgba(108, 99, 255, 0.3);
      padding: 12px 16px;
      border-radius: var(--radius-lg);
      color: var(--text-secondary);
      font-size: 0.8125rem;
      text-align: left;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        background: color-mix(in srgb, var(--accent-primary) 6%, var(--bg-surface-hover));
        border-color: rgba(108, 99, 255, 0.4);
        border-left-color: var(--accent-primary);
        color: var(--text-primary);
        transform: translateX(2px);
        box-shadow: var(--shadow-sm);
      }
    }

    .input-area {
      padding: var(--spacing-md) var(--spacing-lg);
      padding-top: var(--spacing-sm);
      background: transparent;
    }

    .input-container {
      max-width: 800px;
      margin: 0 auto;
    }

    .input-wrapper {
      display: flex;
      align-items: flex-end;
      gap: var(--spacing-sm);
      
      &.focused textarea {
        border-color: var(--accent-primary);
      }
    }

    textarea {
      flex: 1;
      padding: var(--spacing-sm) var(--spacing-md);
      background: var(--bg-input);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      font-size: 0.9375rem;
      line-height: 1.5;
      color: var(--text-primary);
      resize: none;
      min-height: 44px;
      max-height: 200px;
      font-family: inherit;
      transition: border-color var(--transition-fast);
      outline: none;
      
      &::placeholder { color: var(--text-muted); }
    }

    .send-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 44px;
      height: 44px;
      background: var(--accent-primary);
      color: white;
      border: none;
      border-radius: var(--radius-lg);
      cursor: pointer;
      transition: all var(--transition-fast);
      flex-shrink: 0;
      
      &:disabled {
        background: var(--border-color-strong);
        cursor: not-allowed;
      }
      
      &:not(:disabled):hover {
        background: var(--accent-primary-hover);
        transform: translateY(-1px);
      }
      
      span { font-size: 18px; }
    }

    .footer-msg {
      text-align: center;
      font-size: 0.6875rem;
      color: var(--text-muted);
      margin-top: var(--spacing-sm);
    }

    /* ── Retry banner (angular.dev/ai graceful degradation) ── */
    .retry-banner {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      margin-bottom: 8px;
      /* Fallback for browsers without color-mix() (Firefox <113, Safari <16.2) */
      background: rgba(245, 158, 11, 0.10);
      background: color-mix(in srgb, #f59e0b 10%, transparent);
      border: 1px solid rgba(245, 158, 11, 0.30);
      border: 1px solid color-mix(in srgb, #f59e0b 30%, transparent);
      border-radius: var(--radius-lg);
      font-size: 0.8125rem;
      max-width: 800px;
      margin-inline: auto;
      width: 100%;
    }

    .retry-icon {
      font-size: 18px;
      color: #f59e0b;
      flex-shrink: 0;
    }

    .retry-msg {
      flex: 1;
      margin: 0;
      color: var(--text-secondary);
      line-height: 1.4;
    }

    .retry-actions {
      display: flex;
      gap: 6px;
      flex-shrink: 0;
    }

    .retry-btn {
      padding: 5px 12px;
      border-radius: var(--radius-md, 6px);
      background: var(--accent-primary);
      color: white;
      font-size: 0.8125rem;
      font-weight: 500;
      border: none;
      cursor: pointer;
      transition: opacity 0.15s ease;
      /* MCP: visible focus ring mandatory for keyboard users (WCAG AA) */
      &:focus-visible {
        outline: 2px solid var(--accent-primary);
        outline-offset: 2px;
      }
      &:disabled {
        opacity: 0.45;
        cursor: not-allowed;
      }
      &:not(:disabled):hover {
        opacity: 0.85;
      }
    }

    .dismiss-btn {
      padding: 5px 10px;
      border-radius: var(--radius-md, 6px);
      background: transparent;
      border: 1px solid var(--border-color);
      color: var(--text-secondary);
      font-size: 0.8125rem;
      cursor: pointer;
      transition: border-color 0.15s ease;
      &:focus-visible {
        outline: 2px solid var(--border-color-strong);
        outline-offset: 2px;
      }
      &:hover {
        border-color: var(--border-color-strong);
      }
    }

    /* ── Grounding refusal hint ── */
    .grounding-hint {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      margin: 6px 0 12px;
      /* Fallback before color-mix() */
      background: rgba(99, 102, 241, 0.06);
      background: color-mix(in srgb, var(--accent-primary) 6%, transparent);
      border: 1px solid rgba(99, 102, 241, 0.18);
      border: 1px solid color-mix(in srgb, var(--accent-primary) 18%, transparent);
      border-radius: var(--radius-lg);
      font-size: 0.8125rem;
      color: var(--text-secondary);

      .material-symbols-outlined {
        font-size: 16px;
        color: var(--accent-primary);
        flex-shrink: 0;
      }
    }
  `]
})
export class ChatAreaComponent {
  readonly chatService = inject(ChatService);
  readonly authService = inject(AuthService);

  protected readonly inputValue = signal('');
  protected readonly isInputFocused = signal(false);

  private readonly anchor = viewChild<ElementRef>('anchor');

  protected readonly suggestionHints = [
    'What are the grounds for illegal dismissal?',
    'Explain revenue recognition under PFRS 15',
    'What are the withholding tax requirements?'
  ];

  /**
   * Show the thinking indicator when processing but NOT actively streaming text.
   * Once deltas start arriving, the streaming cursor in the message bubble takes over.
   */
  protected readonly showThinkingIndicator = computed(
    () => this.chatService.isProcessing() && !this.chatService.isStreaming()
  );

  constructor() {
    // Auto-scroll when messages change: use the signal value explicitly (not just for tracking)
    effect(() => {
      const msgs = this.chatService.messages();
      if (msgs.length > 0) {
        setTimeout(() => {
          this.anchor()?.nativeElement.scrollIntoView({ behavior: 'smooth' });
        }, 0);
      }
    });
  }

  protected onInput(event: Event): void {
    this.inputValue.set((event.target as HTMLTextAreaElement).value);
  }

  setInputValue(val: string) {
    this.inputValue.set(val);
  }

  handleEnter(event: Event) {
    const keyboardEvent = event as KeyboardEvent;
    if (!keyboardEvent.shiftKey) {
      keyboardEvent.preventDefault();
      this.sendMessage();
    }
  }

  async sendMessage() {
    const val = this.inputValue().trim();
    if (!val || this.chatService.isProcessing()) return;

    this.inputValue.set('');
    await this.chatService.sendMessage(val);
  }

  /**
   * Handle click on a related question chip — auto-send it as a new message
   */
  async handleRelatedQuestion(question: string) {
    if (this.chatService.isProcessing()) return;
    await this.chatService.sendMessage(question);
  }

  /**
   * Template-facing wrapper for chatService.retryLastMessage().
   * Protected (MCP airules.md): template members must be `protected` — not used outside template.
   */
  protected async retryMessage(): Promise<void> {
    await this.chatService.retryLastMessage();
  }
}
```
