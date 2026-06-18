// Onglet RH : modèles de trames d'entretien (intégration page Formation — Ticket 12)

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Loader2, Plus, Copy, Archive, Pencil, ChevronUp, ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/components/ui/use-toast";
import { useCompany } from "@/contexts/CompanyContext";
import { INTERVIEW_TYPE_LABELS, type InterviewType } from "@/api/annualReviews";
import {
  getTemplates,
  createTemplate,
  updateTemplate,
  archiveTemplate,
  duplicateTemplate,
  QUESTION_TYPE_LABELS,
  type InterviewTemplate,
  type QuestionType,
  type TemplateSectionCreate,
} from "@/api/interviewTemplates";
import { cn } from "@/lib/utils";

type StatusFilter = "all" | "active" | "archived";

type LocalQuestion = {
  clientId: string;
  label: string;
  question_type: QuestionType;
  optionsText: string;
  is_required: boolean;
  is_self_evaluation: boolean;
};

type LocalSection = {
  clientId: string;
  title: string;
  questions: LocalQuestion[];
};

function newClientId() {
  return crypto.randomUUID();
}

function templateToLocal(t: InterviewTemplate): LocalSection[] {
  const sections = [...t.sections].sort((a, b) => a.position - b.position);
  return sections.map((s) => ({
    clientId: s.id,
    title: s.title,
    questions: [...s.questions]
      .sort((a, b) => a.position - b.position)
      .map((q) => ({
        clientId: q.id,
        label: q.label,
        question_type: q.question_type as QuestionType,
        optionsText:
          q.options != null ? (typeof q.options === "string" ? q.options : JSON.stringify(q.options)) : "",
        is_required: q.is_required,
        is_self_evaluation: q.is_self_evaluation,
      })),
  }));
}

function localToPayload(sections: LocalSection[]): TemplateSectionCreate[] {
  return sections.map((s, si) => ({
    title: s.title,
    position: si,
    questions: s.questions.map((q, qi) => {
      let options: unknown = undefined;
      const t = q.optionsText.trim();
      if (t && (q.question_type === "single_select" || q.question_type === "multi_select")) {
        try {
          options = JSON.parse(t);
        } catch {
          options = t.split("\n").map((x) => x.trim()).filter(Boolean);
        }
      }
      return {
        label: q.label,
        question_type: q.question_type,
        options,
        is_required: q.is_required,
        is_self_evaluation: q.is_self_evaluation,
        position: qi,
      };
    }),
  }));
}

