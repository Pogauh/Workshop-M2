/** Console sombre « signes vitaux » : les couleurs vivent dans src/index.css (variables), jamais en dur dans les composants. */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)', panel: 'var(--panel)', raise: 'var(--raise)', line: 'var(--line)', ink: 'var(--ink)', muted: 'var(--muted)',
        series: 'var(--series)', ok: 'var(--ok)', warn: 'var(--warn)', serious: 'var(--serious)', crit: 'var(--crit)', info: 'var(--info)',
      },
      fontFamily: {
        sans: ['"Segoe UI Variable Text"', '"Segoe UI"', 'system-ui', '-apple-system', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', '"Cascadia Mono"', '"SF Mono"', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
