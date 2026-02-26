# session.service

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `services__session.service` |
| **Files** | 1 |
| **Total size** | 11,382 bytes |
| **Generated** | 2026-02-26 11:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/services/session.service.ts` (11,382 bytes, Service)

---

## `app/services/session.service.ts`

| Field | Value |
|-------|-------|
| **Role** | Service |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 11,382 bytes |
| **Exports** | `SessionService`, `ChatSession`, `SessionGroup` |

```typescript
﻿import { Injectable, inject, signal, computed, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Message, Citation, GroundingAudit } from '../models/types';

export interface ChatSession {
    id: string;
    title: string;
    messages: Message[];
    updatedAt: Date;
    /** Frontend conversation UUID (legacy — kept for sidebar grouping) */
    vertexConversationId?: string;
    /** ADK server-side session ID — returned by backend on first message in a conversation.
     *  Used for subsequent messages to maintain multi-turn state on the Agent Engine. */
    adkSessionId?: string;
}

export interface SessionGroup {
    label: string;
    sessions: ChatSession[];
}

/** Raw shape of persisted session data (date fields are strings in JSON) */
interface SessionRaw {
    id: string; title: string; updatedAt: string;
    messages: MessageRaw[]; vertexConversationId?: string; adkSessionId?: string;
}
/** Raw shape of persisted message data */
interface MessageRaw {
    id: string; role: 'user' | 'assistant'; content: string;
    timestamp: string;[key: string]: unknown;
}

const STORAGE_KEY = 'alt-ai-sessions';
const CURRENT_SESSION_KEY = 'alt-ai-current-session';

function generateTitle(content: string): string {
    const words = content.split(/\s+/).slice(0, 6);
    let title = words.join(' ');
    if (content.split(/\s+/).length > 6) {
        title += '...';
    }
    return title || 'New Conversation';
}

@Injectable({
    providedIn: 'root'
})
export class SessionService {
    private readonly platformId = inject(PLATFORM_ID);

    // Core state
    readonly sessions = signal<ChatSession[]>(this.loadSessions());
    readonly currentSessionId = signal<string | null>(this.loadCurrentSessionId());

    // Derived
    readonly currentSession = computed(() => {
        const id = this.currentSessionId();
        return this.sessions().find(s => s.id === id) || null;
    });

    readonly conversationTitle = computed(() =>
        this.currentSession()?.title || 'New Conversation'
    );

    // All citations from current session
    readonly currentCitations = computed<Citation[]>(() => {
        const session = this.currentSession();
        if (!session) return [];

        const citationMap = new Map<string, Citation>();
        session.messages.forEach(msg => {
            if (msg.role === 'assistant' && msg.citations) {
                msg.citations.forEach(c => {
                    if (!citationMap.has(c.id)) {
                        citationMap.set(c.id, c);
                    }
                });
            }
        });
        return Array.from(citationMap.values());
    });

