/**
 * useAgentRuntime.ts — conversation state for AGENT OS.
 *
 * The runtime owns four states and nothing about rendering:
 *   idle       nothing happening
 *   listening  the visitor is focused on the prompt / typing
 *   thinking   a question was sent, no tokens yet
 *   speaking   tokens are arriving
 *
 * The provider is an async iterable of string chunks, so the canned local
 * corpus and an on-device model share one interface. To swap in Gemma:
 *
 *   const provider: AgentProvider = {
 *     async *ask(question, history) {
 *       for await (const chunk of llm.generateStream(buildPrompt(question, history))) {
 *         yield chunk.text
 *       }
 *     },
 *   }
 *
 * Lines that start with a two-digit index ("01 Natural Language → SQL") are
 * kept as plain text on the wire and rendered as an indexed list by the bubble
 * component, so structure survives a raw token stream.
 */

import { computed, ref, shallowRef } from 'vue'

export type AgentRole = 'user' | 'agent'

export interface AgentMessage {
  id: number
  role: AgentRole
  text: string
  time: string
  streaming: boolean
}

export interface AgentProvider {
  ask(question: string, history: ReadonlyArray<AgentMessage>): AsyncIterable<string>
}

export type RuntimeState = 'idle' | 'listening' | 'thinking' | 'speaking'

const TZ = 'America/Argentina/Buenos_Aires'

const timeFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: TZ,
  hour12: false,
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

export const stamp = (date = new Date()): string => timeFormatter.format(date)

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

/* ------------------------------------------------------------- corpus --- */

interface CorpusEntry {
  match: RegExp
  answer: string
}

const CORPUS: CorpusEntry[] = [
  {
    match: /rag|retrieval|vector|embedding/i,
    answer: [
      'Diego has used Retrieval Augmented Generation in several production-grade systems.',
      '',
      'Here are the main ones:',
      '',
      '01 Natural Language → SQL',
      '02 Document Intelligence',
      '03 Semantic Product Search',
    ].join('\n'),
  },
  {
    match: /compare|architecture|difference|versus|vs\b/i,
    answer: [
      'They share one principle: retrieval narrows the context before generation runs.',
      '',
      '01 NL→SQL retrieves only the schema and business rules a query can touch',
      '02 Document Intelligence ranks evidence spans before extraction',
      '03 Semantic Search blends structured filters with embeddings, then reranks',
    ].join('\n'),
  },
  {
    match: /experience|career|background|work(ed)?\b/i,
    answer:
      'Diego works across applied AI, distributed systems and integration architecture, with a focus on production APIs, agents, cloud workflows and software that stays maintainable after handover.',
  },
  {
    match: /project|built|system|portfolio/i,
    answer: [
      'Four systems are documented in this portfolio.',
      '',
      '01 Private document extraction',
      '02 Guarded natural language to SQL',
      '03 A financial MCP server',
      '04 Intent-aware semantic search',
    ].join('\n'),
  },
  {
    match: /stack|tech|language|tool|skill/i,
    answer:
      'Python, TypeScript and Java on the core. FastAPI, local LLM runtimes, RAG, MCP and AWS around it. The constant is traceability: explicit contracts, observable pipelines, no silent failures.',
  },
  {
    match: /contact|hire|available|availability|email|reach/i,
    answer:
      'Use this interface to understand the work first. Contact details are in the closing section of the portfolio.',
  },
]

const FALLBACK =
  'I answer from the portfolio context only. Ask about the systems, the architecture behind them, the stack, or how Diego approaches applied AI.'

/** Splits into small chunks so the ripple cadence feels like speech, not paste. */
const chunkify = (text: string): string[] => {
  const chunks: string[] = []
  let buffer = ''
  for (const char of text) {
    buffer += char
    if (buffer.length >= 3 && (char === ' ' || char === '\n')) {
      chunks.push(buffer)
      buffer = ''
    }
  }
  if (buffer) chunks.push(buffer)
  return chunks
}

export const localProvider: AgentProvider = {
  async *ask(question: string): AsyncIterable<string> {
    const entry = CORPUS.find((candidate) => candidate.match.test(question))
    await sleep(420 + Math.random() * 380)
    for (const chunk of chunkify(entry ? entry.answer : FALLBACK)) {
      yield chunk
      await sleep(chunk.includes('\n') ? 60 : 26)
    }
  },
}

/* ------------------------------------------------------------ runtime --- */

export interface RuntimeHooks {
  /** Fired when a message is committed; the field turns this into a ripple. */
  onMessage?: (message: AgentMessage) => void
  /** Fired per streamed chunk; drives the speaking cadence. */
  onToken?: () => void
}

export function useAgentRuntime(provider: AgentProvider = localProvider, hooks: RuntimeHooks = {}) {
  const messages = ref<AgentMessage[]>([])
  const draft = ref('')
  const focused = ref(false)
  const busy = ref(false)
  const error = ref<string | null>(null)
  const nextId = shallowRef(1)

  const state = computed<RuntimeState>(() => {
    if (messages.value.some((message) => message.streaming)) return 'speaking'
    if (busy.value) return 'thinking'
    if (focused.value || draft.value.length > 0) return 'listening'
    return 'idle'
  })

  const canSend = computed(() => draft.value.trim().length > 0 && !busy.value)

  const push = (role: AgentRole, text: string, streaming = false): AgentMessage => {
    const message: AgentMessage = { id: nextId.value++, role, text, time: stamp(), streaming }
    messages.value.push(message)
    if (messages.value.length > 10) messages.value.shift()
    hooks.onMessage?.(message)
    return message
  }

  const seed = (entries: Array<{ role: AgentRole; text: string; time?: string }>): void => {
    for (const entry of entries) {
      messages.value.push({
        id: nextId.value++,
        role: entry.role,
        text: entry.text,
        time: entry.time ?? stamp(),
        streaming: false,
      })
    }
  }

  const send = async (): Promise<void> => {
    const question = draft.value.trim()
    if (!question || busy.value) return

    draft.value = ''
    error.value = null
    push('user', question)
    busy.value = true

    const history = messages.value.slice(0, -1)
    let replyId = -1

    /* The reply must be mutated through the reactive proxy, not through the
       raw object returned by push(): writing to the raw target updates the
       value but never notifies Vue, which left `state` cached on 'speaking'
       and the transcript repainting only when some other ref happened to
       change. Always re-resolve the message from messages.value. */
    const reply = (): AgentMessage | undefined =>
      messages.value.find((message) => message.id === replyId)

    try {
      for await (const chunk of provider.ask(question, history)) {
        if (replyId < 0) {
          busy.value = false
          replyId = push('agent', '', true).id
        }
        const target = reply()
        if (!target) break
        target.text += chunk
        hooks.onToken?.()
      }
      const target = reply()
      if (target) target.streaming = false
      else if (replyId < 0) push('agent', FALLBACK)
    } catch (cause) {
      error.value = 'The agent could not answer. Try again.'
      const target = reply()
      if (target) target.streaming = false
      console.error('[agent-os] provider failed', cause)
    } finally {
      busy.value = false
    }
  }

  const reset = (): void => {
    messages.value = []
    draft.value = ''
    error.value = null
  }

  return { messages, draft, focused, busy, error, state, canSend, send, seed, reset }
}
