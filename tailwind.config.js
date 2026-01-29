/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'color-dark': '#5E6B4E',
        'color-light': '#F6F5F1',
        'color-accent': '#C2441C',
        'color-accent-2': '#7A8B6C',
        'color-footer': '#3F4A38',
        'text-on-dark': '#F3F2EE',
        'text-on-light': '#2A2E26',
        'subtext-on-dark': 'rgba(243,242,238,0.75)',
        'subtext-on-light': 'rgba(42,46,38,0.7)',
        'border-on-dark': 'rgba(243,242,238,0.12)',
        'border-on-light': 'rgba(0,0,0,0.08)',
        'accent-hover': '#A83A18',
      },
      fontFamily: {
        heading: ['Manrope', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      spacing: {
        '120': '120px',
        '72': '72px',
      },
    },
  },
  plugins: [],
};
