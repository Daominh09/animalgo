/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./src/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  // Must be "class", not Tailwind's default "media". On web, nativewind's runtime
  // waits for the stylesheet, then calls colorScheme.set() unconditionally — and that
  // setter throws when the mode is "media" ("Cannot manually set color scheme, as dark
  // mode is type 'media'"). "class" is also what the error itself tells you to use.
  // No dark: variants exist yet, so this changes no styling today.
  darkMode: "class",
  theme: {
    extend: {},
  },
  plugins: [],
};
