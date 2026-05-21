/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#2B3F5E',
          light:   '#354D72',
          lighter: '#405D85',
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
