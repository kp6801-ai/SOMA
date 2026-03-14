import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SOMA — Generative DJ Sessions',
  description: 'Intelligent techno session generation powered by DJ transition science.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  )
}
