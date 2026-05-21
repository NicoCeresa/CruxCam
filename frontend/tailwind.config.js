/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#0F1E35',
          light:   '#1B2D4F',
          lighter: '#253D62',
        },
        forest: {
          DEFAULT: '#2D5A27',
          light:   '#3D7A37',
        },
        terracotta: {
          DEFAULT: '#C4622D',
          light:   '#D4753F',
          dark:    '#A04E20',
        },
        cream: {
          DEFAULT: '#F0EBE0',
          dark:    '#D4CBBB',
          darker:  '#A89E90',
        },
        brown: {
          DEFAULT: '#6B4226',
          light:   '#8B5A36',
          dark:    '#4A2E18',
        },
      },
      fontFamily: {
        display: ['"Barlow Condensed"', 'sans-serif'],
        body:    ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
