import { useEffect, useState } from 'react'
import { useAuthz } from '@sentinel-auth/react'

interface Note {
  id: string
  title: string
  content: string
  owner_name: string
}

export function Notes() {
  const { fetchJson } = useAuthz()
  const [notes, setNotes] = useState<Note[]>([])
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:9200'

  const loadNotes = async () => {
    try {
      const data = await fetchJson<Note[]>(`${BACKEND}/notes`)
      setNotes(data)
    } catch (err) {
      console.error('Failed to load notes:', err)
    }
  }

  useEffect(() => {
    loadNotes()
  }, [])

  const createNote = async () => {
    if (!title.trim()) return
    try {
      await fetchJson(`${BACKEND}/notes`, {
        method: 'POST',
        body: JSON.stringify({ title, content }),
      })
      setTitle('')
      setContent('')
      await loadNotes()
    } catch (err) {
      console.error('Failed to create note:', err)
    }
  }

  return (
    <div>
      <h2>Notes</h2>

      <div style={{ marginBottom: '1.5rem', padding: '1rem', border: '1px solid #ddd', borderRadius: 4 }}>
        <input
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={{ display: 'block', width: '100%', marginBottom: '0.5rem', padding: '0.5rem' }}
        />
        <textarea
          placeholder="Content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          style={{ display: 'block', width: '100%', marginBottom: '0.5rem', padding: '0.5rem' }}
          rows={3}
        />
        <button onClick={createNote}>Create Note</button>
      </div>

      {notes.length === 0 ? (
        <p style={{ color: '#666' }}>No notes yet.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {notes.map((note) => (
            <li key={note.id} style={{ marginBottom: '1rem', padding: '1rem', border: '1px solid #eee', borderRadius: 4 }}>
              <strong>{note.title}</strong>
              <p>{note.content}</p>
              <small style={{ color: '#999' }}>by {note.owner_name}</small>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
