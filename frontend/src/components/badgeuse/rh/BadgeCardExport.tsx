import { useRef } from "react";
import { QRCodeCanvas } from "qrcode.react";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

type BadgeCardExportProps = {
  qrPayload: string;
  displayName: string;
  username?: string;
};

export function BadgeCardExport({
  qrPayload,
  displayName,
  username,
}: BadgeCardExportProps) {
  const canvasRef = useRef<HTMLDivElement>(null);

  const handleDownload = () => {
    const canvas = canvasRef.current?.querySelector("canvas");
    if (!canvas) return;
    const url = (canvas as HTMLCanvasElement).toDataURL("image/png");
    const link = document.createElement("a");
    link.download = `badge-${displayName.replace(/\s+/g, "-")}.png`;
    link.href = url;
    link.click();
  };

  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border p-4 bg-white">
      <div ref={canvasRef} className="p-4 bg-white rounded-lg">
        <QRCodeCanvas value={qrPayload} size={180} level="M" includeMargin />
        <p className="mt-3 text-center text-sm font-semibold text-slate-900">
          {displayName}
        </p>
        {username && (
          <p className="text-center text-xs text-slate-500">{username}</p>
        )}
      </div>
      <Button type="button" variant="outline" size="sm" onClick={handleDownload}>
        <Download className="h-4 w-4 mr-2" />
        Télécharger la carte (PNG)
      </Button>
    </div>
  );
}
