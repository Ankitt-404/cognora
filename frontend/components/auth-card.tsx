'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { useRouter } from 'next/navigation'
import { API, TOKEN_KEY, responseMessage } from '@/app/api'
type AuthCardProps = {
  mode: 'login' | 'register'
}

function Mark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none">
      <path d="M7.5 7.5A6.36 6.36 0 0 1 12 5.64c3.51 0 6.36 2.85 6.36 6.36S15.51 18.36 12 18.36 5.64 15.51 5.64 12" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M5 5v5h5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function AuthCard({ mode }: AuthCardProps) {
   const router = useRouter()
  const [errorMessage, setErrorMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const isLogin = mode === 'login'

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isSubmitting) return
    const formData = new FormData(event.currentTarget)
    const email = String(formData.get('email') ?? '').trim()
    const password = String(formData.get('password') ?? '')
    const confirmPassword = String(formData.get('confirmPassword') ?? '')

    

    setIsSubmitting(true)
    setErrorMessage('')
    try {
      const response = await fetch(`${API}/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const result: unknown = await response.json()
      if (!response.ok) throw new Error(responseMessage(result, 'Something went wrong.'))
      if (!result || typeof result !== 'object' || !('token' in result) || typeof result.token !== 'string') {
        throw new Error('The server returned an invalid response.')
      }
      sessionStorage.setItem(TOKEN_KEY, result.token)
      router.replace('/')
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Could not reach the server.')
    } finally {
      setIsSubmitting(false)
    }
  
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#0b0c0c] text-[#f3f4ef] selection:bg-lime-300 selection:text-neutral-950">
      <div className="pointer-events-none absolute left-1/2 top-[-18rem] size-[42rem] -translate-x-1/2 rounded-full bg-[#c9f27b]/[0.06] blur-3xl" />
      <div className="relative mx-auto flex min-h-screen w-full max-w-[1440px] flex-col px-5 sm:px-8 lg:px-12">
        <header className="flex h-20 items-center justify-between border-b border-white/10">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-full bg-[#c9f27b] text-[#10120d]"><Mark /></span>
            <span className="text-[17px] font-medium tracking-[-0.03em]">cognora</span>
          </Link>
          <Link href="/" className="text-xs text-white/40 transition hover:text-white">Back to workspace</Link>
        </header>

        <section className="flex flex-1 items-center justify-center py-12">
          <div className="w-full max-w-md">
            <div className="mb-8 text-center">
              <div className="mx-auto mb-5 grid size-11 place-items-center rounded-2xl border border-[#c9f27b]/20 bg-[#c9f27b]/10 text-[#c9f27b]">
                <Mark />
              </div>
              <h1 className="text-3xl font-medium tracking-[-0.04em]">
                {isLogin ? 'Welcome back' : 'Create your account'}
              </h1>
              <p className="mt-2 text-sm text-white/40">
                {isLogin ? 'Sign in to continue to your documents.' : 'Start asking better questions of your PDFs.'}
              </p>
            </div>

            <div className="rounded-[28px] border border-white/10 bg-[#121414] p-2 shadow-2xl shadow-black/40">
              <div className="rounded-[22px] border border-white/[0.06] bg-[#171919] p-6 sm:p-8">
                <form onSubmit={handleSubmit} className="space-y-5">
                  {!isLogin && (
                    <label className="block">
                      <span className="mb-2 block text-xs font-medium text-white/55">Full name</span>
                      <input
                        name="name"
                        type="text"
                        autoComplete="name"
                        required
                        placeholder="Your name"
                        className="h-12 w-full rounded-xl border border-white/10 bg-[#0e1010] px-4 text-sm text-white outline-none transition placeholder:text-white/20 focus:border-[#c9f27b]/50 focus:ring-2 focus:ring-[#c9f27b]/10"
                      />
                    </label>
                  )}

                  <label className="block">
                    <span className="mb-2 block text-xs font-medium text-white/55">Email address</span>
                    <input
                      name="email"
                      type="email"
                      autoComplete="email"
                      required
                      placeholder="you@example.com"
                      className="h-12 w-full rounded-xl border border-white/10 bg-[#0e1010] px-4 text-sm text-white outline-none transition placeholder:text-white/20 focus:border-[#c9f27b]/50 focus:ring-2 focus:ring-[#c9f27b]/10"
                    />
                  </label>

                  <label className="block">
                    
                    <input
                      name="password"
                      type="password"
                      autoComplete={isLogin ? 'current-password' : 'new-password'}
                      required
                      minLength={10}
                      placeholder="At least 10 characters"
                      className="h-12 w-full rounded-xl border border-white/10 bg-[#0e1010] px-4 text-sm text-white outline-none transition placeholder:text-white/20 focus:border-[#c9f27b]/50 focus:ring-2 focus:ring-[#c9f27b]/10"
                    />
                  </label>

                  {!isLogin && (
                    <label className="block">
                      <span className="mb-2 block text-xs font-medium text-white/55">Confirm password</span>
                      <input
                        name="confirmPassword"
                        type="password"
                        autoComplete="new-password"
                        required
                        minLength={10}
                        placeholder="Repeat your password"
                        className="h-12 w-full rounded-xl border border-white/10 bg-[#0e1010] px-4 text-sm text-white outline-none transition placeholder:text-white/20 focus:border-[#c9f27b]/50 focus:ring-2 focus:ring-[#c9f27b]/10"
                      />
                    </label>
                  )}

                  <button
                  disabled={isSubmitting}
                    type="submit"
                    className="flex h-12 w-full items-center justify-center rounded-xl bg-[#c9f27b] text-sm font-semibold text-[#10120d] transition hover:bg-[#d5ff87] focus:outline-none focus:ring-2 focus:ring-[#c9f27b]/40 focus:ring-offset-2 focus:ring-offset-[#171919]"
                  >
                    {isSubmitting ? 'Please wait…' : isLogin ? 'Sign in' : 'Create account'}
                  </button>
                </form>

               {errorMessage && (
                <p role="alert" className="mt-4 rounded-xl border border-red-400/20 bg-red-400/[0.05] px-4 py-3 text-center text-xs leading-5 text-red-300">
                {errorMessage}
                </p>
)}

                <p className="mt-6 text-center text-xs text-white/35">
                  {isLogin ? 'New to cognora?' : 'Already have an account?'}{' '}
                  <Link href={isLogin ? '/register' : '/login'} className="font-medium text-white transition hover:text-[#c9f27b]">
                    {isLogin ? 'Create an account' : 'Sign in'}
                  </Link>
                </p>
              </div>
            </div>

            <p className="mt-6 text-center text-[11px] leading-5 text-white/20">
              By continuing, you agree to Cognora&apos;s Terms and Privacy Policy.
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}