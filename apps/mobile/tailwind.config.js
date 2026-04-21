/** @type {import('tailwindcss').Config} */

// Hex palette — mirrors web globals.css OKLCH values.
// Keep in sync with packages/ui-tokens/src/index.ts COLORS.
const colors = {
  surface0:  "#10121c",
  surface1:  "#161925",
  surface2:  "#1c1f2e",
  surface3:  "#23263a",
  foreground: "#f4f3ee",
  quiet:      "#b4b2a5",
  faint:      "#8a897d",
  primary:    "#cfb041",
  primaryFg:  "#181610",
  accent:     "#64c4b9",
  accentFg:   "#10181a",
  border:     "#2d3045",
  borderSoft: "#1e2030",
  // Signal
  emerald:   "#51c96a",
  amber:     "#f5c543",
  crimson:   "#e8503e",
  // Conviction
  diamond:   "#a5f3fc",
  platinum:  "#e9d5ff",
  gold:      "#fde68a",
  silver:    "#e2e8f0",
  bronze:    "#fed7aa",
  unranked:  "#94a3b8",
};

// Radius scale (px) — mirrors web --radius CSS variable scale
const borderRadius = {
  sm:   "10px",
  md:   "13px",
  lg:   "16px",
  xl:   "22px",
  "2xl": "29px",
  "3xl": "36px",
  full:  "9999px",
};

module.exports = {
  content: [
    "./app/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
    "./lib/**/*.{js,jsx,ts,tsx}",
  ],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors,
      borderRadius,
      fontFamily: {
        sans:    ["System"],
        heading: ["System"],
        mono:    ["Courier"],
      },
    },
  },
  plugins: [],
};
