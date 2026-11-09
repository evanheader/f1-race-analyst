import type { components } from './api-types'

type Schemas = components['schemas']
export type Race = Schemas['RaceOut']
export type RaceSummary = Schemas['RaceSummaryOut']
export type RaceResult = Schemas['ResultOut']
export type Lap = Schemas['LapOut']
export type PitStop = Schemas['PitStopOut']
export type AskAnswer = Schemas['AskOut']
export type AskTurn = Schemas['AskTurnIn']

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const MAX_QUESTION_LENGTH = 500
/** The API takes at most this many earlier exchanges, and cuts no answer, so the page trims them first. */
export const MAX_HISTORY = 3
export const MAX_HISTORY_ANSWER_LENGTH = 4000

/** An error answer from the API: `detail` is the API's own message when it sent one. */
export class ApiError extends Error {
  status: number
  detail: string | null

  constructor(status: number, detail: string | null) {
    super(detail ?? `Request failed with status ${status}`)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) {
    let detail: string | null = null
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      // The body was not JSON.
    }
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export const getRaces = (season?: number) =>
  request<RaceSummary[]>(season === undefined ? '/races' : `/races?season=${season}`)
export const getRace = (id: number) => request<Race>(`/races/${id}`)
export const getResults = (id: number) => request<RaceResult[]>(`/races/${id}/results`)
export const getSprintResults = (id: number) => request<RaceResult[]>(`/races/${id}/sprint-results`)
export const getLaps = (id: number) => request<Lap[]>(`/races/${id}/laps`)
export const getPitStops = (id: number) => request<PitStop[]>(`/races/${id}/pit-stops`)
export const ask = (question: string, history: AskTurn[] = []) =>
  request<AskAnswer>('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history }),
  })
