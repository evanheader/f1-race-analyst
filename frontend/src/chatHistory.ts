import type { AskAnswer } from './api'

export type SavedResult = { answer: AskAnswer } | { error: string }
export interface SavedExchange {
  question: string
  result: SavedResult
}
export interface SavedChat {
  id: string
  updatedAt: number
  exchanges: SavedExchange[]
}

export const CHATS_STORAGE_KEY = 'f1ra-chats'
/** The oldest chats drop off past this, so storage stays small. */
export const MAX_SAVED_CHATS = 30

/** Saved chats, most recent first. Anything unreadable counts as no history. */
export function loadChats(): SavedChat[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(CHATS_STORAGE_KEY) ?? '[]')
    return Array.isArray(saved) ? (saved as SavedChat[]) : []
  } catch {
    return []
  }
}

export function saveChats(chats: SavedChat[]) {
  try {
    localStorage.setItem(CHATS_STORAGE_KEY, JSON.stringify(chats))
  } catch {
    // Storage can be full or blocked. The chat still works for this visit.
  }
}

/** Puts a chat first, replacing its older copy, and keeps at most MAX_SAVED_CHATS. */
export function upsertChat(chats: SavedChat[], chat: SavedChat): SavedChat[] {
  return [chat, ...chats.filter((c) => c.id !== chat.id)].slice(0, MAX_SAVED_CHATS)
}
