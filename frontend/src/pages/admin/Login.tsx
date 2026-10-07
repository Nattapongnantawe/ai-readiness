import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { LogoMark, Wordmark } from '../../components/Logo'
import { USE_MOCK, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'

/** Reached only by typing /admin/login — the public UI has no sign-in button. */
export default function Login() {
  const { isAdmin, signIn } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/admin/crawler'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const login = useMutation({
    mutationFn: () => api.login(username, password),
    onSuccess: (t) => { signIn({ token: t.access_token, expires_at: t.expires_at }); navigate(from, { replace: true }) },
  })
  if (isAdmin) return <Navigate to={from} replace />

  const submit = (e: FormEvent) => { e.preventDefault(); login.mutate() }
  return (
    <div className="flex min-h-screen items-center justify-center bg-navy p-4">
      <form onSubmit={submit} className="flex w-full max-w-sm flex-col gap-5 rounded-[22px] bg-white p-7">
        <div className="flex items-center gap-2.5"><LogoMark size={36} /><div className="flex flex-col"><Wordmark /><span className="text-xs text-muted">วิศวกรรมคอมพิวเตอร์ · ม.กาฬสินธุ์</span></div></div>
        <div><h1 className="text-xl font-semibold tracking-[-0.02em]">เข้าสู่ระบบผู้ดูแล</h1><p className="text-sm text-muted">สำหรับตั้งรอบการดึงข้อมูลและจัดการรายวิชา</p></div>
        <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-3">ชื่อผู้ใช้
          <input className="input h-11" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-3">รหัสผ่าน
          <input className="input h-11" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {login.isError && <p role="alert" className="text-sm text-maroon">{login.error instanceof Error ? login.error.message : 'เข้าสู่ระบบไม่สำเร็จ'}</p>}
        {USE_MOCK && <p className="text-xs text-muted">โหมด mock: ใส่ชื่อผู้ใช้และรหัสผ่านอะไรก็ได้</p>}
        <button type="submit" className="btn-primary h-11" disabled={login.isPending}>{login.isPending ? 'กำลังเข้าสู่ระบบ…' : 'เข้าสู่ระบบ'}</button>
      </form>
    </div>
  )
}
