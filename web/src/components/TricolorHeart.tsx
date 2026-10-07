export function TricolorHeart({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden>
      <defs>
        <clipPath id="heartClip">
          <path d="M12 21s-7.2-4.6-9.4-8.3C.8 9.6 2.2 6 5.5 6c1.8 0 3.1 1.1 3.9 2.2C10.2 7.1 11.5 6 13.3 6c3.3 0 4.7 3.6 2.9 6.7C19.2 16.4 12 21 12 21z" />
        </clipPath>
      </defs>
      <g clipPath="url(#heartClip)">
        <rect x="0" y="0" width="8" height="24" fill="#009246" />
        <rect x="8" y="0" width="8" height="24" fill="#ffffff" />
        <rect x="16" y="0" width="8" height="24" fill="#ce2b37" />
      </g>
    </svg>
  );
}
