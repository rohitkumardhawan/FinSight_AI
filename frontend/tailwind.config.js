/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)', 'Plus Jakarta Sans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'monospace'],
      },
      colors: {
        obsidian: {
          bg: '#090B0F',
          surface: '#11141B',
          hover: '#161A23',
          border: 'rgba(255, 255, 255, 0.07)',
          borderHover: 'rgba(255, 255, 255, 0.14)',
        },
        navy: {
          950: '#090B0F',
          900: '#11141B',
          850: '#161A23',
          800: 'rgba(255, 255, 255, 0.08)',
          750: 'rgba(255, 255, 255, 0.12)',
          700: 'rgba(255, 255, 255, 0.16)',
          600: 'rgba(255, 255, 255, 0.22)',
        },
        gold: {
          400: '#FDE047',
          500: '#EAB308',
          600: '#CA8A04',
          accent: '#D4AF37',
          glow: 'rgba(212, 175, 55, 0.15)',
        },
        cobalt: {
          DEFAULT: '#38BDF8',
          500: '#3B82F6',
          400: '#38BDF8',
          glow: 'rgba(56, 189, 248, 0.15)',
        },
      },
    },
  },
  plugins: [],
}
