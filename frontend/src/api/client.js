import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })
export default api

export const uploadFile = (source, file, onProgress) => {
  const fd = new FormData()
  fd.append('source', source)
  fd.append('file', file)
  return api.post('/upload/', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: e => onProgress && onProgress(Math.round(e.loaded * 100 / e.total))
  })
}

export const getRecords = (params) => api.get('/records/', { params })
export const getStats = () => api.get('/stats/')
export const approveRecord = (id, note) => api.post(`/records/${id}/approve/`, { note })
export const rejectRecord = (id, note) => api.post(`/records/${id}/reject/`, { note })
export const bulkApprove = (ids) => api.post('/records/bulk_approve/', { ids })
export const patchRecord = (id, data) => api.patch(`/records/${id}/`, data)
