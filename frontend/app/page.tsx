'use client'

import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { API, TOKEN_KEY, responseMessage } from './api'


const MAX_FILE_BYTES = 25 * 1024 * 1024

type DocumentStatus = 'queued' | 'processing' | 'ready' | 'failed'
type Document = { id: number; title: string; status: DocumentStatus; pages: number | null }
type Source = { n: number; title: string; pages: string; snippet: string }
type Answer = { answer: string; sources: Source[] }

function isDocument(value: unknown): value is Document {
  return (
    value !== null &&
    typeof value === 'object' &&
    'id' in value &&
    typeof value.id === 'number' &&
    'title' in value &&
    typeof value.title === 'string' &&
    'status' in value &&
    (value.status === 'queued' || value.status === 'processing' || value.status === 'ready' || value.status === 'failed') &&
    'pages' in value &&
    (typeof value.pages === 'number' || value.pages === null)
  )
}

function isSource(value: unknown): value is Source {
  return (
    value !== null &&
    typeof value === 'object' &&
    'n' in value &&
    typeof value.n === 'number' &&
    'title' in value &&
    typeof value.title === 'string' &&
    'pages' in value &&
    typeof value.pages === 'string' &&
    'snippet' in value &&
    typeof value.snippet === 'string'
  )
}

function isAnswerResponse(value: unknown): value is Answer & { conversation_id?: number } {
  return (
    value !== null &&
    typeof value === 'object' &&
    'answer' in value &&
    typeof value.answer === 'string' &&
    'sources' in value &&
    Array.isArray(value.sources) &&
    value.sources.every(isSource)
  )
}



function Mark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none">
      <path d="M7.5 7.5A6.36 6.36 0 0 1 12 5.64c3.51 0 6.36 2.85 6.36 6.36S15.51 18.36 12 18.36 5.64 15.51 5.64 12" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M5 5v5h5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function UploadIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" />
    </svg>
  )
}

function FileIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 14h6m-6 3h4" />
    </svg>
  )
}

function ArrowIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14m-5-5 5 5-5 5" />
    </svg>
  )
}

