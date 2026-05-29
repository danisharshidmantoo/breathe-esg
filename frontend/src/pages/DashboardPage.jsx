import { useState, useEffect, useCallback } from 'react'
import { getRecords, getStats, approveRecord, rejectRecord, bulkApprove } from '../api/client'
import {
  useReactTable, getCoreRowModel, flexRender,
  getSortedRowModel, getFilteredRowModel,
} from '@tanstack/react-table'
import { CheckCircle, XCircle, ChevronUp, ChevronDown, RefreshCw, Filter } from 'lucide-react'

const SCOPE_BADGE = {
  scope1: 'bg-red-100 text-red-700',
  scope2: 'bg-amber-100 text-amber-700',
  scope3: 'bg-purple-100 text-purple-700',
}
const SOURCE_BADGE = {
  sap: 'bg-blue-100 text-blue-700',
  utility: 'bg-emerald-100 text-emerald-700',
  travel: 'bg-orange-100 text-orange-700',
}
const STATUS_BADGE = {
  pending: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
}

function StatCard({ label, value, sub, color }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color || 'text-gray-900'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  )
}

function NoteModal({ record, action, onConfirm, onClose }) {
  const [note, setNote] = useState('')
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
        <h3 className="font-bold text-lg mb-1">{action === 'approve' ? '✓ Approve' : '✗ Reject'} Record</h3>
        <p className="text-sm text-gray-500 mb-4">{record?.description}</p>
        <textarea
          className="w-full border border-gray-200 rounded-lg p-3 text-sm resize-none h-24 focus:outline-none focus:ring-2 focus:ring-emerald-400"
          placeholder="Optional analyst note..."
          value={note}
          onChange={e => setNote(e.target.value)}
        />
        <div className="flex gap-3 mt-4 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
          <button
            onClick={() => onConfirm(note)}
            className={`px-4 py-2 text-sm text-white rounded-lg font-semibold ${action === 'approve' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-red-500 hover:bg-red-600'}`}
          >
            {action === 'approve' ? 'Approve' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [records, setRecords] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ source: '', status: 'pending', scope: '', search: '' })
  const [selected, setSelected] = useState(new Set())
  const [modal, setModal] = useState(null) // { record, action }
  const [sorting, setSorting] = useState([])

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [recs, st] = await Promise.all([
        getRecords({ ...filters }),
        getStats()
      ])
      setRecords(recs.data.results || recs.data)
      setStats(st.data)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { fetchData() }, [fetchData])

  const handleApprove = (record) => setModal({ record, action: 'approve' })
  const handleReject = (record) => setModal({ record, action: 'reject' })

  const confirmModal = async (note) => {
    const { record, action } = modal
    if (action === 'approve') await approveRecord(record.id, note)
    else await rejectRecord(record.id, note)
    setModal(null)
    fetchData()
  }

  const handleBulkApprove = async () => {
    await bulkApprove([...selected])
    setSelected(new Set())
    fetchData()
  }

  const toggleSelect = (id) => {
    setSelected(prev => {
      const s = new Set(prev)
      s.has(id) ? s.delete(id) : s.add(id)
      return s
    })
  }

  const columns = [
    {
      id: 'select',
      header: () => null,
      cell: ({ row }) => (
        <input type="checkbox" className="rounded" checked={selected.has(row.original.id)}
          onChange={() => toggleSelect(row.original.id)} />
      ),
      size: 40,
    },
    { accessorKey: 'source', header: 'Source',
      cell: ({ getValue }) => <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SOURCE_BADGE[getValue()] || ''}`}>{getValue()?.toUpperCase()}</span> },
    { accessorKey: 'scope', header: 'Scope',
      cell: ({ getValue }) => <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SCOPE_BADGE[getValue()] || ''}`}>{getValue()}</span> },
    { accessorKey: 'activity_date', header: 'Date', size: 100 },
    { accessorKey: 'vendor_or_provider', header: 'Vendor / Provider',
      cell: ({ getValue }) => <span className="text-sm text-gray-700 font-medium">{getValue() || '—'}</span> },
    { accessorKey: 'description', header: 'Description',
      cell: ({ getValue }) => <span className="text-xs text-gray-500 truncate max-w-xs block">{getValue()}</span> },
    { accessorKey: 'quantity', header: 'Qty',
      cell: ({ row }) => row.original.quantity ? `${Number(row.original.quantity).toLocaleString()} ${row.original.unit}` : '—' },
    { accessorKey: 'co2e_kg', header: 'CO₂e (kg)',
      cell: ({ getValue }) => getValue() != null ? <span className="font-mono text-sm">{Number(getValue()).toLocaleString(undefined, {maximumFractionDigits:1})}</span> : '—' },
    { accessorKey: 'status', header: 'Status',
      cell: ({ getValue }) => <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_BADGE[getValue()] || ''}`}>{getValue()}</span> },
    {
      id: 'actions', header: 'Actions',
      cell: ({ row }) => row.original.status === 'pending' ? (
        <div className="flex gap-2">
          <button onClick={() => handleApprove(row.original)}
            className="p-1 rounded hover:bg-green-50 text-green-600 transition" title="Approve">
            <CheckCircle className="w-5 h-5" />
          </button>
          <button onClick={() => handleReject(row.original)}
            className="p-1 rounded hover:bg-red-50 text-red-500 transition" title="Reject">
            <XCircle className="w-5 h-5" />
          </button>
        </div>
      ) : <span className="text-xs text-gray-400">{row.original.reviewed_at ? '✓ reviewed' : ''}</span>,
    },
  ]

  const table = useReactTable({
    data: records,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  })

  return (
    <div>
      {modal && <NoteModal {...modal} onConfirm={confirmModal} onClose={() => setModal(null)} />}

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <StatCard label="Total Records" value={stats.total_records} />
          <StatCard label="Pending" value={stats.pending} color="text-yellow-600" />
          <StatCard label="Approved" value={stats.approved} color="text-emerald-600" />
          <StatCard label="Rejected" value={stats.rejected} color="text-red-500" />
          <StatCard label="Approved CO₂e" value={`${(stats.total_co2e_kg/1000).toFixed(2)} t`} sub="tonnes CO₂e" color="text-emerald-700" />
        </div>
      )}

      {/* Scope breakdown */}
      {stats && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          {['scope1','scope2','scope3'].map(s => (
            <div key={s} className="bg-white rounded-lg border border-gray-100 p-3 shadow-sm">
              <p className="text-xs text-gray-400 font-medium uppercase">{s}</p>
              <p className="text-lg font-bold text-gray-800 mt-0.5">
                {(stats.by_scope[s]/1000).toFixed(2)} <span className="text-xs font-normal text-gray-500">t CO₂e</span>
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4 flex flex-wrap gap-3 items-center shadow-sm">
        <Filter className="w-4 h-4 text-gray-400" />
        <input
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-emerald-400"
          placeholder="Search vendor / description..."
          value={filters.search}
          onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
        />
        {['source','status','scope'].map(key => (
          <select key={key}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm capitalize focus:outline-none focus:ring-2 focus:ring-emerald-400"
            value={filters[key]}
            onChange={e => setFilters(f => ({ ...f, [key]: e.target.value }))}
          >
            <option value="">All {key}s</option>
            {key === 'source' && ['sap','utility','travel'].map(o => <option key={o} value={o}>{o.toUpperCase()}</option>)}
            {key === 'status' && ['pending','approved','rejected'].map(o => <option key={o} value={o}>{o}</option>)}
            {key === 'scope' && ['scope1','scope2','scope3'].map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        ))}
        <button onClick={fetchData} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition" title="Refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
        {selected.size > 0 && (
          <button onClick={handleBulkApprove}
            className="ml-auto px-3 py-1.5 bg-emerald-600 text-white text-sm font-semibold rounded-lg hover:bg-emerald-700 transition">
            Approve {selected.size} selected
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              {table.getHeaderGroups().map(hg => (
                <tr key={hg.id}>
                  {hg.headers.map(h => (
                    <th key={h.id}
                      className="px-3 py-2.5 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide cursor-pointer select-none"
                      onClick={h.column.getToggleSortingHandler()}
                    >
                      <div className="flex items-center gap-1">
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {h.column.getIsSorted() === 'asc' && <ChevronUp className="w-3 h-3" />}
                        {h.column.getIsSorted() === 'desc' && <ChevronDown className="w-3 h-3" />}
                      </div>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr><td colSpan={columns.length} className="text-center py-12 text-gray-400">Loading...</td></tr>
              ) : table.getRowModel().rows.length === 0 ? (
                <tr><td colSpan={columns.length} className="text-center py-12 text-gray-400">No records found. Try adjusting filters or upload a file.</td></tr>
              ) : (
                table.getRowModel().rows.map(row => (
                  <tr key={row.id} className={`hover:bg-gray-50 transition ${selected.has(row.original.id) ? 'bg-emerald-50' : ''}`}>
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id} className="px-3 py-2.5">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {records.length > 0 && (
          <div className="px-4 py-2 border-t border-gray-100 text-xs text-gray-400">
            {records.length} records shown
          </div>
        )}
      </div>
    </div>
  )
}
