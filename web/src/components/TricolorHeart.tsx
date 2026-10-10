import { useId } from "react";

const HEART_PATH =
  "M32 55C30.5 53.7 7 37.6 7 22.5 7 14.4 13.2 8 21 8c4.8 0 8.7 2.5 11 6.2C34.3 10.5 38.2 8 43 8c7.8 0 14 6.4 14 14.5C57 37.6 33.5 53.7 32 55z";

export function TricolorHeart({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const clip = `th-clip-${uid}`;
  const gold = `th-gold-${uid}`;
  const green = `th-green-${uid}`;
  const white = `th-white-${uid}`;
  const red = `th-red-${uid}`;
  const shade = `th-shade-${uid}`;
  const gloss = `th-gloss-${uid}`;
  const glow = `th-glow-${uid}`;

  return (
    <svg className={className} viewBox="0 0 64 64" aria-hidden>
      <defs>
        <clipPath id={clip}>
          <path d={HEART_PATH} />
        </clipPath>
        <linearGradient id={gold} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#F6E3B0" />
          <stop offset="0.35" stopColor="#C8A774" />
          <stop offset="0.65" stopColor="#8E6B3A" />
          <stop offset="1" stopColor="#E9CF94" />
        </linearGradient>
        <linearGradient id={green} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2FA866" />
          <stop offset="1" stopColor="#0B5E33" />
        </linearGradient>
        <linearGradient id={white} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFFFFF" />
          <stop offset="1" stopColor="#E7E1D6" />
        </linearGradient>
        <linearGradient id={red} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#E8484F" />
          <stop offset="1" stopColor="#9E1A24" />
        </linearGradient>
        <radialGradient id={shade} cx="0.5" cy="0.35" r="0.75">
          <stop offset="0.55" stopColor="#000" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity="0.35" />
        </radialGradient>
        <linearGradient id={gloss} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.75" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <radialGradient id={glow} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#FFF6DC" stopOpacity="1" />
          <stop offset="1" stopColor="#FFF6DC" stopOpacity="0" />
        </radialGradient>
      </defs>

      <g clipPath={`url(#${clip})`}>
        <rect x="0" y="0" width="25" height="64" fill={`url(#${green})`} />
        <rect x="25" y="0" width="14" height="64" fill={`url(#${white})`} />
        <rect x="39" y="0" width="25" height="64" fill={`url(#${red})`} />
        <rect x="0" y="0" width="64" height="64" fill={`url(#${shade})`} />
        <ellipse cx="22" cy="17" rx="11" ry="6" fill={`url(#${gloss})`} transform="rotate(-18 22 17)" />
        <ellipse cx="45" cy="16" rx="6" ry="3.2" fill={`url(#${gloss})`} opacity="0.7" transform="rotate(18 45 16)" />
      </g>

      <path d={HEART_PATH} fill="none" stroke={`url(#${gold})`} strokeWidth="2.6" strokeLinejoin="round" />

      <circle cx="51" cy="11" r="5" fill={`url(#${glow})`} />
      <path d="M51 6.5l0.9 3.6 3.6 0.9-3.6 0.9-0.9 3.6-0.9-3.6-3.6-0.9 3.6-0.9z" fill="#FFF8E6" />
    </svg>
  );
}
