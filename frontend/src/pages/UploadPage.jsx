import { useState, useRef } from 'react'
import { uploadFile } from '../api/client'
import { Upload, CheckCircle, AlertCircle, CloudUpload, FileText } from 'lucide-react'

const SOURCES = [
  {
    id: 'sap',
    label: 'SAP',
    subtitle: 'Fuel & Procurement',
    scope: 'Scope 1',
    color: 'blue',
    accept: '.csv,.txt',
    description: 'Handles German column names (Menge, Buchungsdatum...) and mixed units (gallons ↔ litres). Auto-converts and maps to canonical fields.',
  },
  {
    id: 'utility',
    label: 'Utility',
    subtitle: 'Electricity Bills',
    scope: 'Scope 2',
    color: 'amber',
    accept: '.csv,.pdf',
    description: 'Accepts CSV or PDF. Normalises billing periods that span calendar months. Applies UK grid electricity emission factor (DEFRA 2023).',
  },
  {
    id: 'travel',
    label: 'Travel',
    subtitle: 'Flights, Hotels, Taxis',
    scope: 'Scope 3',
    color: 'purple',
    accept: '.csv',
    description: 'Calculates flight distances from IATA airport codes using haversine formula. Separate emission factors for economy/business class.',
  },
]

const COLOR = {
  blue:   { ring: 'ring-blue-400', bg: 'bg-blue-50', badge: 'bg-blue-100 text-blue-700', text: 'text-blue-700', btn: 'bg-blue-600 hover:bg-blue-700' },
  amber:  { ring: 'ring-amber-400', bg: 'bg-amber-50', badge: 'bg-amber-100 text-amber-700', text: 'text-amber-700', btn: 'bg-amber-500 hover:bg-amber-600' },
  purple: { ring: 'ring-purple-400', bg: 'bg-purple-50', badge: 'bg-purple-100 text-purple-700', text: 'text-purple-700', btn: 'bg-purple-600 hover:bg-purple-700' },
}

function UploadCard({ source }) {
  const [file, setFile] = useState(null)
  const [state, setState] = useState('idle') // idle | uploading | success | error
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const inputRef = useRef()
  const c = COLOR[source.color]

  const handleDrop = (e) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  const handleSubmit = async () => {
    if (!file) return
    setState('uploading')
    setProgress(0)
    setError('')
    try {
      const res = await uploadFile(source.id, file, setProgress)
      setResult(res.data)
      setState('success')
    } catch (err) {
      setError(err.response?.data?.error || 'Upload failed')
      setState('error')
    }
  }

  const reset = () => { setFile(null); setState('idle'); setResult(null); setProgress(0); setError('') }

  return (
    <div className={`bg-white rounded-xl border-2 ${state === 'success' ? 'border-emerald-400' : 'border-gray-200'} p-6 flex flex-col gap-4 shadow-sm`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${c.badge}`}>{source.scope}</span>
          </div>
          <h2 className={`text-xl font-bold mt-1 ${c.text}`}>{source.label}</h2>
          <p className="text-sm text-gray-500">{source.subtitle}</p>
        </div>
        {state === 'success' && <CheckCircle className="text-emerald-500 w-7 h-7 shrink-0" />}
        {state === 'error' && <AlertCircle className="text-red-500 w-7 h-7 shrink-0" />}
      </div>

      <p className="text-xs text-gray-500 leading-relaxed">{source.description}</p>

      {state === 'success' ? (
        <div className="bg-emerald-50 rounded-lg p-4 text-sm">
          <p className="font-semibold text-emerald-700">✓ {result.rows_created} rows imported</p>
          <p className="text-emerald-600 text-xs mt-1">Batch #{result.batch_id} · Head to Review Dashboard to approve records.</p>
          <button onClick={reset} className="mt-3 text-xs text-emerald-700 underline">Upload another file</button>
        </div>
      ) : (
        <>
          <div
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition ${file ? `${c.ring} ${c.bg}` : 'border-gray-200 hover:border-gray-300'}`}
            onDrop={handleDrop}
            onDragOver={e => e.preventDefault()}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept={source.accept}
              className="hidden"
              onChange={e => { setFile(e.target.files[0]); setState('idle') }}
            />
            <CloudUpload className="w-8 h-8 mx-auto text-gray-400 mb-2" />
            {file ? (
              <div className="flex items-center justify-center gap-2 text-sm font-medium text-gray-700">
                <FileText className="w-4 h-4" />
                {file.name}
                <span className="text-xs text-gray-400">({(file.size/1024).toFixed(1)} KB)</span>
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                Drop a file here or <span className="text-blue-600 font-medium">browse</span>
                <br />
                <span className="text-xs text-gray-400">{source.accept}</span>
              </p>
            )}
          </div>

          {state === 'error' && (
            <p className="text-xs text-red-600 bg-red-50 rounded p-2">{error}</p>
          )}

          {state === 'uploading' && (
            <div>
              <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 transition-all duration-300" style={{ width: `${progress}%` }} />
              </div>
              <p className="text-xs text-gray-500 mt-1 text-right">{progress}%</p>
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={!file || state === 'uploading'}
            className={`w-full py-2 rounded-lg text-white text-sm font-semibold transition ${c.btn} disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {state === 'uploading' ? 'Uploading...' : `Import ${source.label} File`}
          </button>
        </>
      )}
    </div>
  )
}

export default function UploadPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Import Emission Data</h1>
        <p className="text-sm text-gray-500 mt-1">Upload files from any of the three data sources. Data is automatically cleaned and normalised before review.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {SOURCES.map(s => <UploadCard key={s.id} source={s} />)}
      </div>
      <div className="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
        <strong>Sample files</strong> are in the repo under <code className="bg-amber-100 px-1 rounded">backend/sample_data/</code> — use those to test the full upload flow.
      </div>
    </div>
  )
}
