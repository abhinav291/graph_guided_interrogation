import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        void: "#050505",
        canvas: "#0a0a0a",
        panel: "#111111",
        surface: "#161616",
        elevated: "#1c1c1c",
        border: "#2a2418",
        "border-gold": "#3d3420",
        gold: {
          DEFAULT: "#c9a227",
          light: "#e8c547",
          dim: "#8b7355",
          muted: "#6b5c3e",
          glow: "#d4af37",
        },
        cream: "#f5f0e6",
        parchment: "#c4b896",
        success: "#2d6a4f",
        "success-gold": "#4ade80",
      },
      boxShadow: {
        gold: "0 0 20px rgba(201, 162, 39, 0.15)",
        "gold-lg": "0 0 40px rgba(201, 162, 39, 0.2)",
        panel: "0 4px 24px rgba(0, 0, 0, 0.6)",
      },
      backgroundImage: {
        "gold-gradient": "linear-gradient(135deg, #c9a227 0%, #e8c547 50%, #b8860b 100%)",
        "dark-radial":
          "radial-gradient(ellipse at 50% 0%, rgba(201, 162, 39, 0.06) 0%, transparent 60%)",
      },
      fontFamily: {
        display: ["Georgia", "Cambria", "Times New Roman", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
