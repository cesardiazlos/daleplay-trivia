---
name: Sonic Pulse
colors:
  surface: '#1c0a2c'
  surface-dim: '#1c0a2c'
  surface-bright: '#443155'
  surface-container-lowest: '#170527'
  surface-container-low: '#251335'
  surface-container: '#291739'
  surface-container-high: '#342244'
  surface-container-highest: '#402d50'
  on-surface: '#f1daff'
  on-surface-variant: '#dcbed4'
  inverse-surface: '#f1daff'
  inverse-on-surface: '#3b284b'
  outline: '#a4899d'
  outline-variant: '#564052'
  surface-tint: '#ffabf3'
  primary: '#ffabf3'
  on-primary: '#5b005b'
  primary-container: '#ff00ff'
  on-primary-container: '#510051'
  inverse-primary: '#a900a9'
  secondary: '#bdf4ff'
  on-secondary: '#00363d'
  secondary-container: '#00e3fd'
  on-secondary-container: '#00616d'
  tertiary: '#d1bcff'
  on-tertiary: '#3c0090'
  tertiary-container: '#a179ff'
  on-tertiary-container: '#350081'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffd7f5'
  primary-fixed-dim: '#ffabf3'
  on-primary-fixed: '#380038'
  on-primary-fixed-variant: '#810081'
  secondary-fixed: '#9cf0ff'
  secondary-fixed-dim: '#00daf3'
  on-secondary-fixed: '#001f24'
  on-secondary-fixed-variant: '#004f58'
  tertiary-fixed: '#e9ddff'
  tertiary-fixed-dim: '#d1bcff'
  on-tertiary-fixed: '#23005b'
  on-tertiary-fixed-variant: '#5700c9'
  background: '#1c0a2c'
  on-background: '#f1daff'
  surface-variant: '#402d50'
typography:
  display-xl:
    fontFamily: Spline Sans
    fontSize: 64px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Spline Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Spline Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Spline Sans
    fontSize: 18px
    fontWeight: '500'
    lineHeight: '1.5'
  body-md:
    fontFamily: Spline Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-bold:
    fontFamily: Spline Sans
    fontSize: 14px
    fontWeight: '700'
    lineHeight: '1.0'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 20px
  margin: 24px
---

## Brand & Style

The brand personality of this design system is electric, competitive, and rhythmic. It is designed to capture the high-stakes energy of a live musical game show, targeting a Gen-Z and Millennial audience that craves instant feedback and immersive environments. The emotional response is one of excitement and "flow," keeping users engaged through rapid-fire interactions.

The visual style is a fusion of **High-Contrast / Bold** and **Tactile** movements. It utilizes a dark, immersive "stage" environment punctuated by neon elements that seem to glow against deep, velvet backgrounds. Every interaction is designed to feel physical—buttons should feel like they are being pressed into a console, and transitions should mimic the movement of light and sound.

## Colors

This design system operates natively in **Dark Mode** to create a cinematic, theatrical experience. The palette is built on a foundation of "Midnight Violet" neutrals to ensure neon accents remain legible and vibrant.

- **Primary (Fuchsia):** Used for critical actions, highlights, and "winning" moments.
- **Secondary (Electric Blue):** Used for secondary interactions and decorative accents.
- **Answer Palette:** Four high-saturation colors specifically for game mechanics. Each color is paired with a specific geometric symbol to ensure accessibility for color-blind users.
- **Backgrounds:** Use deep violet gradients rather than pure black to maintain a sense of atmospheric depth.

## Typography

Typography in this design system is loud and unapologetic. **Spline Sans** was chosen for its geometric precision and energetic, youthful character. 

Headlines utilize heavy weights (700-800) to command attention during fast-paced gameplay. Display styles should incorporate slight negative letter-spacing to create a "compact" and impactful look, ideal for music titles and player names. Body text remains legible by using medium weights to stand out against dark, vibrant backgrounds. All interactive labels should be uppercase to enhance the "arcade" aesthetic.

## Layout & Spacing

This design system uses a **Fluid Grid** model with a heavy emphasis on "Safe Zones" to accommodate pronounced tactile elements. Because components feature thick shadows and "pop-out" effects, spacing between elements must be generous (minimum 24px) to prevent visual overlap.

The layout should center the "Question Card" or "Media Player" as the focal point, with answer options arranged in a 2x2 grid for mobile or a 4-column horizontal row for desktop. Use the 8px base unit for all internal component padding to maintain a consistent rhythmic density.

## Elevation & Depth

Depth is conveyed through **pronounced, hard-edged shadows** rather than soft blurs. This creates a "3D Sticker" or "Arcade Button" effect. 

- **Level 1 (Base):** Cards and containers with a 4px solid shadow offset, slightly darker than the background.
- **Level 2 (Interactive):** Buttons and active answer cards with an 8px solid shadow. The shadow should match the hue of the element but at a much lower luminosity.
- **Level 3 (Pressed):** When an element is clicked, it should translate 4px or 8px downwards (Y-axis), and the shadow size should decrease, simulating a physical mechanical press.
- **Glow Effects:** Use 15-20px outer blurs on primary elements to simulate neon tubes.

## Shapes

The shape language is consistently **Rounded (Level 2)**. A border-radius of 0.5rem (8px) is the standard for most components, while larger cards and answer modules use 1rem (16px) or 1.5rem (24px) to feel friendlier and more "toy-like."

The four specific answer shapes should be rendered as high-contrast white glyphs inside the answer buttons:
1. **Triangle** (Red Option)
2. **Diamond** (Blue Option)
3. **Circle** (Yellow Option)
4. **Square** (Green Option)

These icons should have slightly rounded vertices to match the overall UI curvature.

## Components

- **Answer Buttons:** Large, rectangular blocks with a thick bottom shadow. They must contain the geometric glyph on the left and the answer text centered. On hover, they should "lift" (shadow increases); on click, they "sink" (shadow decreases).
- **Progress Bars (Timer):** A thick, neon-filled track. As time runs out, the bar should change color from Electric Blue to Fuchsia and begin a "pulse" animation.
- **Player Chips:** Small rounded-pill containers showing user avatars and scores. Use high-contrast borders to distinguish the "Local Player" from "Opponents."
- **Leaderboard Rows:** Horizontal cards with glassmorphic backgrounds (low-opacity white with backdrop-blur) to sit above the deep violet background without feeling heavy.
- **Feedback Toasts:** Large, centered overlays for "CORRECT" or "WRONG" using the primary colors. Incorporate "spring" animations (slight bounce) for their entrance.
- **Music Visualizer:** A component at the top of the screen with dancing bars that use the secondary (Electric Blue) color to indicate active audio.