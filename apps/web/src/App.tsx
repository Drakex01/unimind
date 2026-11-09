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

export default function App() {
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [selectedPlugin, setSelectedPlugin] = useState('cybersecurity')
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Welcome to UniMind. Selected domain plugin: Cybersecurity Assistant. Ask an architecture or security analysis question.',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking')

  useEffect(() => {
    // Check API health
    fetch('/health/live')
      .then((res) => (res.ok ? setApiStatus('online') : setApiStatus('offline')))
      .catch(() => setApiStatus('offline'))

    // Fetch installed domain plugins
    fetch('/api/v1/plugins')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setPlugins(data)
      })
      .catch((err) => console.error('Failed to fetch plugins:', err))
  }, [])

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    try {
      const res = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Org-ID': 'org_dev_demo',
          'X-Workspace-ID': 'ws_dev_demo',
          'X-User-ID': 'usr_dev_demo',
        },
        body: JSON.stringify({
          message: userMsg,
          domain_plugin_id: selectedPlugin,
          model_id: 'mock-model-v1',
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
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem' }}>
      <header style={{ borderBottom: '1px solid #334155', paddingBottom: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#38bdf8' }}>UniMind</h1>
            <p style={{ margin: '0.25rem 0 0', color: '#94a3b8', fontSize: '0.875rem' }}>
              Adaptive Multimodal Foundation-Model Platform
            </p>
          </div>
          <div>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '0.25rem 0.75rem',
                borderRadius: '9999px',
                fontSize: '0.75rem',
                backgroundColor: apiStatus === 'online' ? '#065f46' : '#7f1d1d',
                color: apiStatus === 'online' ? '#34d399' : '#f87171',
              }}
            >
              ● API {apiStatus}
            </span>
          </div>
        </div>

        <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <label style={{ fontSize: '0.875rem', color: '#cbd5e1' }}>Domain Plugin:</label>
          <select
            value={selectedPlugin}
            onChange={(e) => setSelectedPlugin(e.target.value)}
            style={{
              backgroundColor: '#1e293b',
              color: '#f8fafc',
              border: '1px solid #475569',
              borderRadius: 4,
              padding: '0.25rem 0.5rem',
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
      </header>

      <main>
        <div
          style={{
            minHeight: '400px',
            maxHeight: '550px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
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
                maxWidth: '80%',
                padding: '0.75rem 1rem',
                borderRadius: 8,
                backgroundColor: m.role === 'user' ? '#0284c7' : '#334155',
                color: '#ffffff',
                fontSize: '0.925rem',
                lineHeight: 1.5,
              }}
            >
              <div style={{ fontSize: '0.75rem', opacity: 0.7, marginBottom: '0.25rem' }}>
                {m.role === 'user' ? 'You' : `UniMind [${selectedPlugin}]`}
              </div>
              {m.content}
            </div>
          ))}
          {loading && (
            <div style={{ alignSelf: 'flex-start', color: '#94a3b8', fontStyle: 'italic', fontSize: '0.875rem' }}>
              UniMind is processing request through capability-checked model gateway...
            </div>
          )}
        </div>

        <form onSubmit={handleSend} style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your domain question or task prompt..."
            style={{
              flex: 1,
              backgroundColor: '#1e293b',
              color: '#ffffff',
              border: '1px solid #475569',
              borderRadius: 6,
              padding: '0.75rem 1rem',
              fontSize: '0.925rem',
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
              padding: '0.75rem 1.5rem',
              fontWeight: 600,
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            Send
          </button>
        </form>
      </main>
    </div>
  )
}
