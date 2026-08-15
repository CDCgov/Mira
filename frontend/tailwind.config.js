/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Nunito Sans'", "system-ui", "-apple-system", "sans-serif"],
        heading: ["'Roboto'", "system-ui", "-apple-system", "sans-serif"],
        mono: ["'Roboto Mono'", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(var(--info-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },

        // ── CDC brand palettes ──────────────────────────────────────────
        // Every non-neutral Tailwind color family used in the app is remapped
        // to an official CDC swatch scale so the UI can only render CDC colors.
        // Blue (also: sky, indigo) — CDC Blue
        blue:    { 50: "#ECF5FF", 100: "#DBE8F7", 200: "#B8D4ED", 300: "#87B5E3", 400: "#5796D9", 500: "#3382CF", 600: "#0057B7", 700: "#0057B7", 800: "#032659", 900: "#032659", 950: "#032659" },
        sky:     { 50: "#ECF5FF", 100: "#DBE8F7", 200: "#B8D4ED", 300: "#87B5E3", 400: "#5796D9", 500: "#3382CF", 600: "#0057B7", 700: "#0057B7", 800: "#032659", 900: "#032659", 950: "#032659" },
        indigo:  { 50: "#ECF5FF", 100: "#DBE8F7", 200: "#B8D4ED", 300: "#87B5E3", 400: "#5796D9", 500: "#3382CF", 600: "#0057B7", 700: "#0057B7", 800: "#032659", 900: "#032659", 950: "#032659" },
        // Teal (also: cyan) — CDC Teal
        teal:    { 50: "#F4FCFC", 100: "#EAF8F9", 200: "#D5F7F9", 300: "#AEECF2", 400: "#7DDEEC", 500: "#00B1CE", 600: "#0081A1", 700: "#0081A1", 800: "#125261", 900: "#125261", 950: "#125261" },
        cyan:    { 50: "#F4FCFC", 100: "#EAF8F9", 200: "#D5F7F9", 300: "#AEECF2", 400: "#7DDEEC", 500: "#00B1CE", 600: "#0081A1", 700: "#0081A1", 800: "#125261", 900: "#125261", 950: "#125261" },
        // Green (also: emerald, lime) — complementary green tuned to the CDC palette
        green:   { 50: "#ECF7F0", 100: "#D6EDDD", 200: "#AEDCC0", 300: "#7FC79E", 400: "#4EAE79", 500: "#2E8B57", 600: "#1F7A47", 700: "#196138", 800: "#14492B", 900: "#0F3A22", 950: "#0A2717" },
        emerald: { 50: "#ECF7F0", 100: "#D6EDDD", 200: "#AEDCC0", 300: "#7FC79E", 400: "#4EAE79", 500: "#2E8B57", 600: "#1F7A47", 700: "#196138", 800: "#14492B", 900: "#0F3A22", 950: "#0A2717" },
        lime:    { 50: "#ECF7F0", 100: "#D6EDDD", 200: "#AEDCC0", 300: "#7FC79E", 400: "#4EAE79", 500: "#2E8B57", 600: "#1F7A47", 700: "#196138", 800: "#14492B", 900: "#0F3A22", 950: "#0A2717" },
        // Purple (also: violet, fuchsia) — CDC Purple
        purple:  { 50: "#FAF7FB", 100: "#F5EBF5", 200: "#E8D6EB", 300: "#D1ADD4", 400: "#B278B2", 500: "#8F4A8F", 600: "#722161", 700: "#722161", 800: "#47264F", 900: "#47264F", 950: "#47264F" },
        violet:  { 50: "#FAF7FB", 100: "#F5EBF5", 200: "#E8D6EB", 300: "#D1ADD4", 400: "#B278B2", 500: "#8F4A8F", 600: "#722161", 700: "#722161", 800: "#47264F", 900: "#47264F", 950: "#47264F" },
        fuchsia: { 50: "#FAF7FB", 100: "#F5EBF5", 200: "#E8D6EB", 300: "#D1ADD4", 400: "#B278B2", 500: "#8F4A8F", 600: "#722161", 700: "#722161", 800: "#47264F", 900: "#47264F", 950: "#47264F" },
        // Yellow (also: amber) — CDC Yellow
        yellow:  { 50: "#FDF7EB", 100: "#FCEBC9", 200: "#FCDBA6", 300: "#FCCF85", 400: "#FABF61", 500: "#FFB24D", 600: "#DE8A05", 700: "#DE8A05", 800: "#975722", 900: "#975722", 950: "#975722" },
        amber:   { 50: "#FDF7EB", 100: "#FCEBC9", 200: "#FCDBA6", 300: "#FCCF85", 400: "#FABF61", 500: "#FFB24D", 600: "#DE8A05", 700: "#DE8A05", 800: "#975722", 900: "#975722", 950: "#975722" },
        // Orange — CDC Orange
        orange:  { 50: "#FEF7F3", 100: "#FFEBE0", 200: "#FFD9C4", 300: "#FCBF9C", 400: "#FF9C63", 500: "#FB7E38", 600: "#DB5E2E", 700: "#DB5E2E", 800: "#944521", 900: "#944521", 950: "#944521" },
        // Red (also: rose) — CDC Red
        red:     { 50: "#FCF2F1", 100: "#FCDEDB", 200: "#FCBDB5", 300: "#F5968F", 400: "#F0695E", 500: "#CC1B22", 600: "#CC1B22", 700: "#961C1C", 800: "#961C1C", 900: "#660F14", 950: "#660F14" },
        rose:    { 50: "#FCF2F1", 100: "#FCDEDB", 200: "#FCBDB5", 300: "#F5968F", 400: "#F0695E", 500: "#CC1B22", 600: "#CC1B22", 700: "#961C1C", 800: "#961C1C", 900: "#660F14", 950: "#660F14" },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
}

