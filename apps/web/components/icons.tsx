/**
 * BrewMatch icon set — hand-built vector icons ported from the approved
 * Phase 2 mockup. Stroke icons inherit `currentColor`; pass a className.
 */
import type { SVGProps } from "react";

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

type IconProps = SVGProps<SVGSVGElement>;

export function DripIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M5 6h14l-4.5 8h-5z" />
      <path {...stroke} d="M4.5 6c0-1.2 3.4-2 7.5-2s7.5.8 7.5 2" />
      <path {...stroke} d="M12 14v3.5" />
      <path {...stroke} d="M8.5 20.5h7" />
    </svg>
  );
}

export function PourOverIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 120 110" {...props}>
      <path {...stroke} d="M30 24h60l-18 34H48z" />
      <path {...stroke} d="M28 24c0-4 14-7 32-7s32 3 32 7" />
      <ellipse {...stroke} cx="60" cy="24" rx="32" ry="7" />
      <path {...stroke} d="M60 58v9" />
      <path
        d="M60 73c2 0 3.5-1.5 3.5-3.2 0-2-3.5-5.8-3.5-5.8s-3.5 3.8-3.5 5.8C56.5 71.5 58 73 60 73z"
        fill="currentColor"
      />
      <path {...stroke} d="M40 80h40l-4 18a6 6 0 0 1-6 5H50a6 6 0 0 1-6-5z" />
      <path {...stroke} d="M80 84h7a5 5 0 0 1 0 10h-5" />
    </svg>
  );
}

export function CupIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M5 10h11v4.5a4.5 4.5 0 0 1-4.5 4.5h-2A4.5 4.5 0 0 1 5 14.5z" />
      <path {...stroke} d="M16 11h2.2a2.3 2.3 0 0 1 0 4.6H16" />
      <path {...stroke} d="M9 3.5c1 1-1 2 0 3.2M12.5 3.5c1 1-1 2 0 3.2" />
    </svg>
  );
}

export function BeanIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <ellipse {...stroke} cx="12" cy="12" rx="6" ry="9" transform="rotate(-35 12 12)" />
      <path {...stroke} d="M9.5 6.5c2.2 3 2.2 8 0 11" transform="rotate(-35 12 12)" />
    </svg>
  );
}

export function ChartIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M4 20h16" />
      <path {...stroke} d="M6.5 20v-6M11 20V8M15.5 20v-9M20 20v-4" />
    </svg>
  );
}

export function BookIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M6 4h12a1 1 0 0 1 1 1v15H8a2 2 0 0 0-2 2z" />
      <path {...stroke} d="M6 4a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2" />
      <path {...stroke} d="M10 9h6M10 12.5h4" />
    </svg>
  );
}

export function SourIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <circle {...stroke} cx="12" cy="12" r="7.5" />
      <path {...stroke} d="M12 12V4.7M12 12l6.3 3.6M12 12l-6.3 3.6" />
    </svg>
  );
}

export function BitterIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <ellipse cx="12" cy="12" rx="6" ry="9" transform="rotate(-35 12 12)" fill="currentColor" />
      <path
        d="M9.5 6.5c2.2 3 2.2 8 0 11"
        transform="rotate(-35 12 12)"
        fill="none"
        stroke="#fff"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function WeakIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M12 3.5c3.4 5 5.5 7.6 5.5 10.5a5.5 5.5 0 0 1-11 0c0-2.9 2.1-5.5 5.5-10.5z" />
    </svg>
  );
}

export function AstringentIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M4 8.5c2-2 4 2 6 0s4-2 6 0 4-2 4-2" />
      <path {...stroke} d="M4 13c2-2 4 2 6 0s4-2 6 0 4-2 4-2" />
      <path {...stroke} d="M4 17.5c2-2 4 2 6 0s4-2 6 0 4-2 4-2" />
    </svg>
  );
}

export function TrophyIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M7 4h10v5a5 5 0 0 1-10 0z" />
      <path {...stroke} d="M7 5H4.5v1.5A3.5 3.5 0 0 0 8 10M17 5h2.5v1.5A3.5 3.5 0 0 1 16 10" />
      <path {...stroke} d="M12 14v3M9 20h6M10 17h4l.5 3h-5z" />
    </svg>
  );
}

export function PlayIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path d="M8 5.5v13l11-6.5z" fill="currentColor" />
    </svg>
  );
}

export function TuneIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M6 4v6M6 14v6M12 4v3M12 11v9M18 4v9M18 17v3" />
      <circle {...stroke} cx="6" cy="12" r="2" />
      <circle {...stroke} cx="12" cy="9" r="2" />
      <circle {...stroke} cx="18" cy="15" r="2" />
    </svg>
  );
}

export function PinIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11z" />
      <circle {...stroke} cx="12" cy="10" r="2.5" />
    </svg>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...props}>
      <path {...stroke} d="M5 12.5l4.5 4.5L19 7" />
    </svg>
  );
}
