/** Les couleurs viennent de variables CSS (src/index.css) : un seul endroit pour changer l'identité visuelle. */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)', surface: 'var(--surface)', ink: 'var(--ink)', muted: 'var(--muted)',
        line: 'var(--line)', soft: 'var(--line-soft)',
        brand: 'var(--brand)', 'brand-soft': 'var(--brand-soft)', 'brand-deep': 'var(--brand-deep)',
        ok: 'var(--ok)', 'ok-soft': 'var(--ok-soft)', warn: 'var(--warn)', 'warn-soft': 'var(--warn-soft)',
        bad: 'var(--bad)', 'bad-soft': 'var(--bad-soft)',
      },
      fontFamily: {
        sans: ['"Segoe UI Variable Text"', '"Segoe UI"', 'system-ui', '-apple-system', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', '"Cascadia Mono"', '"SF Mono"', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
