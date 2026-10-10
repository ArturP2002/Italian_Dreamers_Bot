import { useRef, useState } from "react";

type Props = {
  src: string;
  poster: string;
};

const RING_RADIUS = 48;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

export function VideoNote({ src, poster }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);

  const toggle = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) void video.play();
    else video.pause();
  };

  return (
    <button type="button" className="video-note" aria-label={playing ? "Pause" : "Play"} onClick={toggle}>
      <video
        key={src}
        ref={videoRef}
        className="video-note__video"
        src={src}
        poster={poster}
        playsInline
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false);
          setProgress(0);
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
    </button>
  );
}
