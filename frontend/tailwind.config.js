/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0b1220",
        panel: "#111a2e",
        edge: "#1e2a44",
        muted: "#8597b5",
        accent: "#5b9dff",
        good: "#3fb27f",
        warn: "#e0b341",
        bad: "#e5616a",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
