/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#060A12',
          900: '#0B1220',
          850: '#0F182B',
          800: '#142038',
          700: '#1E2F52',
          600: '#2A406C',
        },
        gold: {
          400: '#FDE047',
          500: '#EAB308',
          600: '#CA8A04',
          accent: '#D4AF37',
          glow: 'rgba(212, 175, 55, 0.15)',
        },
      },
    },
  },
  plugins: [],
}
