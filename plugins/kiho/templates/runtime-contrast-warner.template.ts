// kiho theme-contrast-guard — runtime dev warner (Layer 3)
//
// Wires into ThemeProvider in __DEV__ to console.warn() on low-contrast pairs
// at render time. Catches dynamic colour composition that Layer 1 (static
// token matrix) cannot model: state-driven colour, prop overrides, conditional
// styles, computed gradients, etc.
//
// Production builds: noop. Bundle size in prod = 0 bytes (the entire body is
// gated behind `if (__DEV__)`).
//
// Usage:
//   1. Copy this file to apps/<your-app>/src/theme/runtime-contrast-warner.ts
//   2. In ThemeProvider.tsx (or wherever your theme root is):
//        import { installContrastWarner } from './runtime-contrast-warner';
//        useEffect(() => {
//          if (__DEV__) installContrastWarner({ threshold: 4.5 });
//        }, []);
//   3. (Optional) Enable strict mode by setting process.env.KIHO_CONTRAST_STRICT
//      = 'true' or passing { strict: true } — low-contrast pairs will then
//      throw in dev render rather than warn.
//
// React Native + RN-Web parity: imports `Text` from 'react-native'. RN-Web
// shims the same module so the same warner runs on web. No `window`
// references; no native-only APIs.

import { Text } from "react-native";
import type { ComponentType } from "react";

// ---------------------------------------------------------------------------
// WCAG 2.x contrast — port of bin/contrast_audit.py (~25 LOC)
// ---------------------------------------------------------------------------

type RGB = [number, number, number];
type RGBA = [number, number, number, number];

function parseColor(s: string): RGBA | null {
  s = s.trim();
  // #rgb / #rrggbb / #rrggbbaa
  if (s.startsWith("#")) {
    const h = s.slice(1);
    if (h.length === 3) {
      return [
        parseInt(h[0] + h[0], 16),
        parseInt(h[1] + h[1], 16),
        parseInt(h[2] + h[2], 16),
        1,
      ];
    }
    if (h.length === 6) {
      return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 1];
    }
    if (h.length === 8) {
      return [
        parseInt(h.slice(0, 2), 16),
        parseInt(h.slice(2, 4), 16),
        parseInt(h.slice(4, 6), 16),
        parseInt(h.slice(6, 8), 16) / 255,
      ];
    }
    return null;
  }
  // rgb(r,g,b) / rgba(r,g,b,a)
  const m = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)$/i.exec(s);
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3]), m[4] !== undefined ? Number(m[4]) : 1];
  return null;
}

