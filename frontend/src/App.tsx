import { lazy, Suspense, type ReactNode } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { Skeleton } from './components/ui/States'
import { useAuth } from './lib/auth'
import Dashboard from './pages/Dashboard'

const Search = lazy(() => import('./pages/Search'))
const JobDetail = lazy(() => import('./pages/JobDetail'))
const Gap = lazy(() => import('./pages/Gap'))
const Login = lazy(() => import('./pages/admin/Login'))
const Crawler = lazy(() => import('./pages/admin/Crawler'))
const Courses = lazy(() => import('./pages/admin/Courses'))

function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAdmin } = useAuth()
  const location = useLocation()
  return isAdmin ? <>{children}</> : <Navigate to="/admin/login" replace state={{ from: location.pathname }} />
}

function NotFound() {
  return (
    <div className="flex flex-col items-start gap-3 p-8">
      <h1 className="text-2xl font-semibold">ไม่พบหน้านี้</h1>
      <Link to="/" className="text-brand-800 underline">กลับไปหน้าภาพรวม</Link>
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<div className="p-8"><Skeleton className="h-64" /></div>}>
      <Routes>
        <Route path="/admin/login" element={<Login />} />
        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="search" element={<Search />} />
          <Route path="jobs/:id" element={<JobDetail />} />
          <Route path="gap" element={<Gap />} />
          <Route path="admin" element={<Navigate to="/admin/crawler" replace />} />
          <Route path="admin/crawler" element={<RequireAdmin><Crawler /></RequireAdmin>} />
          <Route path="admin/courses" element={<RequireAdmin><Courses /></RequireAdmin>} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
