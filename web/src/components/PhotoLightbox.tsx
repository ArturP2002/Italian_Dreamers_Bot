import { useEffect, useRef } from "react";

type Props = {
  urls: string[];
  index: number;
  onClose: () => void;
  onIndexChange: (index: number) => void;
  closeLabel?: string;
};

export function PhotoLightbox({ urls, index, onClose, onIndexChange, closeLabel = "×" }: Props) {
  const touchStartX = useRef<number | null>(null);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" && index < urls.length - 1) onIndexChange(index + 1);
      if (e.key === "ArrowLeft" && index > 0) onIndexChange(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [index, urls.length, onClose, onIndexChange]);

  if (!urls.length) return null;
  const safeIndex = Math.min(Math.max(index, 0), urls.length - 1);
  const src = urls[safeIndex];

  return (
    <div
      className="photo-lightbox"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      onTouchStart={(e) => {
        touchStartX.current = e.changedTouches[0]?.clientX ?? null;
      }}
      onTouchEnd={(e) => {
        const start = touchStartX.current;
        touchStartX.current = null;
        if (start == null) return;
        const dx = (e.changedTouches[0]?.clientX ?? start) - start;
        if (dx < -40 && safeIndex < urls.length - 1) onIndexChange(safeIndex + 1);
        else if (dx > 40 && safeIndex > 0) onIndexChange(safeIndex - 1);
      }}
    >
      <button
        type="button"
        className="photo-lightbox__close"
        aria-label={closeLabel}
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
      >
        {closeLabel}
      </button>

      {urls.length > 1 ? (
        <p className="photo-lightbox__counter">
          {safeIndex + 1} / {urls.length}
        </p>
      ) : null}

      {safeIndex > 0 ? (
        <button
          type="button"
          className="photo-lightbox__nav photo-lightbox__nav--prev"
          aria-label="Previous"
          onClick={(e) => {
            e.stopPropagation();
            onIndexChange(safeIndex - 1);
          }}
        >
          ‹
        </button>
      ) : null}

      <img
        className="photo-lightbox__img"
        src={src}
        alt=""
        onClick={(e) => e.stopPropagation()}
      />

      {safeIndex < urls.length - 1 ? (
        <button
          type="button"
          className="photo-lightbox__nav photo-lightbox__nav--next"
          aria-label="Next"
          onClick={(e) => {
            e.stopPropagation();
            onIndexChange(safeIndex + 1);
          }}
        >
          ›
        </button>
      ) : null}
    </div>
  );
}