    // Grouped sessions for NavPanel display
    readonly groupedSessions = computed<SessionGroup[]>(() => {
        const sessions = this.sessions();
        const today = new Date();
        const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate());
        const yesterday = new Date(todayStart);
        yesterday.setDate(yesterday.getDate() - 1);
        const weekAgo = new Date(todayStart);
        weekAgo.setDate(weekAgo.getDate() - 7);

        const groups: Record<string, ChatSession[]> = {
            'Today': [],
            'Yesterday': [],
            'Previous 7 Days': [],
            'Older': []
        };

        sessions.forEach(session => {
            const d = new Date(session.updatedAt);
            if (d >= todayStart) {
                groups['Today'].push(session);
            } else if (d >= yesterday) {
                groups['Yesterday'].push(session);
            } else if (d >= weekAgo) {
                groups['Previous 7 Days'].push(session);
            } else {
                groups['Older'].push(session);
            }
        });

        return Object.entries(groups)
            .filter(([, sessArr]) => sessArr.length > 0)
            .map(([label, sessArr]) => ({
                label,
                sessions: sessArr.sort((a, b) =>
                    new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
                )
            }));
    });

    constructor() {
        // Ensure there's always a session on init
        if (this.sessions().length === 0 || !this.currentSessionId()) {
            this.createSession();
        }
    }

    createSession(title?: string): string {
        const id = crypto.randomUUID();
        const newSession: ChatSession = {
            id,
            title: title || 'New Conversation',
            messages: [],
            updatedAt: new Date()
        };

        this.sessions.update(prev => [newSession, ...prev]);
        this.currentSessionId.set(id);
        this.persist();
        return id;
    }

    selectSession(sessionId: string) {
        this.currentSessionId.set(sessionId);
        this.persistCurrentId();
    }

    addMessage(sessionId: string, message: Message) {
        this.sessions.update(prev =>
            prev.map(s => {
                if (s.id !== sessionId) return s;

                const updatedMessages = [...s.messages, message];

                // Auto-generate title from first user message
                let title = s.title;
                if (s.title === 'New Conversation' && message.role === 'user' && s.messages.length === 0) {
                    title = generateTitle(message.content);
                }

                return { ...s, title, messages: updatedMessages, updatedAt: new Date() };
            })
        );
        this.persist();
    }

    deleteSession(sessionId: string) {
        this.sessions.update(prev => prev.filter(s => s.id !== sessionId));
        if (this.currentSessionId() === sessionId) {
            const remaining = this.sessions();
            this.currentSessionId.set(remaining.length > 0 ? remaining[0].id : null);
            if (remaining.length === 0) {
                this.createSession();
            }
        }
        this.persist();
    }

    deleteSessions(sessionIds: string[]) {
        const idSet = new Set(sessionIds);
        const currentId = this.currentSessionId();

        this.sessions.update(prev => prev.filter(s => !idSet.has(s.id)));

        if (currentId && idSet.has(currentId)) {
            const remaining = this.sessions();
            this.currentSessionId.set(remaining.length > 0 ? remaining[0].id : null);
            if (remaining.length === 0) {
                this.createSession();
                return;  // createSession calls persist() internally
            }
        }
        this.persist();  // single persist call
    }

    renameSession(sessionId: string, newTitle: string) {
        this.sessions.update(prev =>
            prev.map(s =>
                s.id === sessionId ? { ...s, title: newTitle, updatedAt: new Date() } : s
            )
        );
        this.persist();
    }

    /**
     * Store the ADK session ID returned from the backend (Item #5).
     * This is the server-side session resource name from VertexAiSessionService.
     * Used to resume the same ADK session on subsequent messages.
     */
    setAdkSessionId(sessionId: string, adkSessionId: string) {
        this.sessions.update(prev =>
            prev.map(s =>
                s.id === sessionId ? { ...s, adkSessionId } : s
            )
        );
        this.persist();
    }

    /**
     * S3-③ Memory Bank: Returns the ADK session ID of the previously active session.
     * Used when starting a NEW chat to archive the completed prior session to Memory Bank.
     *
     * Logic: sessions are newest-first. If the current session has no adkSessionId
     * (i.e., it's brand new), look for the most recent session that HAS an adkSessionId.
     */
    getPreviousAdkSessionId(): string | undefined {
        const current = this.currentSession();
        // Only relevant when current session is fresh (no adkSessionId yet)
        if (current?.adkSessionId) return undefined;
        // Find the most recent OTHER session that has an adkSessionId
        const allSessions = this.sessions();
        const previous = allSessions.find(s => s.id !== current?.id && !!s.adkSessionId);
        return previous?.adkSessionId;
    }

    /**
     * Store the Vertex AI conversation ID returned from the backend
     * so subsequent messages in this session use the same conversation.
     */
    setVertexConversationId(sessionId: string, conversationId: string) {
        this.sessions.update(prev =>
            prev.map(s =>
                s.id === sessionId ? { ...s, vertexConversationId: conversationId } : s
            )
        );
        this.persist();
    }

    /**
     * [Layer 2] Attach a GroundingAudit to an existing assistant message.
     *
     * Called by ChatService ~500ms after the stream completes, once the
     * non-blocking checkGrounding API call resolves. The signal update triggers
     * OnPush change detection and the GroundingBadgeComponent fades in.
     *
     * @param messageId - The assistant message's UUID
     * @param audit     - The resolved GroundingAudit from GroundingAuditService
     */
    updateMessageAudit(messageId: string, audit: GroundingAudit): void {
        this.sessions.update(prev =>
            prev.map(s => ({
                ...s,
                messages: s.messages.map(m =>
                    m.id === messageId ? { ...m, audit } : m
                ),
            }))
        );
        this.persist();
    }

    // ----- Persistence -----

    private loadSessions(): ChatSession[] {
        if (!isPlatformBrowser(this.platformId)) return [];  // SSR guard
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (!stored) return [];
            const parsed = JSON.parse(stored) as SessionRaw[];
            return parsed.map((s: SessionRaw) => ({
                ...s,
                updatedAt: new Date(s.updatedAt),
                messages: (s.messages || []).map((m: MessageRaw) => ({
                    ...m,
                    timestamp: new Date(m.timestamp)
                }))
            }));
        } catch (e) {
            console.error('Failed to load sessions:', e);
            return [];
        }
    }

    private loadCurrentSessionId(): string | null {
        if (!isPlatformBrowser(this.platformId)) return null;  // SSR guard
        return localStorage.getItem(CURRENT_SESSION_KEY);
    }

    private persist() {
        if (!isPlatformBrowser(this.platformId)) return;  // SSR guard
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(this.sessions()));
        } catch (e) {
            console.error('Failed to save sessions:', e);
        }
        this.persistCurrentId();
    }

    private persistCurrentId() {
        if (!isPlatformBrowser(this.platformId)) return;  // SSR guard
        const id = this.currentSessionId();
        if (id) {
            localStorage.setItem(CURRENT_SESSION_KEY, id);
        } else {
            localStorage.removeItem(CURRENT_SESSION_KEY);
        }
    }
}


// [TOAST-TEST]
```
