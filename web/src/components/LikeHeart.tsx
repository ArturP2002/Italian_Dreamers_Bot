type Props = {
  liked?: boolean;
  matched?: boolean;
  className?: string;
  onClick?: () => void;
  "aria-label"?: string;
};

/** Catalog heart — filled only when the viewer liked (match ≠ one-sided incoming). */
export function LikeHeart({ liked, matched, className = "", onClick, ...rest }: Props) {
  const on = Boolean(liked);
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
      <span className="like-heart__glyph" aria-hidden>
        {on ? "❤️" : "🤍"}
      </span>
    </button>
  );
}

export function MatchBanner({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="match-banner" role="status">
      <span className="match-banner__hearts" aria-hidden>
        <span>🤍</span>
        <span>❤️</span>
      </span>
      <span className="match-banner__text">
        <strong>{title}</strong>
        <span>{hint}</span>
      </span>
    </div>
  );
}
