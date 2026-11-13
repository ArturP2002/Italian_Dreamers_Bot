import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { PhotoGuideSheet } from "../components/PhotoGuideSheet";
import { type Language, t } from "../i18n/messages";
import { fetchMe, uploadVerificationSelfie } from "../lib/api";

type Props = { language: Language; onRefresh?: () => void };

type CamState = "idle" | "starting" | "live" | "denied";

async function requestCameraStream(): Promise<MediaStream> {
  const media = navigator.mediaDevices;
  if (!media?.getUserMedia) {
    throw new Error("getUserMedia unsupported");
  }
  // Try front camera first, then any camera — Telegram iOS is picky about constraints.
  const attempts: MediaStreamConstraints[] = [
    { audio: false, video: { facingMode: { ideal: "user" }, width: { ideal: 720 }, height: { ideal: 720 } } },
    { audio: false, video: { facingMode: "user" } },
    { audio: false, video: true },
  ];
  let lastError: unknown;
  for (const constraints of attempts) {
    try {
      return await media.getUserMedia(constraints);
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("camera_denied");
}

/** Crop mirrored frame to the circle guide (center square of the video). */
function captureCircleJpeg(video: HTMLVideoElement): Promise<Blob | null> {
  const vw = video.videoWidth || 720;
  const vh = video.videoHeight || 720;
  const side = Math.min(vw, vh);
  const sx = Math.floor((vw - side) / 2);
  const sy = Math.floor((vh - side) / 2);
  const canvas = document.createElement("canvas");
  canvas.width = side;
  canvas.height = side;
  const ctx = canvas.getContext("2d");
  if (!ctx) return Promise.resolve(null);
  // Mirror horizontally to match preview.
  ctx.translate(side, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(video, sx, sy, side, side, 0, 0, side, side);
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/jpeg", 0.92));
}

export function VerifyScreen({ language, onRefresh }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [photoGuideOpen, setPhotoGuideOpen] = useState(false);
  const [camState, setCamState] = useState<CamState>("idle");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const galleryInputRef = useRef<HTMLInputElement | null>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    const video = videoRef.current;
    if (video) {
      video.srcObject = null;
    }
    setCamState("idle");
  }, []);

  useEffect(() => {
    void fetchMe().then((me) => setStatus(me?.verification_status ?? "none"));
    return () => stopCamera();
  }, [stopCamera]);

  const uploadBlob = async (blob: Blob, filename: string) => {
    setBusy(true);
    setError(null);
    try {
      const file = new File([blob], filename, { type: blob.type || "image/jpeg" });
      const res = await uploadVerificationSelfie(file);
      setStatus(res.verification_status);
      onRefresh?.();
      if (res.verification_status === "verified" || res.verification_status === "pending") {
        stopCamera();
      }
    } catch (e) {
      const raw = e instanceof Error ? e.message : "";
      if (raw.includes("group_photo")) {
        setPhotoGuideOpen(true);
        setError(t(language, "photoGroupRejected"));
      } else {
        setError(t(language, "writeNoPerson"));
      }
    } finally {
      setBusy(false);
    }
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    await uploadBlob(file, file.name || "selfie.jpg");
  };

  const startLivePreview = async () => {
    if (busy || camState === "starting" || camState === "live") return;
    setError(null);
    setCamState("starting");
    try {
      const stream = await requestCameraStream();
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) {
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        setCamState("denied");
        return;
      }
      video.setAttribute("playsinline", "true");
      video.setAttribute("webkit-playsinline", "true");
      video.muted = true;
      video.srcObject = stream;
      await video.play();
      setCamState("live");
    } catch {
      stopCamera();
      setCamState("denied");
      setError(t(language, "verifyCameraDenied"));
    }
  };

  const captureFromPreview = async () => {
    const video = videoRef.current;
    if (!video || camState !== "live" || busy) return;
    const blob = await captureCircleJpeg(video);
    if (!blob) return;
    await uploadBlob(blob, "selfie.jpg");
  };

  const canCapture = status !== "verified" && status !== "pending";
  const isLive = camState === "live";

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back" onClick={() => stopCamera()}>
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "verifyTitle")}</h1>
      <p className="work-body">{t(language, "verifyHint")}</p>
      {status === "verified" ? <p className="home-meta">{t(language, "verifyOk")}</p> : null}
      {status === "pending" ? <p className="home-meta">{t(language, "verifyPending")}</p> : null}
      {status === "rejected" ? <p className="form-error">{t(language, "verifyRejected")}</p> : null}

      {canCapture ? (
        <>
          <div className="verify-camera">
            <div className={`verify-camera__frame${isLive ? " verify-camera__frame--live" : ""}`}>
              <video
                ref={videoRef}
                className="verify-camera__video"
                playsInline
                muted
                autoPlay
              />
              <div className="verify-camera__circle" aria-hidden />
              {!isLive ? (
                <p className="verify-camera__hint">
                  {camState === "starting"
                    ? t(language, "verifyCameraStarting")
                    : t(language, "verifyCircleHint")}
                </p>
              ) : null}
            </div>
            <p className="verify-camera__caption">{t(language, "verifyOvalHint")}</p>
          </div>

          {isLive ? (
            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={busy}
              onClick={() => void captureFromPreview()}
            >
              {busy ? t(language, "saving") : t(language, "verifyShoot")}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={busy || camState === "starting"}
              onClick={() => void startLivePreview()}
            >
              {camState === "starting" ? t(language, "verifyCameraStarting") : t(language, "verifyOpenCamera")}
            </button>
          )}

          <button
            type="button"
            className="btn btn--block btn--ghost verify-fallback"
            disabled={busy}
            onClick={() => galleryInputRef.current?.click()}
          >
            {t(language, "verifyUpload")}
          </button>

          <input
            ref={galleryInputRef}
            type="file"
            accept="image/*"
            hidden
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              void onFile(file);
            }}
          />
        </>
      ) : null}

      {error ? <p className="form-error">{error}</p> : null}
      <PhotoGuideSheet
        language={language}
        open={photoGuideOpen}
        onClose={() => setPhotoGuideOpen(false)}
      />
    </section>
  );
}
