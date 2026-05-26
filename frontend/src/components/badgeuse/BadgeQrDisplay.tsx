import { QRCodeSVG } from "qrcode.react";
import { cn } from "@/lib/utils";

type BadgeQrDisplayProps = {
  payload: string;
  displayName?: string;
  username?: string;
  size?: number;
  className?: string;
};

export function BadgeQrDisplay({
  payload,
  displayName,
  username,
  size = 200,
  className,
}: BadgeQrDisplayProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-xl border bg-white p-6 text-center shadow-sm",
        className
      )}
      aria-label="Code QR de badgeuse"
    >
      <QRCodeSVG
        value={payload}
        size={size}
        level="M"
        includeMargin
        bgColor="#ffffff"
        fgColor="#0f172a"
      />
      {displayName && (
        <p className="text-base font-semibold text-slate-900">{displayName}</p>
      )}
      {username && (
        <p className="text-xs text-slate-500">Identifiant : {username}</p>
      )}
      <p className="text-xs text-muted-foreground max-w-[220px]">
        Présentez ce code à la borne d&apos;entrée
      </p>
    </div>
  );
}
