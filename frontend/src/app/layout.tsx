import type { Metadata } from 'next';
import { Plus_Jakarta_Sans, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const sansFont = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

const monoFont = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

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
    <html lang="en" className={`dark ${sansFont.variable} ${monoFont.variable}`}>
      <body className="bg-[#090B0F] text-slate-100 min-h-screen antialiased selection:bg-sky-500/20 selection:text-sky-300 font-sans">
        {children}
      </body>
    </html>
  );
}
