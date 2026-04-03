import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "ss-bg": "#0f1117",
        "ss-surface": "#1a1d27",
        "ss-surface-2": "#242736",
        "ss-border": "#2e3347",
        "ss-text": "#e8eaf0",
        "ss-text-muted": "#8892a4",
        "ss-accent": "#4f8ef7",
        "ss-success": "#34c759",
        "ss-warning": "#ff9f0a",
        "ss-error": "#ff453a",
      },
    },
  },
  plugins: [],
} satisfies Config;
