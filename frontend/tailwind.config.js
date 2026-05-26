/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          950: '#ffffff',
          900: '#f8fafc',
          800: '#f1f5f9',
          700: '#e2e8f0',
          600: '#cbd5e1',
          500: '#94a3b8',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