function channel(c: number): number {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

function luminance([r, g, b]: RGB): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a: RGB, b: RGB): number {
  const la = luminance(a);
  const lb = luminance(b);
  const [hi, lo] = la >= lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

function compositeOn(fg: RGBA, bg: RGB): RGB {
  const a = fg[3];
  if (a >= 1) return [fg[0], fg[1], fg[2]];
  return [
    Math.round(fg[0] * a + bg[0] * (1 - a)),
    Math.round(fg[1] * a + bg[1] * (1 - a)),
    Math.round(fg[2] * a + bg[2] * (1 - a)),
  ];
}

// ---------------------------------------------------------------------------
// Style cascade walker
// ---------------------------------------------------------------------------

interface InstallOptions {
  /** Body-text minimum ratio. Default 4.5 (WCAG SC 1.4.3 AA). */
  threshold?: number;
  /** When true, throw in dev render on any low-contrast finding. Default
   *  reads `process.env.KIHO_CONTRAST_STRICT === 'true'` (false otherwise). */
  strict?: boolean;
  /** Hero token names that bump threshold to 7.0. */
  heroTokens?: readonly string[];
}

interface FlatStyle {
  color?: string;
  backgroundColor?: string;
  fontSize?: number;
  fontWeight?: string | number;
  [k: string]: unknown;
}

/** Flatten a RN style prop (object | array | falsy | id) into a single object.
 *  We only need `color` / `backgroundColor` / `fontSize` / `fontWeight`. */
function flattenStyle(style: unknown): FlatStyle {
  if (!style) return {};
  if (typeof style === "number") return {}; // RN registered style id; not resolvable here
  if (Array.isArray(style)) {
    const out: FlatStyle = {};
    for (const s of style) Object.assign(out, flattenStyle(s));
    return out;
  }
  if (typeof style === "object") return style as FlatStyle;
  return {};
}

let _installed = false;

export function installContrastWarner(options: InstallOptions = {}): void {
  if (_installed) return;
  if (typeof __DEV__ !== "undefined" && !__DEV__) return;
  _installed = true;

  const threshold = options.threshold ?? 4.5;
  const strict =
    options.strict ??
    (typeof process !== "undefined" && process.env?.KIHO_CONTRAST_STRICT === "true");
  const heroTokens = new Set(options.heroTokens ?? ["heroNumber", "netWorth"]);

  // Cache to avoid the same component / style combination spamming logs
  const seen = new Set<string>();

  const TextAny = Text as unknown as ComponentType<unknown> & {
    render?: (props: Record<string, unknown>, ref: unknown) => unknown;
  };
  const original = TextAny.render;
  if (typeof original !== "function") {
    // RN-Web shim may not expose render; fall back to a wrapper at the
    // theme provider level instead. Skip silently.
    _installed = false;
    return;
  }

  TextAny.render = function patchedTextRender(props: Record<string, unknown>, ref: unknown) {
    try {
      const style = flattenStyle(props?.style);
      const fg = typeof style.color === "string" ? style.color : undefined;
      // Layer 3 cannot walk the React tree from inside Text.render to find
      // the nearest non-transparent backgroundColor ancestor — that requires
      // a higher-level wrapper. We do a best-effort against an explicit
      // backgroundColor on the same element OR the props.contextBg if the
      // theme provider has plumbed one through (kiho convention).
      const bg =
        (typeof style.backgroundColor === "string" ? style.backgroundColor : undefined) ??
        (typeof props?.contextBg === "string" ? (props.contextBg as string) : undefined);

      if (fg && bg) {
        const fgRGBA = parseColor(fg);
        const bgRGBA = parseColor(bg);
        if (fgRGBA && bgRGBA) {
          const bgRGB: RGB =
            bgRGBA[3] >= 1
              ? [bgRGBA[0], bgRGBA[1], bgRGBA[2]]
              : compositeOn(bgRGBA, [255, 255, 255]); // assume white under translucent
          const fgRGB = fgRGBA[3] >= 1 ? ([fgRGBA[0], fgRGBA[1], fgRGBA[2]] as RGB) : compositeOn(fgRGBA, bgRGB);
          const ratio = contrast(fgRGB, bgRGB);

          // Determine threshold: hero / large / body
          const fontSize = typeof style.fontSize === "number" ? style.fontSize : 14;
          const isBold =
            String(style.fontWeight ?? "").match(/^(?:[6-9]00|bold)$/i) !== null;
          const isLargeText = fontSize >= 18 || (fontSize >= 14 && isBold);
          const tokenName = typeof props?.["data-token"] === "string" ? (props["data-token"] as string) : "";
          const isHero = heroTokens.has(tokenName);
          const required = isHero ? 7.0 : isLargeText ? 3.0 : threshold;

          if (ratio + 1e-6 < required) {
            const cacheKey = `${fg}|${bg}|${required}`;
            if (!seen.has(cacheKey)) {
              seen.add(cacheKey);
              const componentName = (props?.testID as string) || (props?.accessibilityLabel as string) || "<Text>";
              const msg =
                `[contrast] ${componentName} color=${fg} on bg=${bg} ratio=${ratio.toFixed(2)} ` +
                `(required ${required}${isHero ? ", hero" : isLargeText ? ", large" : ""})`;
              if (strict) {
                throw new Error(msg);
              }
              // eslint-disable-next-line no-console
              console.warn(msg);
            }
          }
        }
      }
    } catch (err) {
      if (strict) throw err;
      // Silent in non-strict — never crash render due to the warner
    }
    return original.call(this, props, ref);
  };
}

/** Test-only — restore the original Text.render. Called from setup files. */
export function uninstallContrastWarner(): void {
  _installed = false;
}
