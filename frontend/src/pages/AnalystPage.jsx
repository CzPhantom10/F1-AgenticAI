import { useEffect, useRef, useState } from 'react'

import { ErrorState } from '../components/PageState'
import { postAnalystQuery } from '../lib/f1Api'

// ── Suggested questions ───────────────────────────────────────────────────
const SUGGESTIONS = [
  'Why was Verstappen dominant in 2024?',
  'Who had the most wins in the 2024 season?',
  'How did Red Bull compare to Ferrari in 2024?',
  'Who scored the most podiums in 2018?',
  'What was Hamilton\'s performance in the 2024 season?',
]

// ── Source type badge ─────────────────────────────────────────────────────
// ── Source type badge ─────────────────────────────────────────────────────
const SOURCE_COLORS = {
  standing:          'bg-zinc-800 text-zinc-300 border-zinc-700',
  race:              'bg-zinc-800 text-zinc-300 border-zinc-700',
  race_result:       'bg-zinc-800 text-zinc-300 border-zinc-700',
  qualifying_result: 'bg-zinc-800 text-zinc-300 border-zinc-700',
}

function SourceBadge({ source }) {
  const color = SOURCE_COLORS[source.type] ?? 'bg-zinc-800 text-zinc-300 border-zinc-700'
  return (
    <span
      className={`inline-flex items-center rounded border px-2.5 py-1 text-xs font-medium leading-tight ${color}`}
    >
      {source.label}
    </span>
  )
}