function SortableSectionCard({
  section,
  index,
  onTitleChange,
  onRemoveSection,
  onAddQuestion,
  onQuestionChange,
  onMoveQuestion,
  onRemoveQuestion,
}: {
  section: LocalSection;
  index: number;
  onTitleChange: (id: string, title: string) => void;
  onRemoveSection: (id: string) => void;
  onAddQuestion: (sectionId: string) => void;
  onQuestionChange: (
    sectionId: string,
    qid: string,
    patch: Partial<LocalQuestion>
  ) => void;
  onMoveQuestion: (sectionId: string, qid: string, dir: -1 | 1) => void;
  onRemoveQuestion: (sectionId: string, qid: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: section.clientId,
  });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "rounded-lg border bg-card p-4 space-y-3",
        isDragging && "opacity-70 ring-2 ring-primary/30"
      )}
    >
      <div className="flex items-start gap-2">
        <button
          type="button"
          className="mt-1 p-1 rounded-md text-muted-foreground hover:bg-muted cursor-grab active:cursor-grabbing touch-none"
          aria-label="Déplacer la section"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <div className="flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2 justify-between">
            <Label className="text-xs text-muted-foreground">Section {index + 1}</Label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-destructive h-7"
              onClick={() => onRemoveSection(section.clientId)}
            >
              Supprimer la section
            </Button>
          </div>
          <Input
            placeholder="Titre de la section"
            value={section.title}
            onChange={(e) => onTitleChange(section.clientId, e.target.value)}
          />
        </div>
      </div>

      <div className="pl-8 space-y-3 border-l-2 border-muted ml-2">
        {section.questions.map((q, qi) => (
          <div key={q.clientId} className="rounded-md border bg-muted/20 p-3 space-y-2">
            <div className="flex flex-wrap gap-2 justify-between items-center">
              <span className="text-xs font-medium text-muted-foreground">Question {qi + 1}</span>
              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  disabled={qi === 0}
                  onClick={() => onMoveQuestion(section.clientId, q.clientId, -1)}
                  aria-label="Monter"
                >
                  <ChevronUp className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  disabled={qi === section.questions.length - 1}
                  onClick={() => onMoveQuestion(section.clientId, q.clientId, 1)}
                  aria-label="Descendre"
                >
                  <ChevronDown className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-destructive h-7"
                  onClick={() => onRemoveQuestion(section.clientId, q.clientId)}
                >
                  Retirer
                </Button>
              </div>
            </div>
            <Input
              placeholder="Libellé de la question"
              value={q.label}
              onChange={(e) =>
                onQuestionChange(section.clientId, q.clientId, { label: e.target.value })
              }
            />
            <Select
              value={q.question_type}
              onValueChange={(v) =>
                onQuestionChange(section.clientId, q.clientId, {
                  question_type: v as QuestionType,
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Type de réponse" />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(QUESTION_TYPE_LABELS) as QuestionType[]).map((k) => (
                  <SelectItem key={k} value={k}>
                    {QUESTION_TYPE_LABELS[k]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {(q.question_type === "single_select" || q.question_type === "multi_select") && (
              <div className="space-y-1">
                <Label className="text-xs">Options (JSON ou une option par ligne)</Label>
                <Input
                  placeholder='["A","B"] ou une ligne par choix'
                  value={q.optionsText}
                  onChange={(e) =>
                    onQuestionChange(section.clientId, q.clientId, {
                      optionsText: e.target.value,
                    })
                  }
                />
              </div>
            )}
            <div className="flex flex-wrap gap-6 items-center">
              <div className="flex items-center gap-2">
                <Switch
                  id={`req-${q.clientId}`}
                  checked={q.is_required}
                  onCheckedChange={(c) =>
                    onQuestionChange(section.clientId, q.clientId, { is_required: !!c })
                  }
                />
                <Label htmlFor={`req-${q.clientId}`} className="text-sm font-normal">
                  Obligatoire
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id={`self-${q.clientId}`}
                  checked={q.is_self_evaluation}
                  onCheckedChange={(c) =>
                    onQuestionChange(section.clientId, q.clientId, {
                      is_self_evaluation: !!c,
                    })
                  }
                />
                <Label htmlFor={`self-${q.clientId}`} className="text-sm font-normal">
                  Auto-évaluation
                </Label>
              </div>
            </div>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onAddQuestion(section.clientId)}
        >
          <Plus className="h-4 w-4 mr-1" />
          Ajouter une question
        </Button>
      </div>
    </div>
  );
}

export default function InterviewTemplatesTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? "";

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editing, setEditing] = useState<InterviewTemplate | null>(null);
  const [name, setName] = useState("");
  const [interviewType, setInterviewType] = useState<InterviewType>("annual_performance");
  const [sections, setSections] = useState<LocalSection[]>([]);
  const [archiveTarget, setArchiveTarget] = useState<InterviewTemplate | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const {
    data: templates = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["interview-templates", activeCompanyId],
    queryFn: async () => {
      const res = await getTemplates();
      return res.data;
    },
    enabled: !!activeCompanyId,
  });

  const filtered = useMemo(() => {
    if (statusFilter === "all") return templates;
    return templates.filter((t) => t.status === statusFilter);
  }, [templates, statusFilter]);

  const resetForm = useCallback(() => {
    setEditing(null);
    setName("");
    setInterviewType("annual_performance");
    setSections([]);
  }, []);

  const openCreate = () => {
    resetForm();
    setSheetOpen(true);
  };

  const openEdit = (t: InterviewTemplate) => {
    setEditing(t);
    setName(t.name);
    setInterviewType(t.interview_type);
    setSections(templateToLocal(t));
    setSheetOpen(true);
  };

  useEffect(() => {
    if (!sheetOpen) resetForm();
  }, [sheetOpen, resetForm]);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["interview-templates", activeCompanyId] });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payloadSections = localToPayload(sections);
      if (!name.trim()) throw new Error("Le nom est obligatoire.");
      try {
        if (editing) {
          await updateTemplate(editing.id, {
            name: name.trim(),
            sections: payloadSections,
          });
        } else {
          await createTemplate({
            name: name.trim(),
            interview_type: interviewType,
            sections: payloadSections,
          });
        }
      } catch (e: unknown) {
        const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data
          ?.detail;
        throw new Error(typeof d === "string" ? d : "Enregistrement impossible.");
      }
    },
    onSuccess: () => {
      invalidate();
      toast({
        title: editing ? "Modèle mis à jour" : "Modèle créé",
        description: "Les modifications ont été enregistrées.",
      });
      setSheetOpen(false);
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Enregistrement impossible.",
        variant: "destructive",
      });
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: (id: string) => duplicateTemplate(id),
    onSuccess: () => {
      invalidate();
      toast({ title: "Modèle dupliqué", description: "Une copie a été créée." });
    },
    onError: (err: Error) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        err?.message ??
        "Duplication impossible.";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => archiveTemplate(id),
    onSuccess: () => {
      invalidate();
      toast({ title: "Modèle archivé", description: "Le modèle n'est plus proposé par défaut." });
      setArchiveTarget(null);
    },
    onError: (err: Error) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        err?.message ??
        "Archivage impossible.";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    },
  });

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setSections((prev) => {
      const oldIndex = prev.findIndex((s) => s.clientId === active.id);
      const newIndex = prev.findIndex((s) => s.clientId === over.id);
      if (oldIndex < 0 || newIndex < 0) return prev;
      return arrayMove(prev, oldIndex, newIndex);
    });
  };

  const addSection = () => {
    setSections((prev) => [
      ...prev,
      { clientId: newClientId(), title: "", questions: [] },
    ]);
  };

  const addQuestion = (sectionId: string) => {
    setSections((prev) =>
      prev.map((s) =>
        s.clientId === sectionId
          ? {
              ...s,
              questions: [
                ...s.questions,
                {
                  clientId: newClientId(),
                  label: "",
                  question_type: "text" as QuestionType,
                  optionsText: "",
                  is_required: false,
                  is_self_evaluation: false,
                },
              ],
            }
          : s
      )
    );
  };

  const onSectionTitle = (id: string, title: string) => {
    setSections((prev) => prev.map((s) => (s.clientId === id ? { ...s, title } : s)));
  };

  const removeSection = (id: string) => {
    setSections((prev) => prev.filter((s) => s.clientId !== id));
  };

  const onQuestionChange = (sectionId: string, qid: string, patch: Partial<LocalQuestion>) => {
    setSections((prev) =>
      prev.map((s) =>
        s.clientId !== sectionId
          ? s
          : {
              ...s,
              questions: s.questions.map((q) =>
                q.clientId === qid ? { ...q, ...patch } : q
              ),
            }
      )
    );
  };

  const moveQuestion = (sectionId: string, qid: string, dir: -1 | 1) => {
    setSections((prev) =>
      prev.map((s) => {
        if (s.clientId !== sectionId) return s;
        const i = s.questions.findIndex((q) => q.clientId === qid);
        const j = i + dir;
        if (i < 0 || j < 0 || j >= s.questions.length) return s;
        return { ...s, questions: arrayMove(s.questions, i, j) };
      })
    );
  };

  const removeQuestion = (sectionId: string, qid: string) => {
    setSections((prev) =>
      prev.map((s) =>
        s.clientId !== sectionId
          ? s
          : { ...s, questions: s.questions.filter((q) => q.clientId !== qid) }
      )
    );
  };

  const errMsg = isError
    ? (error as Error)?.message ?? "Impossible de charger les modèles."
    : null;

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-blue-200 bg-blue-50/80 px-4 py-3 text-sm text-blue-950 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-100">
        <p className="font-medium">Paramétrage recommandé</p>
        <p className="mt-1 text-blue-900/90 dark:text-blue-100/90">
          Créez un modèle <strong>actif</strong> par type d&apos;entretien (cadres, forfait jour,
          entretien pro 2 ans, bilan 6 ans, reprise d&apos;absence…). Lors de la planification, le
          modèle correspondant est proposé automatiquement. Recopiez le contenu de vos documents Word
          existants section par section.
        </p>
      </div>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Modèles de trames</h2>
          <p className="text-sm text-muted-foreground">
            Trames réutilisables pour préparer et conduire les entretiens.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 justify-end">
          <Select
            value={statusFilter}
            onValueChange={(v) => setStatusFilter(v as StatusFilter)}
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="Statut" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous</SelectItem>
              <SelectItem value="active">Actifs</SelectItem>
              <SelectItem value="archived">Archivés</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-2" />
            Créer un modèle
          </Button>
        </div>
      </div>

      {errMsg && (
        <div
          role="alert"
          className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {errMsg}
          <Button variant="link" className="ml-2 h-auto p-0 text-destructive" onClick={() => refetch()}>
            Réessayer
          </Button>
        </div>
      )}

      <div className="rounded-md border">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-sm">
            {templates.length === 0
              ? "Aucun modèle pour cette entreprise. Créez votre premier modèle."
              : "Aucun modèle ne correspond au filtre."}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nom</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Sections</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-medium">{row.name}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {INTERVIEW_TYPE_LABELS[row.interview_type] ?? row.interview_type}
                  </TableCell>
                  <TableCell>{row.sections?.length ?? 0}</TableCell>
                  <TableCell>
                    <Badge variant={row.status === "active" ? "default" : "secondary"}>
                      {row.status === "active" ? "Actif" : "Archivé"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button variant="ghost" size="sm" onClick={() => openEdit(row)}>
                      <Pencil className="h-4 w-4 mr-1" />
                      Modifier
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => duplicateMutation.mutate(row.id)}
                      disabled={duplicateMutation.isPending}
                    >
                      <Copy className="h-4 w-4 mr-1" />
                      Dupliquer
                    </Button>
                    {row.status === "active" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        onClick={() => setArchiveTarget(row)}
                      >
                        <Archive className="h-4 w-4 mr-1" />
                        Archiver
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="w-full sm:max-w-xl overflow-y-auto flex flex-col">
          <SheetHeader>
            <SheetTitle>{editing ? "Modifier le modèle" : "Créer un modèle"}</SheetTitle>
          </SheetHeader>
          <div className="flex-1 space-y-4 py-4">
            <div className="space-y-2">
              <Label>Nom *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex. Entretien annuel 2026" />
            </div>
            {!editing && (
              <div className="space-y-2">
                <Label>Type d&apos;entretien *</Label>
                <Select
                  value={interviewType}
                  onValueChange={(v) => setInterviewType(v as InterviewType)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(INTERVIEW_TYPE_LABELS) as InterviewType[]).map((k) => (
                      <SelectItem key={k} value={k}>
                        {INTERVIEW_TYPE_LABELS[k]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {editing && (
              <p className="text-xs text-muted-foreground">
                Le type d&apos;entretien ne peut pas être modifié après création. Dupliquez le modèle pour en changer.
              </p>
            )}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Sections et questions</Label>
                <Button type="button" variant="outline" size="sm" onClick={addSection}>
                  <Plus className="h-4 w-4 mr-1" />
                  Ajouter une section
                </Button>
              </div>
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                <SortableContext
                  items={sections.map((s) => s.clientId)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="space-y-3">
                    {sections.map((s, i) => (
                      <SortableSectionCard
                        key={s.clientId}
                        section={s}
                        index={i}
                        onTitleChange={onSectionTitle}
                        onRemoveSection={removeSection}
                        onAddQuestion={addQuestion}
                        onQuestionChange={onQuestionChange}
                        onMoveQuestion={moveQuestion}
                        onRemoveQuestion={removeQuestion}
                      />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            </div>
          </div>
          <SheetFooter className="gap-2 sm:justify-end border-t pt-4">
            <Button variant="outline" onClick={() => setSheetOpen(false)}>
              Annuler
            </Button>
            <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Enregistrer
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <AlertDialog open={!!archiveTarget} onOpenChange={(o) => !o && setArchiveTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archiver ce modèle ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le modèle « {archiveTarget?.name} » sera marqué comme archivé. Cette action est impossible si un
              entretien est encore lié à ce modèle.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => archiveTarget && archiveMutation.mutate(archiveTarget.id)}
            >
              Archiver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
