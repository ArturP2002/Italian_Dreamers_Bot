type Props = {
  liked?: boolean;
  matched?: boolean;
  className?: string;
  onClick?: () => void;
  "aria-label"?: string;
};

/** Catalog heart: white outline → solid red when liked. */
export function LikeHeart({ liked, matched, className = "", onClick, ...rest }: Props) {
  const on = Boolean(liked || matched);
  return (
    <button
      type="button"
      className={`like-heart${on ? " is-on" : ""}${matched ? " is-match" : ""}${className ? ` ${className}` : ""}`}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onClick?.();
      }}
      {...rest}
    >
      <svg viewBox="0 0 24 24" aria-hidden>
        <path d="M12 21s-6.7-4.35-9.33-7.4C.8 11.5.5 8.7 2.1 6.7 3.5 4.95 6.05 4.6 7.9 6.05L12 9.4l4.1-3.35C17.95 4.6 20.5 4.95 21.9 6.7c1.6 2 .9 4.8-0.57 6.9C18.7 16.65 12 21 12 21z" />
      </svg>
    </button>
  );
}

export function MatchBanner({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="match-banner" role="status">
      <span className="match-banner__hearts" aria-hidden>
        <span>♥</span>
        <span>♥</span>
      </span>
      <span className="match-banner__text">
        <strong>{title}</strong>
        <span>{hint}</span>
      </span>
    </div>
  );
}
