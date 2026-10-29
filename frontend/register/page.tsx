import type { Metadata } from 'next'
import AuthCard from '@/components/auth-card'

export const metadata: Metadata = {
  title: 'Create account — cognora',
}

export default function RegisterPage() {
  return <AuthCard mode="register" />
}