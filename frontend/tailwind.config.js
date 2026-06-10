/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        glow: '0 0 0 1px rgba(255,255,255,0.08), 0 18px 60px rgba(0,0,0,0.45)',
      },
      colors: {
        f1: {
          red: '#e10600',
          black: '#090a0f',
          slate: '#11131a',
        },
      },
    },
  },
  plugins: [],
}