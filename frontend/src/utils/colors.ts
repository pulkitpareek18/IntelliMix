// Color palette for the entire application
export const colors = {
  // Red spectrum
  brightRed: "#f4483a",       // Primary accent or alert color
  slightlyDarkerRed: "#f45444", // Secondary accent or button color
  deepRed: "#d24d34",         // Emphasis or call-to-action color
  reddishOrange: "#d14324",   // Highlight or warning color
  vividRed: "#f13521",        // Attention-grabbing elements
  
  // Yellow spectrum
  vibrantYellow: "#ffb92b",   // Buttons, highlights, or warning
  softYellow: "#f7e5a0",      // Subtle background or hover effects
  paleYellow: "#ffe09c",      // Secondary background or muted accents
  
  // Base colors
  white: "#FFFFFF",           // Pure white for minimal elements
  black: "#000000",           // Black for important elements
  
  // Light theme additions
  lightGray: "#F0F3F5",       // Light gray for subtle backgrounds
  mediumGray: "#9AA0A6",      // Medium gray for less prominent text
  darkGray: "#353535",        // Dark gray for main text on white background
  
  // Additional softer colors
  softRed: "#fee2e1",         // Very light red background
  softerRed: "#fbeae9",       // Even lighter red for larger areas
  softestYellow: "#fff8e8",   // Very light yellow for backgrounds
  textDark: "#444444"         // Softer than pure black for text
};

// Types for better TypeScript support
export type ColorKey = keyof typeof colors;
export type ColorPalette = typeof colors;

export default colors;