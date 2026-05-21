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
      backgroundImage: {
        // Subtle topographic contour pattern using SVG
        'topo': "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cpath d='M0 80 Q50 60 100 80 Q150 100 200 80' stroke='%231B2D4F' stroke-width='1' fill='none'/%3E%3Cpath d='M0 120 Q50 100 100 120 Q150 140 200 120' stroke='%231B2D4F' stroke-width='1' fill='none'/%3E%3Cpath d='M0 160 Q50 140 100 160 Q150 180 200 160' stroke='%231B2D4F' stroke-width='1' fill='none'/%3E%3Cpath d='M0 40 Q50 20 100 40 Q150 60 200 40' stroke='%231B2D4F' stroke-width='1' fill='none'/%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [],
}
