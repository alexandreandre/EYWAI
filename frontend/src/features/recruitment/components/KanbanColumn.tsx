import { useState, useRef, type HTMLAttributes } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { GripVertical, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Candidate, PipelineStage } from "@/api/recruitment";
import { CandidateCard } from "./CandidateCard";

export function KanbanColumn({
  stage,
  candidates,
  onCardClick,
  onCandidateDrop,
  isRh,
  onRename,
  onDelete,
  stageDragHandleProps,
  compact = false,
  jobTitlesByJobId,
}: {
  stage: PipelineStage;
  candidates: Candidate[];
  onCardClick: (c: Candidate) => void;
  onCandidateDrop: (candidateId: string, stageId: string) => void;
  isRh: boolean;
  onRename?: (name: string) => void;
  onDelete?: () => void;
  /** Poignée @dnd-kit (icône ⋮⋮ uniquement — évite le conflit avec le renommage) */
  stageDragHandleProps?: HTMLAttributes<HTMLButtonElement>;
  /** Colonnes nombreuses : padding / espacement réduits */
  compact?: boolean;
  jobTitlesByJobId?: Record<string, string>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(stage.name);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dragCountRef = useRef(0);

  const bgColor = stage.stage_type === "rejected"
    ? "border-red-200 bg-red-50/50"
    : stage.stage_type === "hired"
      ? "border-green-200 bg-green-50/50"
      : "border-border bg-muted/30";

  const scrollViewportTint =
    stage.stage_type === "rejected"
      ? "[&_[data-radix-scroll-area-viewport]]:bg-red-50/50"
      : stage.stage_type === "hired"
        ? "[&_[data-radix-scroll-area-viewport]]:bg-green-50/50"
        : "[&_[data-radix-scroll-area-viewport]]:bg-muted/30";

  const startEditing = () => {
    setDraft(stage.name);
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  };

  const commitRename = () => {
    setEditing(false);
    const v = draft.trim();
    if (v && v !== stage.name && onRename) onRename(v);
  };

  const canDelete = isRh && stage.stage_type === "standard" && candidates.length === 0;

  return (
    <div
      className={`flex min-h-0 w-full min-w-0 max-w-full flex-1 flex-col overflow-hidden rounded-lg border transition-colors duration-150 ${dragOver ? "ring-2 ring-primary/40 border-primary/40" : ""} ${bgColor}`}
      onDragOver={isRh ? (e) => {
        if (e.dataTransfer.types.includes("candidateid")) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
        }
      } : undefined}
      onDragEnter={isRh ? (e) => {
        if (e.dataTransfer.types.includes("candidateid")) {
          dragCountRef.current++;
          setDragOver(true);
        }
      } : undefined}
      onDragLeave={isRh ? () => {
        dragCountRef.current--;
        if (dragCountRef.current <= 0) { dragCountRef.current = 0; setDragOver(false); }
      } : undefined}
      onDrop={isRh ? (e) => {
        dragCountRef.current = 0;
        setDragOver(false);
        const candidateId = e.dataTransfer.getData("candidateId");
        if (candidateId) { e.preventDefault(); onCandidateDrop(candidateId, stage.id); }
      } : undefined}
    >
      {/* Header — réordonnancement via la poignée ⋮⋮ (@dnd-kit) */}
      <div className={cn("border-b flex items-center gap-1.5", compact ? "px-2 py-1.5" : "px-3 py-2")}>
        {isRh && stageDragHandleProps && (
          <button
            type="button"
            className="-ml-1 p-1 rounded-md shrink-0 cursor-grab active:cursor-grabbing touch-none text-muted-foreground hover:bg-muted/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            aria-label="Déplacer l&apos;étape"
            {...stageDragHandleProps}
          >
            <GripVertical className="h-4 w-4 opacity-70" />
          </button>
        )}

        {editing ? (
          <Input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename();
              if (e.key === "Escape") { setEditing(false); setDraft(stage.name); }
            }}
            className="h-7 text-sm font-semibold px-1.5 flex-1 min-w-0"
            autoFocus
          />
        ) : (
          <span
            className={`text-sm font-semibold truncate flex-1 min-w-0 ${isRh && onRename ? "cursor-pointer hover:underline decoration-dotted underline-offset-4" : ""}`}
            onClick={isRh && onRename ? (e) => { e.stopPropagation(); startEditing(); } : undefined}
            title={isRh && onRename ? "Cliquer pour renommer" : undefined}
          >
            {stage.name}
          </span>
        )}

        <Badge variant="secondary" className="h-5 text-[10px] px-1.5 shrink-0">
          {candidates.length}
        </Badge>

        {isRh && stage.stage_type === "standard" && (
          <button
            onClick={(e) => { e.stopPropagation(); if (canDelete && onDelete) onDelete(); }}
            disabled={!canDelete}
            className="p-0.5 rounded hover:bg-destructive/10 disabled:opacity-20 disabled:pointer-events-none text-muted-foreground hover:text-destructive transition-colors"
            title={canDelete ? "Supprimer cette étape" : candidates.length > 0 ? "Déplacez d'abord les candidats" : "Supprimer"}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <ScrollArea
        className={cn(
          "flex-1 max-h-[calc(100vh-320px)]",
          compact ? "p-1" : "p-2",
          scrollViewportTint,
          "[&_[data-radix-scroll-area-viewport]]:rounded-b-lg",
        )}
      >
        <div className={compact ? "space-y-1.5" : "space-y-2"}>
          {candidates.map((c) => (
            <div
              key={c.id}
              draggable={isRh}
              onDragStart={isRh ? (e) => {
                e.dataTransfer.setData("candidateId", c.id);
                e.stopPropagation();
              } : undefined}
            >
              <CandidateCard
                candidate={c}
                onClick={() => onCardClick(c)}
                jobTitle={jobTitlesByJobId?.[c.job_id]}
              />
            </div>
          ))}
          {candidates.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-6">Aucun candidat</p>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
