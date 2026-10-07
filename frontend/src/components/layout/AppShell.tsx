import { Outlet } from 'react-router-dom'
import { USE_MOCK } from '../../lib/api'
import { Sidebar } from './Sidebar'
import { TabBar } from './TabBar'

export function AppShell() {
  return (
    <div className="min-h-screen bg-canvas lg:flex lg:items-start lg:gap-2 lg:p-2">
      <Sidebar className="sticky top-2 hidden h-[calc(100vh-16px)] lg:flex" />
      <main className="min-w-0 flex-1 pb-28 lg:min-h-[calc(100vh-16px)] lg:rounded-2xl lg:border lg:border-line lg:bg-white lg:pb-0 lg:shadow-card">
        {USE_MOCK && (
          <div className="bg-maroon-soft px-4 py-2 text-center text-xs font-medium text-maroon lg:rounded-t-2xl">
            โหมดข้อมูลตัวอย่าง (mock) · ยังไม่ได้เชื่อมต่อ Backend
          </div>
        )}
        <Outlet />
      </main>
      <TabBar className="lg:hidden" />
    </div>
  )
}
