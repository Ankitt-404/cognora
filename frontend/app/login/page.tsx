import type { Metadata } from 'next'
import AuthCard from '@/components/auth-card'

export const metadata: Metadata = {
  title: 'Sign in — cognora',
}

export default function LoginPage() {
  return <AuthCard mode="login" />
}
