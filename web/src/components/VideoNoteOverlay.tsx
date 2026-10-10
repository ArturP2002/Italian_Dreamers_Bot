import { useEffect, useRef, useState } from "react";

type Props = {
  src: string;
  closeLabel: string;
  onClose: () => void;
};

const RING_RADIUS = 48;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

export function VideoNoteOverlay({ src, closeLabel, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    void videoRef.current?.play().catch(() => setPlaying(false));
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggle = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) void video.play();
    else video.pause();
  };

  return (
    <div className="video-note-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <button type="button" className="video-note-overlay__close" aria-label={closeLabel} onClick={onClose}>
        ×
      </button>
      <div
        className="video-note"
        onClick={(e) => {
          e.stopPropagation();
          toggle();
        }}
      >
        <video
          ref={videoRef}
          className="video-note__video"
          src={src}
          playsInline
          preload="auto"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => {
            setPlaying(false);
            setProgress(1);
          }}
          onTimeUpdate={(e) => {
            const v = e.currentTarget;
            if (v.duration) setProgress(v.currentTime / v.duration);
          }}
        />
        <svg className="video-note__ring" viewBox="0 0 100 100" aria-hidden>
          <circle cx="50" cy="50" r={RING_RADIUS} className="video-note__ring-track" />
          <circle
            cx="50"
            cy="50"
            r={RING_RADIUS}
            className="video-note__ring-bar"
            strokeDasharray={RING_LENGTH}
            strokeDashoffset={RING_LENGTH * (1 - progress)}
          />
        </svg>
        {!playing ? (
          <span className="video-note__play" aria-hidden>
            ▶
          </span>
        ) : null}
      </div>
    </div>
  );
}
