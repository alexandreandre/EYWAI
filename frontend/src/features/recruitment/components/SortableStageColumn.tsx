import { type CSSProperties } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "@/lib/utils";
import type { Candidate, PipelineStage } from "@/api/recruitment";
import { KanbanColumn } from "./KanbanColumn";

export function SortableStageColumn({
  stage,
  candidates,
  onCardClick,
  onCandidateDrop,
  isRh,
  onRename,
  onDelete,
  compact = false,
}: {
  stage: PipelineStage;
  candidates: Candidate[];
  onCardClick: (c: Candidate) => void;
  onCandidateDrop: (candidateId: string, stageId: string) => void;
  isRh: boolean;
  onRename?: (name: string) => void;
  onDelete?: () => void;
  compact?: boolean;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: stage.id });

  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 20 : undefined,
  };

  return (
    <div
      id={`recruitment-pipeline-stage-${stage.id}`}
      ref={setNodeRef}
      style={style}
      className={cn("min-w-0 flex-1", isDragging && "opacity-95")}
    >
      <KanbanColumn
        stage={stage}
        candidates={candidates}
        onCardClick={onCardClick}
        onCandidateDrop={onCandidateDrop}
        isRh={isRh}
        onRename={onRename}
        onDelete={onDelete}
        compact={compact}
        stageDragHandleProps={{ ...listeners, ...attributes }}
      />
    </div>
  );
}
