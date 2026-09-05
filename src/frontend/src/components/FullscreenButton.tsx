import { useEffect, useState } from "react";
import { inTauri } from "../api/env";

async function isFullscreen(): Promise<boolean> {
  if (inTauri()) {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    return getCurrentWindow().isFullscreen();
  }
  return typeof document !== "undefined" && Boolean(document.fullscreenElement);
}

async function requestFullscreen(active: boolean): Promise<void> {
  if (inTauri()) {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().setFullscreen(active);
    return;
  }
  if (active) {
    await document.documentElement.requestFullscreen();
  } else if (document.fullscreenElement) {
    await document.exitFullscreen();
  }
}

const EnterIcon = () => (
  <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">
    <path
      d="M3 8V5a2 2 0 0 1 2-2h3M13 8v3a2 2 0 0 1-2 2H8M3 8v3a2 2 0 0 0 2 2h3M13 8V5a2 2 0 0 0-2-2H8"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const ExitIcon = () => (
  <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">
    <path
      d="M8 3v3a2 2 0 0 0 2 2h3M8 13v-3a2 2 0 0 1 2-2h3M8 3v3a2 2 0 0 1-2 2H3M8 13v-3a2 2 0 0 0-2-2H3"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const FullscreenButton = () => {
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => {
    if (inTauri()) return;
    const onChange = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const handleToggle = async () => {
    const next = !(await isFullscreen());
    try {
      await requestFullscreen(next);
      setFullscreen(next);
    } catch (error) {
      console.error("Failed to toggle fullscreen:", error);
    }
  };

  return (
    <button
      type="button"
      className="icon-btn"
      onClick={handleToggle}
      aria-pressed={fullscreen}
      aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
      title={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
      data-testid="fullscreen-toggle"
    >
      <span className="icon-btn-icon">
        {fullscreen ? <ExitIcon /> : <EnterIcon />}
      </span>
      <span className="icon-btn-label">
        {fullscreen ? "Exit fullscreen" : "Fullscreen"}
      </span>
    </button>
  );
};

export default FullscreenButton;
