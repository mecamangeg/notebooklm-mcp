# nav-panel

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__nav-panel` |
| **Files** | 1 |
| **Total size** | 22,191 bytes |
| **Generated** | 2026-02-26 11:01 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/nav-panel/nav-panel.ts` (22,191 bytes, Source)

---

## `app/components/nav-panel/nav-panel.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-24 |
| **Size** | 22,191 bytes |
| **Exports** | `NavPanelComponent` |

```typescript
import {
  Component, inject, signal, output, ChangeDetectionStrategy,
  ElementRef, viewChild, effect
} from '@angular/core';

import { SessionService, ChatSession } from '../../services/session.service';
import { ChatService } from '../../services/chat.service';

@Component({
  selector: 'app-nav-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [],
  template: `
    <aside class="nav-panel" [attr.aria-label]="'Conversations sidebar'">
      <div class="nav-panel-header">
        <button class="new-chat-button" type="button" (click)="handleNewChat()">
          <span class="material-symbols-outlined" style="font-size:18px" [attr.aria-hidden]="'true'">add</span>
          <span>New Chat</span>
        </button>
      </div>

      <!-- Selection toolbar -->
      @if (selectionMode()) {
        <div class="selection-toolbar">
          <div class="selection-info">
            <span>{{ selectedIds().size }} selected</span>
          </div>
          <div class="selection-actions">
            <button class="selection-action-btn" type="button" (click)="selectAll()" [attr.aria-label]="'Select all conversations'">
              <span class="material-symbols-outlined" style="font-size:16px" [attr.aria-hidden]="'true'">check_box</span>
            </button>
            <button class="selection-action-btn" type="button" (click)="unselectAll()" [attr.aria-label]="'Deselect all conversations'">
              <span class="material-symbols-outlined" style="font-size:16px" [attr.aria-hidden]="'true'">indeterminate_check_box</span>
            </button>
            <button class="selection-action-btn delete" type="button" (click)="handleDeleteSelected()" [disabled]="selectedIds().size === 0" [attr.aria-label]="'Delete ' + selectedIds().size + ' selected conversations'">
              <span class="material-symbols-outlined" style="font-size:16px" [attr.aria-hidden]="'true'">delete</span>
            </button>
            <button class="selection-action-btn" type="button" (click)="exitSelectionMode()" [attr.aria-label]="'Exit selection mode'">
              <span class="material-symbols-outlined" style="font-size:16px" [attr.aria-hidden]="'true'">close</span>
            </button>
          </div>
        </div>
      }

      <!-- Enter selection mode -->
      @if (!selectionMode() && sessionService.sessions().length > 0) {
        <div class="selection-toggle">
          <button class="enter-selection-btn" type="button" (click)="selectionMode.set(true)" [attr.aria-label]="'Select conversations'">
            <span class="material-symbols-outlined" style="font-size:14px" [attr.aria-hidden]="'true'">check_box_outline_blank</span>
            <span>Select</span>
          </button>
        </div>
      }

      <nav class="nav-panel-content" [attr.aria-label]="'Conversation history'">
        @for (group of sessionService.groupedSessions(); track group.label) {
          <div class="session-group">
            <button class="session-group-header" type="button" (click)="toggleGroup(group.label)"
              [attr.aria-expanded]="expandedGroups()[group.label] ? 'true' : 'false'"
              [attr.aria-controls]="'group-' + group.label"
              [attr.aria-label]="group.label + ' conversations'"
            >
              <span class="material-symbols-outlined" style="font-size:14px" aria-hidden="true">
                {{ expandedGroups()[group.label] ? 'expand_more' : 'chevron_right' }}
              </span>
              <span>{{ group.label }}</span>
            </button>

            @if (expandedGroups()[group.label]) {
              <ul class="session-list" role="listbox" [attr.aria-label]="group.label + ' conversations'" [id]="'group-' + group.label">
                @for (session of group.sessions; track session.id) {
                  <li
                    class="session-item"
                    role="option"
                    tabindex="0"
                    [class.active]="session.id === sessionService.currentSessionId()"
                    [class.selected]="selectedIds().has(session.id)"
                    [attr.aria-selected]="selectionMode() ? selectedIds().has(session.id) : (session.id === sessionService.currentSessionId())"
                    [attr.aria-current]="!selectionMode() && session.id === sessionService.currentSessionId() ? 'location' : null"
                    [attr.aria-label]="session.title"
                    (click)="handleSessionClick(session)"
                    (contextmenu)="handleContextMenu($event, session)"
                    (keydown.enter)="handleSessionClick(session)"
                    (keydown.space)="handleSessionClick(session)"
                  >
                    @if (selectionMode()) {
                      <span class="session-checkbox" [attr.aria-hidden]="'true'">
                        <span class="material-symbols-outlined" style="font-size:16px">
                          {{ selectedIds().has(session.id) ? 'check_box' : 'check_box_outline_blank' }}
                        </span>
                      </span>
                    }

                    @if (!selectionMode()) {
                      <span class="material-symbols-outlined session-icon" [attr.aria-hidden]="'true'">chat_bubble_outline</span>
                    }

                    @if (renamingId() === session.id) {
                      <div class="rename-input-wrapper">
                        <input
                          class="rename-input"
                          [value]="renameValue()"
                          [attr.aria-label]="'Rename conversation: ' + renameValue()"
                          (input)="onRenameInput($event)"
                          (keydown.enter)="confirmRename()"
                          (keydown.escape)="cancelRename()"
                          (blur)="confirmRename()"
                          #renameInput
                        />
                        <button class="rename-action" type="button" [attr.aria-label]="'Save rename'" (click)="confirmRename()">
                          <span class="material-symbols-outlined" style="font-size:14px" [attr.aria-hidden]="'true'">check</span>
                        </button>
                        <button class="rename-action cancel" type="button" [attr.aria-label]="'Cancel rename'" (click)="cancelRename()">
                          <span class="material-symbols-outlined" style="font-size:14px" [attr.aria-hidden]="'true'">close</span>
                        </button>
                      </div>
                    } @else {
                      <span class="session-title">{{ session.title }}</span>

                      @if (!selectionMode()) {
                        <div class="session-actions">
                          <button class="session-action-btn" type="button"
                            [attr.aria-label]="'Rename: ' + session.title"
                            (click)="startRename($event, session)">
                            <span class="material-symbols-outlined" style="font-size:14px" [attr.aria-hidden]="'true'">edit</span>
                          </button>
                          <button class="session-action-btn delete" type="button"
                            [attr.aria-label]="'Delete: ' + session.title"
                            (click)="handleDeleteSingle($event, session.id)">
                            <span class="material-symbols-outlined" style="font-size:14px" [attr.aria-hidden]="'true'">delete</span>
                          </button>
                        </div>
                      }
                    }
                  </li>
                }
              </ul>
            }
          </div>
        }

        @if (sessionService.sessions().length === 0) {
          <div class="empty-sessions" aria-live="polite" aria-atomic="true">
            <p>No conversations yet</p>
            <p class="empty-hint">Start a new chat to begin</p>
          </div>
        }
      </nav>
    </aside>

    <!-- Inline confirmation dialog (replaces browser confirm()) -->
    @if (confirmState()) {
      <div class="confirm-overlay" (click)="confirmDialogCancel()" (keydown.escape)="confirmDialogCancel()">
        <div class="confirm-dialog"
          role="dialog"
          [attr.aria-modal]="'true'"
          [attr.aria-labelledby]="'confirm-dialog-title'"
          aria-describedby="confirm-dialog-desc"
          #confirmDialog
          (click)="$event.stopPropagation()">
          <h3 class="confirm-title" id="confirm-dialog-title">{{ confirmState()!.title }}</h3>
          <p class="confirm-message" id="confirm-dialog-desc">{{ confirmState()!.message }}</p>
          <div class="confirm-actions">
            <button class="confirm-btn-cancel" type="button" #confirmCancel (click)="confirmDialogCancel()">Cancel</button>
            <button class="confirm-btn-delete" type="button" (click)="confirmDialogConfirm()">Delete</button>
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    /* ── Panel shell ── */
    .nav-panel {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: var(--bg-surface);
      border-right: 1px solid var(--border-color-subtle);
      overflow: hidden;
      font-size: 13px;
    }

    /* ── Header ── */
    .nav-panel-header {
      padding: 12px 10px 8px;
      flex-shrink: 0;
    }

    .new-chat-button {
      display: flex;
      align-items: center;
      gap: 6px;
      width: 100%;
      padding: 8px 12px;
      background: var(--accent-primary);
      color: white;
      border: none;
      border-radius: var(--radius-md, 8px);
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: opacity 0.15s ease;
      &:hover { opacity: 0.88; }
      &:focus-visible { outline: 2px solid var(--accent-primary); outline-offset: 2px; }
    }

    /* ── Selection toggle ("Select" button row) ── */
    .selection-toggle {
      padding: 2px 10px 4px;
      flex-shrink: 0;
    }

    .enter-selection-btn {
      display: flex;
      align-items: center;
      gap: 4px;
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 11px;
      cursor: pointer;
      padding: 3px 4px;
      border-radius: 4px;
      transition: color 0.15s;
      &:hover { color: var(--text-secondary); }
    }

    /* ── Selection toolbar (shown when selectionMode = true) ── */
    .selection-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 6px 10px;
      background: var(--bg-surface-active);
      border-bottom: 1px solid var(--border-color-subtle);
      flex-shrink: 0;
    }

    .selection-info {
      font-size: 12px;
      color: var(--text-secondary);
      font-weight: 500;
    }

    .selection-actions {
      display: flex;
      gap: 2px;
    }

    .selection-action-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
      &:hover { background: var(--bg-surface-hover); color: var(--text-primary); }
      &.delete:hover { color: var(--error); }
      &:disabled { opacity: 0.35; cursor: not-allowed; }
    }

    /* ── Scrollable session list ── */
    .nav-panel-content {
      flex: 1;
      overflow-y: auto;
      padding: 4px 0 12px;
      /* Thin scrollbar */
      scrollbar-width: thin;
      scrollbar-color: var(--border-color) transparent;
    }

    /* ── Group headers ── */
    .session-group { margin-bottom: 4px; }

    .session-group-header {
      display: flex;
      align-items: center;
      gap: 4px;
      width: 100%;
      padding: 4px 10px;
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      cursor: pointer;
      transition: color 0.15s;
      &:hover { color: var(--text-secondary); }
    }

    /* ── Session list ── */
    .session-list {
      list-style: none;
      margin: 0;
      padding: 0;
    }

    /* ── Individual session item ── */
    .session-item {
      position: relative;
      display: flex;
      align-items: center;
      gap: 7px;
      padding: 7px 10px;
      cursor: pointer;
      border-radius: 6px;
      margin: 1px 6px;
      transition: background 0.15s;
      min-width: 0;

      /* Action buttons hidden by default — revealed on hover */
      .session-actions { display: none; }

      &:hover {
        background: var(--bg-surface-hover);
        .session-actions { display: flex; }
      }

      &.active {
        background: var(--bg-surface-active);
        border-left: 2px solid var(--accent-primary);
        padding-left: 8px;
        .session-title { color: var(--text-primary); font-weight: 500; }
        .session-actions { display: flex; } /* always show on active item */
      }

      &.selected {
        background: color-mix(in srgb, var(--accent-primary) 10%, transparent);
      }
    }

    /* Chat bubble icon beside session title */
    .session-icon {
      font-size: 15px;
      color: var(--text-muted);
      flex-shrink: 0;
    }

    /* Checkbox icon in selection mode */
    .session-checkbox {
      flex-shrink: 0;
      color: var(--accent-primary);
      display: flex;
      align-items: center;
    }

    /* Session title — truncated */
    .session-title {
      flex: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: 13px;
      color: var(--text-secondary);
      line-height: 1.4;
    }

    /* Hover-reveal action buttons (edit + delete) */
    .session-actions {
      flex-shrink: 0;
      gap: 2px;
      align-items: center;
    }

    .session-action-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      border-radius: 4px;
      cursor: pointer;
      padding: 0;
      transition: background 0.15s, color 0.15s;
      &:hover { background: var(--bg-surface-active); color: var(--text-primary); }
      &.delete:hover { color: var(--error); }
      &:focus-visible { outline: 2px solid var(--accent-primary); outline-offset: 1px; }
    }

    /* ── Inline rename input ── */
    .rename-input-wrapper {
      flex: 1;
      display: flex;
      align-items: center;
      gap: 4px;
      min-width: 0;
    }

    .rename-input {
      flex: 1;
      min-width: 0;
      background: var(--bg-surface-active);
      border: 1px solid var(--accent-primary);
      border-radius: 4px;
      color: var(--text-primary);
      font-size: 12px;
      padding: 3px 6px;
      outline: none;
      &:focus-visible {
        outline: 2px solid var(--accent-primary);
        outline-offset: 0;
      }
    }

    .rename-action {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      border-radius: 4px;
      cursor: pointer;
      padding: 0;
      &:hover { color: var(--text-primary); }
      &.cancel:hover { color: var(--error); }
    }

    /* ── Empty state ── */
    .empty-sessions {
      padding: 24px 16px;
      text-align: center;
      color: var(--text-muted);
      font-size: 13px;
    }

    .empty-hint {
      font-size: 11px;
      margin-top: 4px;
      opacity: 0.7;
    }

    /* ── Confirm dialog overlay ── */
    .confirm-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.45);
      z-index: 1000;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .confirm-dialog {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg, 12px);
      padding: 20px 24px;
      width: min(320px, 90vw);
      box-shadow: 0 8px 32px rgba(0,0,0,0.25);
    }

    .confirm-title {
      margin: 0 0 8px;
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .confirm-message {
      margin: 0 0 18px;
      font-size: 13px;
      color: var(--text-secondary);
      line-height: 1.5;
    }

    .confirm-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }

    .confirm-btn-cancel {
      padding: 7px 16px;
      border-radius: var(--radius-md, 8px);
      border: 1px solid var(--border-color);
      background: transparent;
      color: var(--text-secondary);
      font-size: 13px;
      cursor: pointer;
      &:hover { border-color: var(--border-color-strong); }
    }

    .confirm-btn-delete {
      padding: 7px 16px;
      border-radius: var(--radius-md, 8px);
      border: none;
      background: var(--error, #ef4444);
      color: white;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      &:hover { opacity: 0.88; }
    }
  `]
})
export class NavPanelComponent {
  protected readonly sessionService = inject(SessionService);
  private readonly chatService = inject(ChatService);

  // Outputs: parent App needs to know when session context changes
  readonly sessionSelected = output<void>();

  // Nav Panel state
  protected readonly selectionMode = signal(false);
  protected readonly selectedIds = signal<Set<string>>(new Set());
  protected readonly expandedGroups = signal<Record<string, boolean>>({
    'Today': true,
    'Yesterday': true,
    'Previous 7 Days': true,
    'Older': false
  });
  protected readonly renamingId = signal<string | null>(null);
  protected readonly renameValue = signal('');

  // Inline confirmation dialog state
  protected readonly confirmState = signal<{ title: string; message: string; onConfirm: () => void } | null>(null);

  /** Focus the cancel button when the dialog opens (WCAG 2.4.3 focus order) */
  private readonly confirmCancelRef = viewChild<ElementRef<HTMLButtonElement>>('confirmCancel');

  constructor() {
    // When confirmState becomes non-null the dialog is about to render.
    // A setTimeout(0) fires after Angular's synchronous render cycle
    // so the #confirmCancel element is guaranteed to exist in the DOM.
    effect(() => {
      if (this.confirmState()) {
        setTimeout(() => this.confirmCancelRef()?.nativeElement?.focus(), 0);
      }
    });
  }

  handleNewChat() {
    this.sessionService.createSession();
    this.chatService.loadFromSession();
    this.sessionSelected.emit();
  }

  handleSessionClick(session: ChatSession) {
    if (this.selectionMode()) {
      this.toggleSelection(session.id);
    } else {
      this.sessionService.selectSession(session.id);
      this.chatService.loadFromSession();
      this.sessionSelected.emit();
    }
  }

  handleContextMenu(e: Event, session: ChatSession) {
    e.preventDefault();
    if (!this.selectionMode()) {
      this.selectionMode.set(true);
      this.selectedIds.set(new Set([session.id]));
    }
  }

  toggleGroup(label: string) {
    this.expandedGroups.update(prev => ({ ...prev, [label]: !prev[label] }));
  }

  toggleSelection(sessionId: string) {
    this.selectedIds.update(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sessionId)) {
        newSet.delete(sessionId);
      } else {
        newSet.add(sessionId);
      }
      return newSet;
    });
  }

  selectAll() {
    this.selectedIds.set(new Set(this.sessionService.sessions().map(s => s.id)));
  }

  unselectAll() {
    this.selectedIds.set(new Set());
  }

  exitSelectionMode() {
    this.selectionMode.set(false);
    this.selectedIds.set(new Set());
  }

  handleDeleteSelected() {
    const ids = this.selectedIds();
    if (ids.size === 0) return;
    this.confirmState.set({
      title: 'Delete conversations',
      message: `Delete ${ids.size} conversation(s)? This cannot be undone.`,
      onConfirm: () => {
        this.sessionService.deleteSessions(Array.from(ids));
        this.exitSelectionMode();
        this.chatService.loadFromSession();
      }
    });
  }

  handleDeleteSingle(e: Event, sessionId: string) {
    e.stopPropagation();
    this.confirmState.set({
      title: 'Delete conversation',
      message: 'Delete this conversation? This cannot be undone.',
      onConfirm: () => {
        this.sessionService.deleteSession(sessionId);
        this.chatService.loadFromSession();
      }
    });
  }

  startRename(e: Event, session: ChatSession) {
    e.stopPropagation();
    this.renamingId.set(session.id);
    this.renameValue.set(session.title);
  }

  protected onRenameInput(event: Event): void {
    this.renameValue.set((event.target as HTMLInputElement).value);
  }

  confirmRename() {
    const id = this.renamingId();
    const val = this.renameValue().trim();
    if (id && val) {
      this.sessionService.renameSession(id, val);
    }
    this.renamingId.set(null);
    this.renameValue.set('');
  }

  cancelRename() {
    this.renamingId.set(null);
    this.renameValue.set('');
  }

  confirmDialogConfirm() {
    this.confirmState()?.onConfirm();
    this.confirmState.set(null);
  }

  confirmDialogCancel() {
    this.confirmState.set(null);
  }
}
```
