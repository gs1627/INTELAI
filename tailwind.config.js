/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './frontend/src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#0d1323', surface: '#0d1323', 'surface-container-lowest': '#080e1e',
        'surface-container-low': '#151b2c', 'surface-container': '#191f30',
        'surface-container-high': '#24293b', 'surface-container-highest': '#2f3446',
        primary: '#a2c9ff', 'primary-container': '#0071c5', secondary: '#d3fbff',
        tertiary: '#67d3ff', 'on-surface': '#dde2f9', 'on-surface-variant': '#c0c7d3',
        'outline-variant': '#414752',
      },
      fontFamily: {
        display: ['Space Grotesk', 'sans-serif'], body: ['Inter', 'sans-serif'],
        telemetry: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: { DEFAULT: '0.125rem', lg: '0.25rem', xl: '0.5rem', full: '0.75rem' },
    },
  },
  plugins: [],
};
