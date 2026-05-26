import { useCallback, useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { Maximize2, Minimize2, RefreshCw } from "lucide-react";
import { scanBadgeQr, type ScanPunchResult } from "@/api/badgeuse";
import { formatSecondsToHoursMinutes, formatTimeFr } from "@/lib/badgeuseFormat";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

const SCANNER_ID = "badgeuse-qr-reader";
const DEBOUNCE_MS = 4000;

type Feedback =
  | { kind: "success"; result: ScanPunchResult }
  | { kind: "error"; message: string };

type QrScannerPanelProps = {
  companyId: string;
  onScanSuccess?: () => void;
  className?: string;
};

async function startScannerWithBestCamera(
  scanner: Html5Qrcode,
  onDecoded: (text: string) => void
): Promise<void> {
  const config = { fps: 10, qrbox: { width: 280, height: 280 } };
  const noop = () => {};

  const attempts: (string | { facingMode: string })[] = [
    { facingMode: "environment" },
    { facingMode: "user" },
  ];

  let lastErr: unknown;
  for (const cameraIdOrConfig of attempts) {
    try {
      await scanner.start(cameraIdOrConfig, config, onDecoded, noop);
      return;
    } catch (e) {
      lastErr = e;
      await safeStopScanner(scanner);
    }
  }

  try {
    const devices = await Html5Qrcode.getCameras();
    for (const device of devices) {
      try {
        await scanner.start(device.id, config, onDecoded, noop);
        return;
      } catch (e) {
        lastErr = e;
        await safeStopScanner(scanner);
      }
    }
  } catch (e) {
    lastErr = e;
  }

  throw lastErr;
}

async function safeStopScanner(scanner: Html5Qrcode): Promise<void> {
  try {
    if (scanner.isScanning) {
      await scanner.stop();
    }
  } catch {
    /* ignore */
  }
  try {
    scanner.clear();
  } catch {
    /* ignore */
  }
}

export function QrScannerPanel({
  companyId,
  onScanSuccess,
  className,
}: QrScannerPanelProps) {
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [scanning, setScanning] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraRetryKey, setCameraRetryKey] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const lastPayloadRef = useRef<{ payload: string; at: number } | null>(null);
  const busyRef = useRef(false);
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const cameraContainerRef = useRef<HTMLDivElement | null>(null);
  const isUnmountingRef = useRef(false);

  const stopNativeVideoTracks = useCallback(() => {
    const container = cameraContainerRef.current;
    if (!container) return;
    const videos = container.querySelectorAll("video");
    videos.forEach((video) => {
      const media = video.srcObject;
      if (media instanceof MediaStream) {
        media.getTracks().forEach((track) => track.stop());
        video.srcObject = null;
      }
    });
  }, []);

  const shutdownCamera = useCallback(async () => {
    const scanner = scannerRef.current;
    scannerRef.current = null;
    if (scanner) {
      await safeStopScanner(scanner);
    }
    stopNativeVideoTracks();
  }, [stopNativeVideoTracks]);

  const playBeep = useCallback((ok: boolean) => {
    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = ok ? 880 : 220;
      gain.gain.value = 0.08;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.12);
    } catch {
      /* ignore */
    }
    if (typeof navigator !== "undefined" && navigator.vibrate) {
      navigator.vibrate(ok ? 40 : [80, 40, 80]);
    }
  }, []);

  const handleDecoded = useCallback(
    async (decodedText: string) => {
      const now = Date.now();
      const last = lastPayloadRef.current;
      if (
        last &&
        last.payload === decodedText &&
        now - last.at < DEBOUNCE_MS
      ) {
        return;
      }
      if (busyRef.current) return;
      busyRef.current = true;
      lastPayloadRef.current = { payload: decodedText, at: now };

      try {
        const result = await scanBadgeQr(companyId, { qr_payload: decodedText });
        setFeedback({ kind: "success", result });
        playBeep(true);
        onScanSuccess?.();
      } catch (err: unknown) {
        const message =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ||
          (err as Error)?.message ||
          "Scan impossible";
        setFeedback({ kind: "error", message: String(message) });
        playBeep(false);
      } finally {
        busyRef.current = false;
        window.setTimeout(() => setFeedback(null), 2200);
      }
    },
    [companyId, onScanSuccess, playBeep]
  );

  useEffect(() => {
    let scanner: Html5Qrcode | null = null;
    let cancelled = false;
    isUnmountingRef.current = false;

    const start = async () => {
      setCameraError(null);
      setScanning(false);
      try {
        scanner = new Html5Qrcode(SCANNER_ID);
        scannerRef.current = scanner;
        await startScannerWithBestCamera(scanner, (text) => {
          if (!cancelled) void handleDecoded(text);
        });
        if (!cancelled) setScanning(true);
      } catch {
        if (!cancelled) {
          setCameraError(
            "Aucune caméra utilisable (permissions refusées, appareil sans caméra, ou autre application qui utilise déjà la caméra). Utilisez le mode « Sans QR » sous cette zone."
          );
        }
      }
    };

    void start();

    return () => {
      cancelled = true;
      isUnmountingRef.current = true;
      void shutdownCamera();
    };
  }, [handleDecoded, cameraRetryKey, shutdownCamera]);

  useEffect(() => {
    const onHidden = () => {
      if (document.hidden) {
        void shutdownCamera();
      }
    };
    document.addEventListener("visibilitychange", onHidden);
    return () => {
      document.removeEventListener("visibilitychange", onHidden);
    };
  }, [shutdownCamera]);

  useEffect(() => {
    const onFullscreenChange = () => {
      const fullscreenNow =
        document.fullscreenElement === cameraContainerRef.current;
      setIsFullscreen(fullscreenNow);
      if (isUnmountingRef.current) return;
      // Restart scanner to let html5-qrcode recompute internal canvas/video sizes.
      setCameraRetryKey((k) => k + 1);
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
    };
  }, []);

  const toggleFullscreen = async () => {
    const node = cameraContainerRef.current;
    if (!node || typeof node.requestFullscreen !== "function") return;
    try {
      if (document.fullscreenElement === node) {
        await document.exitFullscreen();
      } else {
        await node.requestFullscreen();
      }
    } catch {
      /* ignore */
    }
  };

  return (
    <div className={cn("relative space-y-3", className)}>
      {cameraError && (
        <Alert variant="default" className="border-amber-500/40 bg-amber-50/80 dark:bg-amber-950/30">
          <AlertTitle className="text-amber-950 dark:text-amber-100">
            Caméra non disponible
          </AlertTitle>
          <AlertDescription className="text-amber-950/90 dark:text-amber-50/90">
            <p className="text-sm">{cameraError}</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-3 gap-2 border-amber-600/40 bg-background"
              onClick={() => setCameraRetryKey((k) => k + 1)}
            >
              <RefreshCw className="h-4 w-4" />
              Réessayer la caméra
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div
        ref={cameraContainerRef}
        className={cn(
          "relative",
          isFullscreen && "h-screen w-screen overflow-hidden bg-black"
        )}
      >
      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="absolute right-2 top-2 z-20 gap-1.5"
        onClick={() => void toggleFullscreen()}
      >
        {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        {isFullscreen ? "Quitter plein écran" : "Plein écran"}
      </Button>
      <div
        id={SCANNER_ID}
        className={cn(
          "w-full min-h-[320px] rounded-xl overflow-hidden bg-slate-950 [&_video]:rounded-xl",
          isFullscreen &&
            "h-full min-h-0 rounded-none [&_video]:h-full [&_video]:rounded-none [&_video]:object-cover"
        )}
      />
      {!scanning && !cameraError && (
        <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-slate-900/80 text-sm text-slate-200">
          Initialisation de la caméra…
        </div>
      )}
      {!scanning && cameraError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-muted-foreground/30 bg-muted/40 px-4 text-center text-sm text-muted-foreground">
          <p>Zone caméra — désactivée</p>
          <p className="text-xs">Faites défiler vers le mode Sans QR</p>
        </div>
      )}

      {feedback && (
        <div
          className={cn(
            "absolute inset-0 flex flex-col items-center justify-center rounded-xl px-6 text-center transition-opacity",
            feedback.kind === "success"
              ? "bg-emerald-600/95 text-white"
              : "bg-red-600/95 text-white"
          )}
          role="status"
          aria-live="assertive"
        >
          {feedback.kind === "success" ? (
            <>
              <p className="text-2xl font-bold">{feedback.result.status_label}</p>
              <p className="mt-2 text-lg">{feedback.result.employee_name}</p>
              <p className="mt-1 text-sm opacity-90">
                {formatTimeFr(feedback.result.timestamp)} —{" "}
                {formatSecondsToHoursMinutes(feedback.result.total_seconds_today)}{" "}
                aujourd&apos;hui
              </p>
            </>
          ) : (
            <>
              <p className="text-xl font-semibold">QR non reconnu</p>
              <p className="mt-2 text-sm">{feedback.message}</p>
            </>
          )}
        </div>
      )}
      </div>
    </div>
  );
}
