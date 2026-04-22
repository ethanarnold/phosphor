import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  useApi,
  useApiKeyPrefix,
  type Document,
  type DocumentList,
} from '../lib/api'
import { useLab } from '../lib/queries'

function fmtBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(1)} MB`
}

function StatusTag({ status }: { status: string }) {
  const color =
    status === 'parsed'
      ? 'complexity-low'
      : status === 'failed'
      ? 'complexity-high'
      : ''
  return <span className={`tag ${color}`}>{status}</span>
}

export default function Documents() {
  const api = useApi()
  const qc = useQueryClient()
  const keyPrefix = useApiKeyPrefix()
  const { data: lab } = useLab()
  const [uploading, setUploading] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery<DocumentList>({
    queryKey: [keyPrefix, 'documents', lab?.id],
    enabled: !!lab,
    queryFn: () => api<DocumentList>(`/api/v1/labs/${lab!.id}/documents?limit=50`),
  })

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!lab || files.length === 0) return
      setError(null)
      setUploading(files.map((f) => f.name))

      const single = files.length === 1
      try {
        if (single) {
          const fd = new FormData()
          fd.append('file', files[0])
          await api<Document>(`/api/v1/labs/${lab.id}/documents`, {
            method: 'POST',
            body: fd,
          })
        } else {
          const fd = new FormData()
          for (const f of files) fd.append('files', f)
          await api<Document[]>(`/api/v1/labs/${lab.id}/documents/bulk`, {
            method: 'POST',
            body: fd,
          })
        }
        qc.invalidateQueries({ queryKey: [keyPrefix, 'documents', lab.id] })
        qc.invalidateQueries({ queryKey: [keyPrefix, 'lab-state', lab.id] })
      } catch (err) {
        const e = err as { detail?: string }
        setError(e.detail ?? 'Upload failed')
      } finally {
        setUploading([])
      }
    },
    [api, lab, qc, keyPrefix],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/*': ['.txt', '.md', '.csv'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    multiple: true,
  })

  if (!lab) return null

  return (
    <>
      <header>
        <div>
          <div className="kicker">Knowledge ingestion</div>
          <h1>Documents</h1>
        </div>
      </header>

      <div
        {...getRootProps()}
        className={`dropzone${isDragActive ? ' active' : ''}`}
        aria-label="Upload documents"
        style={{ marginBottom: 24 }}
      >
        <input {...getInputProps()} />
        {isDragActive
          ? 'Drop files to upload…'
          : 'Drag & drop PDFs, papers, protocols, or notes — or click to choose. Max 25 MB each.'}
      </div>
      {uploading.length > 0 && (
        <div className="muted" style={{ marginBottom: 16 }}>
          Uploading: {uploading.join(', ')}…
        </div>
      )}
      {error && <div className="error" style={{ marginBottom: 16 }}>{error}</div>}

      <section className="section">
        <div className="section-head">
          <div className="label">Library</div>
          {data && data.documents.length > 0 && (
            <span className="muted">
              {data.documents.length} {data.documents.length === 1 ? 'document' : 'documents'}
            </span>
          )}
        </div>
        {isLoading ? (
          <p className="muted">Loading…</p>
        ) : !data || data.documents.length === 0 ? (
          <p className="muted">No documents yet. Upload above to start.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Status</th>
                <th>Chunks</th>
                <th>Size</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {data.documents.map((d) => (
                <tr key={d.id}>
                  <td>
                    {d.filename}
                    {d.parse_error && (
                      <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 4 }}>
                        {d.parse_error}
                      </div>
                    )}
                  </td>
                  <td><StatusTag status={d.status} /></td>
                  <td>{d.chunk_count}</td>
                  <td>{fmtBytes(d.byte_size)}</td>
                  <td className="muted">
                    {new Date(d.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
