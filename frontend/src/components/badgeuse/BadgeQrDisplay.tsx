import { useRef } from "react";
import { QRCodeCanvas } from "qrcode.react";
import { Download } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type BadgeQrDisplayProps = {
  payload: string;
  displayName?: string;
  username?: string;
  size?: number;
  className?: string;
  allowDownload?: boolean;
};

function badgeQrDownloadFilename(displayName?: string, username?: string): string {
  const base = username || displayName || "badgeuse";
  return `badgeuse-${base.replace(/\s+/g, "-").replace(/[^\w.-]/g, "")}.png`;
}

export function BadgeQrDisplay({
  payload,
  displayName,
  username,
  size = 200,
  className,
  allowDownload = false,
}: BadgeQrDisplayProps) {
  const qrRef = useRef<HTMLDivElement>(null);

  const handleDownload = () => {
    const canvas = qrRef.current?.querySelector("canvas");
    if (!canvas) return;
    const url = (canvas as HTMLCanvasElement).toDataURL("image/png");
    const link = document.createElement("a");
    link.download = badgeQrDownloadFilename(displayName, username);
    link.href = url;
    link.click();
  };

  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-xl border bg-white p-6 text-center shadow-sm",
        className
      )}
      aria-label="Code QR de badgeuse"
    >
      <div ref={qrRef}>
        <QRCodeCanvas
          value={payload}
          size={size}
          level="M"
          includeMargin
          bgColor="#ffffff"
          fgColor="#0f172a"
        />
      </div>
      {displayName && (
        <p className="text-base font-semibold text-slate-900">{displayName}</p>
      )}
      {username && (
        <p className="text-xs text-slate-500">Identifiant : {username}</p>
      )}
      <p className="text-xs text-muted-foreground max-w-[220px]">
        Présentez ce code à la borne d&apos;entrée
      </p>
      {allowDownload && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-1 gap-2 text-muted-foreground hover:text-foreground"
          onClick={handleDownload}
        >
          <Download className="h-4 w-4" aria-hidden />
          Enregistrer sur mon appareil
        </Button>
      )}
    </div>
  );
}
