import React, { useState, useEffect } from 'react'

interface Plugin {
  plugin: {
    id: string
    name: string
    version: string
    description: string
  }
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface AuthState {
  token: string | null
  email: string | null
  orgId: string | null
  workspaceId: string | null
  role: string | null
}

export default function App() {
  const [auth, setAuth] = useState<AuthState>({
    token: null,
    email: null,
    orgId: null,
    workspaceId: null,
    role: null,
  })

  // Auth form states
  const [authMode, setAuthMode] = useState<'login' | 'register'>('register')
  const [authEmail, setAuthEmail] = useState('admin@unimind.org')
  const [authPassword, setAuthPassword] = useState('Password123!')
  const [authFullName, setAuthFullName] = useState('UniMind Admin')
  const [authOrgName, setAuthOrgName] = useState('Defense Lab')
  const [authError, setAuthError] = useState<string | null>(null)

  // Chat states
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [selectedPlugin, setSelectedPlugin] = useState('cybersecurity')
  const [selectedModel, setSelectedModel] = useState('mock-model-v1')
  const [streamEnabled, setStreamEnabled] = useState(true)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Welcome to UniMind Platform. Please register or login to establish your tenant context and begin interacting.',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking')

  useEffect(() => {
    fetch('/health/live')
      .then((res) => (res.ok ? setApiStatus('online') : setApiStatus('offline')))
      .catch(() => setApiStatus('offline'))

    fetch('/api/v1/plugins')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setPlugins(data)
      })
      .catch((err) => console.error('Failed to fetch plugins:', err))
  }, [])

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError(null)

    const endpoint = authMode === 'register' ? '/api/v1/auth/register' : '/api/v1/auth/login'
    const body =
      authMode === 'register'
        ? {
            email: authEmail,
            password: authPassword,
            full_name: authFullName,
            organization_name: authOrgName,
          }
        : {
            email: authEmail,
            password: authPassword,
          }

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Authentication failed')
      }

      const data = await res.json()
      setAuth({
        token: data.access_token,
        email: authEmail,
        orgId: data.org_id,
        workspaceId: data.workspace_id,
        role: data.role,
      })
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Authenticated as ${authEmail}. Tenant Org: [${data.org_id}], Workspace: [${data.workspace_id}], Role: [${data.role}].`,
        },
      ])
    } catch (err: any) {
      setAuthError(err.message)
    }
  }

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (auth.token) {
      headers['Authorization'] = `Bearer ${auth.token}`
    } else {
      headers['X-Org-ID'] = 'org_dev_demo'
      headers['X-Workspace-ID'] = 'ws_dev_demo'
      headers['X-User-ID'] = 'usr_dev_demo'
    }

    try {
      if (streamEnabled) {
        // Server-Sent Events (SSE) streaming request
        const res = await fetch('/api/v1/chat/stream', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            message: userMsg,
            domain_plugin_id: selectedPlugin,
            model_id: selectedModel,
          }),
        })

        if (!res.ok) {
          const errData = await res.json()
          throw new Error(errData.detail || 'Streaming failed')
        }

        // Initialize empty assistant message
        setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

        const reader = res.body?.getReader()
        const decoder = new TextDecoder()
        if (reader) {
          let doneReading = false
          while (!doneReading) {
            const { value, done } = await reader.read()
            if (done) break
            const textChunk = decoder.decode(value)
            const lines = textChunk.split('\n')
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.replace('data: ', ''))
                  if (data.delta) {
                    setMessages((prev) => {
                      const updated = [...prev]
                      const lastIdx = updated.length - 1
                      updated[lastIdx] = {
                        ...updated[lastIdx],
                        content: updated[lastIdx].content + data.delta,
                      }
                      return updated
                    })
                  }
                  if (data.error) {
                    throw new Error(data.error)
                  }
                } catch (pErr) {
                  // Skip parse errors on partial frames
                }
              }
            }
          }
        }
      } else {
        // Standard Unary Chat Request
        const res = await fetch('/api/v1/chat', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            message: userMsg,
            domain_plugin_id: selectedPlugin,
            model_id: selectedModel,
          }),
        })

        if (!res.ok) {
          const errData = await res.json()
          throw new Error(errData.detail || 'API request failed')
        }

        const data = await res.json()
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.response_text,
          },
        ])
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}`,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      {/* Top Header */}
      <header style={{ borderBottom: '1px solid #334155', paddingBottom: '1rem', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#38bdf8' }}>UniMind</h1>
            <p style={{ margin: '0.2rem 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
              Adaptive Multimodal Foundation-Model Platform
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span
              style={{
                padding: '0.2rem 0.6rem',
                borderRadius: '9999px',
                fontSize: '0.75rem',
                backgroundColor: apiStatus === 'online' ? '#065f46' : '#7f1d1d',
                color: apiStatus === 'online' ? '#34d399' : '#f87171',
              }}
            >
              ● API {apiStatus}
            </span>
            {auth.token ? (
              <span
                style={{
                  padding: '0.2rem 0.6rem',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  backgroundColor: '#1e3a8a',
                  color: '#93c5fd',
                }}
              >
                Tenant: {auth.orgId?.substring(0, 10)}... [{auth.role}]
              </span>
            ) : (
              <span
                style={{
                  padding: '0.2rem 0.6rem',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  backgroundColor: '#475569',
                  color: '#cbd5e1',
                }}
              >
                Unauthenticated (Dev Fallback)
              </span>
            )}
          </div>
        </div>

        {/* Identity & Authentication Bar */}
        {!auth.token && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: '#1e293b', borderRadius: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.85rem', color: '#cbd5e1', fontWeight: 600 }}>
                {authMode === 'register' ? 'Register Tenant Identity' : 'Sign In with Existing Account'}
              </span>
              <button
                type="button"
                onClick={() => setAuthMode(authMode === 'register' ? 'login' : 'register')}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#38bdf8',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  textDecoration: 'underline',
                }}
              >
                {authMode === 'register' ? 'Have an account? Log in' : 'Need an account? Register'}
              </button>
            </div>

            <form onSubmit={handleAuthSubmit} style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              <input
                type="email"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                placeholder="Email"
                style={{
                  padding: '0.35rem 0.6rem',
                  borderRadius: 4,
                  border: '1px solid #475569',
                  backgroundColor: '#0f172a',
                  color: '#fff',
                  fontSize: '0.8rem',
                }}
              />
              <input
                type="password"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                placeholder="Password"
                style={{
                  padding: '0.35rem 0.6rem',
                  borderRadius: 4,
                  border: '1px solid #475569',
                  backgroundColor: '#0f172a',
                  color: '#fff',
                  fontSize: '0.8rem',
                }}
              />
              {authMode === 'register' && (
                <>
                  <input
                    type="text"
                    value={authFullName}
                    onChange={(e) => setAuthFullName(e.target.value)}
                    placeholder="Full Name"
                    style={{
                      padding: '0.35rem 0.6rem',
                      borderRadius: 4,
                      border: '1px solid #475569',
                      backgroundColor: '#0f172a',
                      color: '#fff',
                      fontSize: '0.8rem',
                    }}
                  />
                  <input
                    type="text"
                    value={authOrgName}
                    onChange={(e) => setAuthOrgName(e.target.value)}
                    placeholder="Organization Name"
                    style={{
                      padding: '0.35rem 0.6rem',
                      borderRadius: 4,
                      border: '1px solid #475569',
                      backgroundColor: '#0f172a',
                      color: '#fff',
                      fontSize: '0.8rem',
                    }}
                  />
                </>
              )}
              <button
                type="submit"
                style={{
                  backgroundColor: '#0284c7',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 4,
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                {authMode === 'register' ? 'Register & Provision Tenant' : 'Sign In'}
              </button>
            </form>
            {authError && (
              <div style={{ color: '#f87171', fontSize: '0.75rem', marginTop: '0.25rem' }}>{authError}</div>
            )}
          </div>
        )}

        {/* Domain Plugin & Model Selector Controls */}
        <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
          <div>
            <label style={{ fontSize: '0.8rem', color: '#94a3b8', marginRight: '0.4rem' }}>Domain Plugin:</label>
            <select
              value={selectedPlugin}
              onChange={(e) => setSelectedPlugin(e.target.value)}
              style={{
                backgroundColor: '#1e293b',
                color: '#f8fafc',
                border: '1px solid #475569',
                borderRadius: 4,
                padding: '0.25rem 0.5rem',
                fontSize: '0.8rem',
              }}
            >
              {plugins.map((p) => (
                <option key={p.plugin.id} value={p.plugin.id}>
                  {p.plugin.name} (v{p.plugin.version})
                </option>
              ))}
              {plugins.length === 0 && <option value="cybersecurity">Cybersecurity Assistant (default)</option>}
            </select>
          </div>

          <div>
            <label style={{ fontSize: '0.8rem', color: '#94a3b8', marginRight: '0.4rem' }}>Foundation Model:</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              style={{
                backgroundColor: '#1e293b',
                color: '#f8fafc',
                border: '1px solid #475569',
                borderRadius: 4,
                padding: '0.25rem 0.5rem',
                fontSize: '0.8rem',
              }}
            >
              <option value="mock-model-v1">Mock Provider (Deterministic Offline)</option>
              <option value="gemini-3.8-flash">Google Gemini 3.8 Flash (Cloud)</option>
              <option value="gemini-3.5-flash-lite">Google Gemini 3.5 Flash-Lite (Fast/Low Cost)</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <input
              type="checkbox"
              id="streamToggle"
              checked={streamEnabled}
              onChange={(e) => setStreamEnabled(e.target.checked)}
              style={{ cursor: 'pointer' }}
            />
            <label htmlFor="streamToggle" style={{ fontSize: '0.8rem', color: '#cbd5e1', cursor: 'pointer' }}>
              Streaming Tokens (SSE)
            </label>
          </div>
        </div>
      </header>

      {/* Main Chat Interface */}
      <main>
        <div
          style={{
            minHeight: '380px',
            maxHeight: '520px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
            padding: '1rem',
            backgroundColor: '#1e293b',
            borderRadius: 8,
            border: '1px solid #334155',
          }}
        >
          {messages.map((m, idx) => (
            <div
              key={idx}
              style={{
                alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '82%',
                padding: '0.75rem 1rem',
                borderRadius: 8,
                backgroundColor: m.role === 'user' ? '#0284c7' : '#334155',
                color: '#ffffff',
                fontSize: '0.9rem',
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
              }}
            >
              <div style={{ fontSize: '0.75rem', opacity: 0.7, marginBottom: '0.25rem' }}>
                {m.role === 'user' ? (auth.email || 'You') : `UniMind [${selectedPlugin}]`}
              </div>
              {m.content}
            </div>
          ))}
          {loading && !messages[messages.length - 1]?.content && (
            <div style={{ alignSelf: 'flex-start', color: '#94a3b8', fontStyle: 'italic', fontSize: '0.85rem' }}>
              Invoking {selectedModel} via capability-aware gateway...
            </div>
          )}
        </div>

        <form onSubmit={handleSend} style={{ display: 'flex', gap: '0.5rem', marginTop: '0.85rem' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Ask a ${selectedPlugin} question or task instruction...`}
            style={{
              flex: 1,
              backgroundColor: '#1e293b',
              color: '#ffffff',
              border: '1px solid #475569',
              borderRadius: 6,
              padding: '0.7rem 1rem',
              fontSize: '0.9rem',
              outline: 'none',
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            style={{
              backgroundColor: loading || !input.trim() ? '#475569' : '#0284c7',
              color: '#ffffff',
              border: 'none',
              borderRadius: 6,
              padding: '0.7rem 1.4rem',
              fontWeight: 600,
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            {streamEnabled ? 'Stream' : 'Send'}
          </button>
        </form>
      </main>
    </div>
  )
}
