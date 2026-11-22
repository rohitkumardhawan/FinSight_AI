import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'FinSight AI — AI-Powered Equity Research & Financial Intelligence',
  description: 'Premium institutional equity research, financial intelligence, and DCF valuation platform.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-navy-950 text-slate-100 min-h-screen antialiased selection:bg-gold-500/20 selection:text-gold-400">
        {children}
      </body>
    </html>
  );
}
