/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        dora: {
          navy: '#1a2744',
          blue: '#2c5282',
          sky: '#4a90d9',
          slate: '#334155',
          sand: '#f8f6f3',
          warm: '#faf9f7',
          accent: '#d97706',
          success: '#16a34a',
          danger: '#dc2626',
        },
      },
      fontFamily: {
        display: ['"DM Sans"', 'system-ui', 'sans-serif'],
        body: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
