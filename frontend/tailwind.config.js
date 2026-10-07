/** Design tokens from the AI Readiness design canvas (university blue + faculty maroon). */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#09090B', 2: '#27272A', 3: '#3F3F46' },
        muted: '#52525B',
        faint: '#71717A',
        line: { DEFAULT: '#E7E7EA', soft: '#F0F0F2' },
        canvas: '#F4F4F6',
        brand: {
          50: '#F6F9FE', 100: '#EEF3FC', 150: '#E3ECF9', 200: '#DCE7F8', 300: '#B9CDEE',
          400: '#9DB8E3', 500: '#7BA3D9', 600: '#5C84C2', 700: '#2F63B8', 800: '#234C91', 900: '#1B3C75',
        },
        navy: { DEFAULT: '#0B1A33', 800: '#0F2140', 700: '#13274A', 600: '#1A2C4D', 500: '#243A63', text: '#A9BBD8', dim: '#7F93B5' },
        maroon: { DEFAULT: '#8E1F3D', soft: '#FBEAEF', 200: '#F6D9E1', light: '#F2A7BC' },
        good: { DEFAULT: '#16A34A', text: '#15803D', soft: '#ECFDF3', bright: '#4ADE80', deep: '#0F2A1D' },
        warn: { DEFAULT: '#D97706', text: '#B45309', soft: '#FEF3C7' },
      },
      fontFamily: {
        sans: ['Geist', 'Anuphan', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 3px rgba(16, 24, 40, 0.04)',
        pop: '0 10px 30px rgba(0, 0, 0, 0.25)',
        seg: '0 1px 2px rgba(16, 24, 40, 0.12)',
      },
      borderRadius: { '4xl': '22px' },
    },
  },
  plugins: [],
}