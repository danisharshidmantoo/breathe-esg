import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import DashboardPage from './pages/DashboardPage'
import { Leaf, Upload, LayoutDashboard } from 'lucide-react'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white border-b border-gray-200 sticky top-0 z-30">
          <div className="max-w-7xl mx-auto px-4 flex items-center h-14 gap-6">
            <div className="flex items-center gap-2 font-bold text-emerald-700 text-lg mr-4">
              <Leaf className="w-5 h-5" /> Breathe ESG
            </div>
            <NavLink to="/" end className={({isActive}) =>
              `flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-md transition ${isActive ? 'bg-emerald-50 text-emerald-700' : 'text-gray-600 hover:bg-gray-100'}`
            }>
              <Upload className="w-4 h-4" /> Upload
            </NavLink>
            <NavLink to="/review" className={({isActive}) =>
              `flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-md transition ${isActive ? 'bg-emerald-50 text-emerald-700' : 'text-gray-600 hover:bg-gray-100'}`
            }>
              <LayoutDashboard className="w-4 h-4" /> Review Dashboard
            </NavLink>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/review" element={<DashboardPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
export default App