// ── Single message bubble ─────────────────────────────────────────────────
function MessageBubble({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[75%] rounded-lg bg-[#27272a] px-4 py-2.5 shadow-sm border border-[#3f3f46]">
          <p className="text-sm text-white/90 leading-6">{msg.content}</p>
        </div>
      </div>
    )
  }

  if (msg.role === 'error') {
    return (
      <div className="flex justify-start mb-4">
        <div className="max-w-[90%]">
          <ErrorState message={msg.content} />
        </div>
      </div>
    )
  }

  // assistant
  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-[85%] space-y-3 min-w-[30%]">
        {/* Header/Label */}
        <div className="flex items-center gap-2">
          <span className="h-5 w-5 flex items-center justify-center rounded bg-red-600 text-[10px] font-bold text-white uppercase">
            A
          </span>
          <span className="text-xs font-semibold text-zinc-400">Analyst</span>
        </div>
        
        {/* Answer text */}
        <div className="text-sm leading-7 text-white/90 space-y-3 pl-7">
          {msg.content.split(/\n+/).map((line, i) => {
            const trimmed = line.trim();
            if (!trimmed) return null;

            // Check if line is bullet point
            if (trimmed.startsWith('•') || trimmed.startsWith('-') || trimmed.startsWith('*')) {
              return (
                <li key={i} className="list-none pl-5 relative before:content-['•'] before:absolute before:left-1 before:text-red-500 font-normal">
                  {trimmed.substring(1).trim()}
                </li>
              );
            }

            // Check if line is heading like "Answer" or "Key Evidence" or "Why" or "Factors Considered" or "Reasons:"
            const cleanHeader = trimmed.replace(/:$/, '');
            if (
              cleanHeader === 'Answer' || 
              cleanHeader === 'Key Evidence' || 
              cleanHeader === 'Why' || 
              cleanHeader === 'Factors Considered' || 
              cleanHeader === 'Reasons'
            ) {
              return (
                <h3 key={i} className="text-xs font-bold uppercase tracking-wider text-red-500 mt-5 mb-1.5 first:mt-0">
                  {cleanHeader}
                </h3>
              );
            }

            // Normal text
            return <p key={i} className="font-normal">{trimmed}</p>;
          })}
        </div>

        {/* Sources */}
        {msg.sources && msg.sources.length > 0 && (
          <div className="flex flex-wrap gap-2 pl-7 mt-3">
            {msg.sources.map((src, idx) => (
              <SourceBadge key={idx} source={src} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Typing indicator ──────────────────────────────────────────────────────
const THINKING_STEPS = [
  'Searching race results...',
  'Fetching qualifying times...',
  'Compiling standings...',
  'Analyzing with Llama 3.3...',
  'Writing response...',
]

function TypingIndicator() {
  const [stepIdx, setStepIdx] = useState(0)

  useEffect(() => {
    const id = setInterval(() => {
      setStepIdx((i) => (i + 1) % THINKING_STEPS.length)
    }, 2800)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-[90%] space-y-3 pl-7">
        <div className="flex items-center gap-2.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-2 w-2 rounded-full bg-red-500"
              style={{ animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }}
            />
          ))}
          <span
            key={stepIdx}
            className="ml-1 text-xs text-white/50"
            style={{ animation: 'fadeIn 0.4s ease' }}
          >
            {THINKING_STEPS[stepIdx]}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────
export function AnalystPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const bottomRef               = useRef(null)
  const inputRef                = useRef(null)

  function scrollToBottom() {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  async function handleSubmit(question) {
    const q = (question ?? input).trim()
    if (!q || loading) return

    setInput('')
    // Keep reference to previous messages for history payload before state updates
    const historyPayload = [...messages]
    setMessages((prev) => [...prev, { role: 'user', content: q }])
    setLoading(true)
    scrollToBottom()

    try {
      const data = await postAnalystQuery(q, historyPayload)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.answer, sources: data.sources },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'error', content: err.message || 'Analyst service unavailable.' },
      ])
    } finally {
      setLoading(false)
      scrollToBottom()
      inputRef.current?.focus()
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex h-[calc(100vh-8.5rem)] flex-col gap-3">
      {/* ── Header ── */}
      <div className="glass-panel rounded-xl px-5 py-2.5">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div>
              <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">AI Assistant</p>
              <h1 className="text-lg font-bold text-white leading-none mt-0.5">F1 Query Assistant</h1>
            </div>
            <p className="hidden md:block text-xs text-zinc-400 mt-3">
              Ask questions about F1 race results, driver stats, and season standings from 2018 onwards.
            </p>
          </div>
          <span className="f1-chip self-center py-0.5 px-2.5 text-[9px]">Llama 3.3 Model</span>
        </div>
      </div>

      {/* ── Chat area ── */}
      <div className="glass-panel flex flex-1 flex-col overflow-hidden rounded-xl">
        {/* Messages scroll region */}
        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-6">
          {/* Empty state */}
          {isEmpty && (
            <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
              {/* Icon */}
              <div className="flex h-16 w-16 items-center justify-center rounded-lg border border-red-600/30 bg-red-600/10">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  className="h-8 w-8 text-red-400"
                >
                  <path d="M11.25 4.533A9.707 9.707 0 0 0 6 3a9.735 9.735 0 0 0-3.25.555.75.75 0 0 0-.5.707v14.25a.75.75 0 0 0 1 .707A8.237 8.237 0 0 1 6 18.75c1.995 0 3.823.707 5.25 1.886V4.533ZM12.75 20.636A8.214 8.214 0 0 1 18 18.75c.966 0 1.89.166 2.75.47a.75.75 0 0 0 1-.708V4.262a.75.75 0 0 0-.5-.707A9.735 9.735 0 0 0 18 3a9.707 9.707 0 0 0-5.25 1.533v16.103Z" />
                </svg>
              </div>

              <div>
                <p className="text-lg font-semibold text-white">F1 AI Assistant</p>
                <p className="mt-1 text-sm text-zinc-400">
                  Get answers about race results, qualifying times, and seasonal standings.
                </p>
              </div>

              {/* Suggestion chips */}
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => handleSubmit(s)}
                    className="rounded border border-zinc-800 bg-zinc-950 px-3.5 py-2 text-xs text-zinc-400 hover:border-zinc-700 hover:text-white hover:bg-zinc-900 transition cursor-pointer font-medium"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Conversation */}
          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}

          {/* Typing indicator */}
          {loading && <TypingIndicator />}

          <div ref={bottomRef} />
        </div>

        {/* ── Input bar ── */}
        <div className="border-t border-zinc-850 px-5 py-4 bg-zinc-900/50">
          <div className="flex items-end gap-3">
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about a driver, race, or season…"
              disabled={loading}
              className="flex-1 resize-none rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm text-white placeholder-zinc-500 outline-none transition focus:border-red-600 disabled:opacity-50"
              style={{ maxHeight: '120px', overflowY: 'auto' }}
            />
            <button
              type="button"
              onClick={() => handleSubmit()}
              disabled={!input.trim() || loading}
              className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg border border-red-600 bg-red-600 text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
              aria-label="Send"
            >
              {loading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-red-300 border-t-transparent" />
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="h-5 w-5"
                >
                  <path d="M3.105 2.288a.75.75 0 0 0-.826.95l1.414 4.926A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.086l-1.414 4.926a.75.75 0 0 0 .826.95 28.897 28.897 0 0 0 15.293-7.154.75.75 0 0 0 0-1.115A28.897 28.897 0 0 0 3.105 2.288Z" />
                </svg>
              )}
            </button>
          </div>
          <p className="mt-2 text-center text-xs text-zinc-500">
            Press Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  )
}
