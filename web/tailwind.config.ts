import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0a0a0a",
        surface: "#141414",
        card: "#1a1a1a",
        border: "#262626",
        "border-subtle": "#333",
        muted: "#737373",
        "muted-light": "#a3a3a3",
      },
    },
  },
  plugins: [],
} satisfies Config;