function Workspace({ token, onLogout }: { token: string; onLogout: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const uploadRequest = useRef(0)
  const hasInitializedSelection = useRef(false)
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null)
  const [documentsError, setDocumentsError] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [answerError, setAnswerError] = useState('')
  const [isAsking, setIsAsking] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [mode, setMode] = useState<'agent' | 'basic'>('agent')

    const authedFetch = useCallback(
    async (path: string, options: RequestInit = {}) => {
      const headers = new Headers(options.headers)
      headers.set('Authorization', `Bearer ${token}`)
      const response = await fetch(`${API}${path}`, { ...options, headers })
      if (response.status === 401) onLogout()
      return response
    },
    [token, onLogout],
  )

  const refreshDocuments = useCallback(async () => {
    
    
    const response = await authedFetch('/documents')
    const result: unknown = await response.json()
    if (!response.ok) throw new Error(responseMessage(result, 'Could not load uploaded documents.'))
    if (!Array.isArray(result) || !result.every(isDocument)) {
      throw new Error('The document service returned an invalid document list.')
    }
    
    setDocuments(result)
    setDocumentsError('')
    if (!hasInitializedSelection.current) {
      hasInitializedSelection.current = true
      setSelectedDocumentId(result.find((document) => document.status === 'ready')?.id ?? result[0]?.id ?? null)
    }
  }, [authedFetch])

  useEffect(() => {
    let cancelled = false
    const loadDocuments = async () => {
      try {
        await refreshDocuments()
      } catch (error) {
        if (!cancelled) {
          setDocumentsError(error instanceof Error ? error.message : 'Could not load uploaded documents.')
        }
      }
    }

    void loadDocuments()
    return () => {
      cancelled = true
    }
  }, [refreshDocuments])
  

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0]
    event.target.value = ''
    if (!nextFile) return
    const requestId = ++uploadRequest.current

    setIsUploading(true)
    setUploadError('')

    if (nextFile.size > MAX_FILE_BYTES) {
      setIsUploading(false)
      setUploadError('File too large (max 25 MB).')
      return
    }
    if (nextFile.type !== 'application/pdf' && !nextFile.name.toLowerCase().endsWith('.pdf')) {
      setIsUploading(false)
      setUploadError('Choose a PDF file.')
      return
    }

    const body = new FormData()
    body.append('file', nextFile)
    try {
      const response = await authedFetch('/documents', { method: 'POST', body })
      const result: unknown = await response.json()
      if (requestId !== uploadRequest.current) return
      if (!response.ok) throw new Error(responseMessage(result, 'Upload failed.'))
      if (
        !result ||
        typeof result !== 'object' ||
        !('id' in result) ||
        typeof result.id !== 'number' ||
        !('status' in result) ||
        (result.status !== 'queued' && result.status !== 'processing' && result.status !== 'ready')
      ) {
        throw new Error('The server returned an invalid upload response.')
      }
      hasInitializedSelection.current = true
      setSelectedDocumentId(result.id)
      await refreshDocuments()
    } catch (error) {
      if (requestId !== uploadRequest.current) return
      setUploadError(error instanceof Error ? error.message : 'Could not reach the document server.')
    } finally {
      if (requestId === uploadRequest.current) setIsUploading(false)
    }
  }

  const startNewChat = () => {
    hasInitializedSelection.current = true
    setConversationId(null)
    setQuestion('')
    setAnswer(null)
    setAnswerError('')
    setUploadError('')
    setSelectedDocumentId(null)
    inputRef.current?.click()
  }

  const hasProcessingDocuments = documents.some(
    (document) => document.status === 'queued' || document.status === 'processing',
  )

  useEffect(() => {
    if (!hasProcessingDocuments) return

    const timer = setInterval(() => {
      void refreshDocuments().catch((error: unknown) => {
        setDocumentsError(error instanceof Error ? error.message : 'Could not refresh document status.')
      })
    }, 1500)
    return () => clearInterval(timer)
  }, [hasProcessingDocuments, refreshDocuments])

  const selectedDocument = documents.find((document) => document.id === selectedDocumentId)
  const documentReady = selectedDocument?.status === 'ready'

  const ask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedQuestion = question.trim()
    if (selectedDocumentId === null || selectedDocument?.status !== 'ready' || !trimmedQuestion || isAsking) return
      
    setIsAsking(true)
    setAnswer(null)
    setAnswerError('')
    try {
const response = await authedFetch(`/${mode === 'agent' ? 'agent' : 'chat'}`, {        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: trimmedQuestion,
          document_ids: [selectedDocumentId],
          conversation_id: conversationId,
        }),
      })
      const result: unknown = await response.json()
      if (response.status === 404) setConversationId(null)
      if (!response.ok) throw new Error(responseMessage(result, 'Could not get an answer.'))
      if (!isAnswerResponse(result)) {
        throw new Error('The answer service returned an invalid response.')
      }
      if (typeof result.conversation_id === 'number') {
        setConversationId(result.conversation_id)
      }
      setAnswer({ answer: result.answer, sources: result.sources })
    } catch (error) {
      setAnswerError(error instanceof Error ? error.message : 'Could not reach the answer service.')
    } finally {
      setIsAsking(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#0b0c0c] text-[#f3f4ef] selection:bg-lime-300 selection:text-neutral-950">
      <div className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col px-5 sm:px-8 lg:px-12">
        <header className="flex h-20 items-center justify-between border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-full bg-[#c9f27b] text-[#10120d]"><Mark /></span>
            <span className="text-[17px] font-medium tracking-[-0.03em]">cognora</span>
          </div>
          <button
  type="button"
  onClick={onLogout}
  className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/50 transition hover:text-white"
>
  Log out
</button>
        </header>

        <section className="grid flex-1 items-center gap-12 py-12 lg:grid-cols-[0.82fr_1.18fr] lg:gap-20 lg:py-16">
          <div className="max-w-xl">
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[11px] uppercase tracking-[0.16em] text-white/45">
              <span className="size-1.5 rounded-full bg-[#c9f27b]" />
              context-aware answers
            </div>
            <h1 className="text-[clamp(2.9rem,6vw,5.7rem)] font-medium leading-[0.92] tracking-[-0.065em]">
              Ask your PDF.<br />
              <span className="text-white/35">Get the point.</span>
            </h1>
            <p className="mt-7 max-w-md text-base leading-7 text-white/50">
              Upload a document and ask questions in plain language. Cognora finds the relevant context and gives you a clear answer.
            </p>
            <div className="mt-10 flex items-center gap-7 text-xs text-white/30">
              <span>PDF only</span>
              <span className="h-3 w-px bg-white/15" />
              <span>Up to 25 MB</span>
              <span className="h-3 w-px bg-white/15" />
              <span>Secure</span>
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-[#121414] p-2 shadow-2xl shadow-black/40">
            <div className="rounded-[22px] border border-white/[0.06] bg-[#171919] p-5 sm:p-7">
              <div className="mb-6 flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium">Your workspace</p>
                  <p className="mt-1 text-xs text-white/35">
                    {isUploading
                      ? 'Uploading document…'
                      : selectedDocument
                        ? `${selectedDocument.title} · ${selectedDocument.status}`
                        : 'Select a document or start a new chat'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={startNewChat}
                  disabled={isAsking || isUploading}
                  className="shrink-0 rounded-lg border border-[#c9f27b]/30 px-3 py-2 text-xs font-medium text-[#c9f27b] transition hover:bg-[#c9f27b]/10 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  New chat
                </button>
              </div>

              <input ref={inputRef} type="file" accept="application/pdf,.pdf" onChange={handleFile} disabled={isAsking || isUploading} className="sr-only" />
              <div>
                <div className="mb-2 flex items-center justify-between px-1">
                  <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-white/35">Your documents</span>
                  <span className="text-[10px] text-white/25">{documents.length} uploaded</span>
                </div>
                {documents.length > 0 ? (
                  <ul className="max-h-48 space-y-2 overflow-y-auto pr-1">
                    {documents.map((document) => {
                      const selected = selectedDocumentId === document.id
                      return (
                        <li key={document.id}>
                          <button
                            type="button"
                            aria-pressed={selected}
                            disabled={isAsking}
                            onClick={() => {
                              hasInitializedSelection.current = true
                              setSelectedDocumentId(document.id)
                              setConversationId(null)
                              setQuestion('')
                              setAnswer(null)
                              setAnswerError('')
                            }}
                            className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left transition disabled:cursor-not-allowed ${
                              selected
                                ? 'border-[#c9f27b]/35 bg-[#c9f27b]/[0.06]'
                                : 'border-white/[0.07] bg-white/[0.015] hover:border-white/20 hover:bg-white/[0.035]'
                            }`}
                          >
                            <span className={`grid size-9 shrink-0 place-items-center rounded-lg ${
                              selected ? 'bg-[#c9f27b] text-neutral-950' : 'bg-white/[0.06] text-white/50'
                            }`}>
                              <FileIcon />
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-xs font-medium text-white/80">{document.title}</span>
                              <span className="mt-1 block text-[10px] text-white/35">
                                {document.pages === null ? 'Pages unavailable' : `${document.pages} ${document.pages === 1 ? 'page' : 'pages'}`}
                              </span>
                            </span>
                            <span className={`shrink-0 text-[10px] capitalize ${
                              document.status === 'ready' ? 'text-[#c9f27b]' :
                                document.status === 'failed' ? 'text-red-300' : 'text-white/40'
                            }`}>
                              {document.status === 'queued' ? 'Waiting' : document.status}
                            </span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                ) : (
                <button
                  type="button"
                  onClick={startNewChat}
                  className="group flex min-h-36 w-full flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-white/[0.015] text-center transition hover:border-[#c9f27b]/45 hover:bg-[#c9f27b]/[0.03]"
                >
                  <span className="mb-3 grid size-10 place-items-center rounded-full border border-white/10 bg-white/[0.04] text-white/55 transition group-hover:text-[#c9f27b]"><UploadIcon /></span>
                  <span className="text-sm font-medium">Upload your first PDF</span>
                  <span className="mt-1 text-xs text-white/30">Start a new chat with a document</span>
                </button>
                )}
                {documentsError && <p role="alert" className="mt-3 px-1 text-xs leading-5 text-red-300">{documentsError}</p>}
                {uploadError && <p role="alert" className="mt-3 px-1 text-xs leading-5 text-red-300">{uploadError}</p>}
              </div>

              <div className="mt-4">
                <div className="mb-2 flex items-center justify-between px-1">
                  <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-white/35">Retrieval mode</span>
                  <span className="text-[10px] text-white/25">
                    {mode === 'agent' ? 'Multi-step reasoning' : 'Fast direct search'}
                  </span>
                </div>
                <div
                  role="group"
                  aria-label="Retrieval mode"
                  className="grid grid-cols-2 rounded-xl border border-white/10 bg-[#0e1010] p-1"
                >
                  <button
                    type="button"
                    disabled={isAsking}
                    aria-pressed={mode === 'agent'}
                    onClick={() => {
                      setMode('agent')
                      setAnswer(null)
                      setAnswerError('')
                    }}
                    className={`rounded-lg px-3 py-2.5 text-xs font-medium transition ${
                      mode === 'agent'
                        ? 'bg-white/10 text-white shadow-sm'
                        : 'text-white/35 hover:text-white/60'
                    }`}
                  >
                    Agent
                  </button>
                  <button
                    type="button"
                    disabled={isAsking}
                    aria-pressed={mode === 'basic'}
                    onClick={() => {
                      setMode('basic')
                      setAnswer(null)
                      setAnswerError('')
                    }}
                    className={`rounded-lg px-3 py-2.5 text-xs font-medium transition ${
                      mode === 'basic'
                        ? 'bg-white/10 text-white shadow-sm'
                        : 'text-white/35 hover:text-white/60'
                    }`}
                  >
                    Basic retrieval
                  </button>
                </div>
              </div>

              {(isAsking || answer || answerError) && (
                <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.025] p-5">
                  <div className="mb-3 flex items-center gap-2 text-xs text-[#c9f27b]">
                    <span className="size-1.5 rounded-full bg-current" />
                    {mode === 'agent' ? 'Agent answer' : 'Basic retrieval answer'}
                  </div>
                  <div className="max-h-72 overflow-y-auto pr-2">
                    {isAsking && <p role="status" className="text-sm leading-6 text-white/50">Searching your document…</p>}
                    {answerError && <p role="alert" className="text-sm leading-6 text-red-300">{answerError}</p>}
                    {answer && (
                      <>
                        <p className="whitespace-pre-wrap text-sm leading-6 text-white/75">{answer.answer}</p>
                        {answer.sources.length > 0 && (
                          <div className="mt-5 border-t border-white/10 pt-4">
                            <p className="mb-3 text-[10px] font-medium uppercase tracking-[0.14em] text-white/35">Sources</p>
                            <ul className="space-y-3">
                              {answer.sources.map((source) => (
                                <li key={`${source.n}-${source.title}`} className="text-xs leading-5 text-white/45">
                                  <p className="font-medium text-white/65">[{source.n}] {source.title} · page{source.pages.includes('-') ? 's' : ''} {source.pages}</p>
                                  <p className="mt-1">{source.snippet}</p>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              )}

              <form onSubmit={ask} className="mt-4">
                <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-[#0e1010] p-2 pl-4 transition focus-within:border-white/25">
                  <input
                    value={question}
                    onChange={(event) => {
                      setQuestion(event.target.value)
                      setAnswer(null)
                      setAnswerError('')
                    }}
                    disabled={!documentReady || isAsking}
                    placeholder={documentReady ? 'Ask anything about this document…' : 'Upload and prepare a PDF to begin…'}
                    className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-white/25 disabled:cursor-not-allowed"
                  />
                  <button
                    type="submit"
                    disabled={!documentReady || !question.trim() || isAsking}
                    aria-label="Ask question"
                    className="grid size-10 shrink-0 place-items-center rounded-xl bg-[#c9f27b] text-neutral-950 transition hover:bg-[#d5ff87] disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/20"
                  >
                    {isAsking ? <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent" /> : <ArrowIcon />}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </section>

        <footer className="flex h-16 items-center justify-between border-t border-white/[0.07] text-[11px] text-white/25">
          <span>© 2025 cognora</span>
          <span>Read less. Understand more.</span>
        </footer>
      </div>
    </main>
  )
}


export default function App() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)
  const [isCheckingStorage, setIsCheckingStorage] = useState(true)

  useEffect(() => {
    let savedToken: string | null = null
    try {
      savedToken = sessionStorage.getItem(TOKEN_KEY)
    } catch {
      // storage unavailable: send the user to sign in
    }
    if (savedToken) setToken(savedToken)
    else router.replace('/login')
    setIsCheckingStorage(false)
  }, [router])

  const handleLogout = useCallback(() => {
    try { sessionStorage.removeItem(TOKEN_KEY) } catch {}
    setToken(null)
    router.replace('/login')
  }, [router])

  if (isCheckingStorage || !token) return null
  return <Workspace token={token} onLogout={handleLogout} />
}