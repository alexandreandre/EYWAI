// frontend/src/pages/PromotionDetail.tsx
// Page de détail d'une promotion

import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { PromotionBadge } from "@/components/PromotionBadge";
import { PromotionComparison } from "@/components/PromotionComparison";
import { PromotionTimeline } from "@/components/PromotionTimeline";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  getPromotion,
  approvePromotion,
  rejectPromotion,
  markPromotionEffective,
  deletePromotion,
  downloadPromotionDocument,
} from "@/api/promotions";
import { PromotionModal } from "@/components/PromotionModal";
import apiClient from "@/api/apiClient";
import {
  Loader2,
  ArrowLeft,
  Edit,
  Send,
  CheckCircle2,
  XCircle,
  Trash2,
  FileDown,
  RefreshCw,
  User,
  FileText,
  Clock,
  MessageSquare,
  Shield,
  Calendar,
} from "lucide-react";

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

const ROLE_LABELS: Record<string, string> = {
  collaborateur_rh: "Collaborateur RH",
  rh: "RH",
  admin: "Administrateur",
};

export default function PromotionDetail() {
  const { promotionId } = useParams<{ promotionId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // États pour les modals
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [approveDialogOpen, setApproveDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [markEffectiveDialogOpen, setMarkEffectiveDialogOpen] = useState(false);
  const [approveNotes, setApproveNotes] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [newNote, setNewNote] = useState("");

  // Charger la promotion
  const {
    data: promotion,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["promotion", promotionId],
    queryFn: async () => {
      const res = await getPromotion(promotionId!);
      return res.data;
    },
    enabled: !!promotionId,
  });

  // Charger les informations de l'employé
  const { data: employee } = useQuery({
    queryKey: ["employee", promotion?.employee_id],
    queryFn: async () => {
      if (!promotion?.employee_id) return null;
      const res = await apiClient.get(`/api/employees/${promotion.employee_id}`);
      return res.data;
    },
    enabled: !!promotion?.employee_id,
  });

  // Pour l'instant, on affiche simplement "Utilisateur" car l'endpoint /api/profiles n'existe pas
  // TODO: Modifier le backend pour inclure les noms dans la réponse de get_promotion_by_id
  const requestedByName = promotion?.requested_by ? "Utilisateur" : null;
  const approvedByName = promotion?.approved_by ? "Utilisateur" : null;

  // Mutations
  const approveMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      approvePromotion(id, notes ? { notes } : undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["promotion", promotionId] });
      queryClient.invalidateQueries({ queryKey: ["promotions"] });
      queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
      setApproveDialogOpen(false);
      setApproveNotes("");
      toast({
        title: "Promotion approuvée",
        description: "La promotion a été approuvée avec succès.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible d'approuver la promotion.",
        variant: "destructive",
      });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      rejectPromotion(id, { rejection_reason: reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["promotion", promotionId] });
      queryClient.invalidateQueries({ queryKey: ["promotions"] });
      queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
      setRejectDialogOpen(false);
      setRejectReason("");
      toast({
        title: "Promotion rejetée",
        description: "La promotion a été rejetée.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de rejeter la promotion.",
        variant: "destructive",
      });
    },
  });

  const markEffectiveMutation = useMutation({
    mutationFn: () => markPromotionEffective(promotionId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["promotion", promotionId] });
      queryClient.invalidateQueries({ queryKey: ["promotions"] });
      queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
      setMarkEffectiveDialogOpen(false);
      toast({
        title: "Promotion effective",
        description: "Les changements ont été appliqués avec succès.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de marquer la promotion comme effective.",
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deletePromotion(promotionId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["promotions"] });
      queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
      handleClose();
      toast({
        title: "Promotion supprimée",
        description: "La promotion a été supprimée avec succès.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de supprimer la promotion.",
        variant: "destructive",
      });
    },
  });

  const handleClose = () => {
    const returnTo = searchParams.get("returnTo");
    const employeeId = searchParams.get("employeeId");
    const tab = searchParams.get("tab");

    if (returnTo === "employee" && employeeId) {
      navigate(`/employees/${employeeId}${tab ? `?tab=${tab}` : ""}`);
    } else {
      navigate("/promotions");
    }
  };

  const handleApprove = () => {
    if (!promotionId) return;
    approveMutation.mutate({
      id: promotionId,
      notes: approveNotes || undefined,
    });
  };

  const handleReject = () => {
    if (!promotionId || !rejectReason.trim()) {
      toast({
        title: "Champ requis",
        description: "Veuillez saisir une raison de rejet.",
        variant: "destructive",
      });
      return;
    }
    rejectMutation.mutate({
      id: promotionId,
      reason: rejectReason,
    });
  };

  const handleDownloadDocument = async () => {
    if (!promotionId) return;
    try {
      const url = await downloadPromotionDocument(promotionId);
      window.open(url, "_blank");
    } catch (error: unknown) {
      const message =
        error && typeof error === "object" && "message" in error
          ? String((error as { message: string }).message)
          : "Impossible de télécharger le document.";
      toast({
        title: "Erreur",
        description: message,
        variant: "destructive",
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError || !promotion) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={handleClose}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour
        </Button>
        <Card>
          <CardContent className="pt-6">
            <p className="text-destructive">Erreur lors du chargement de la promotion.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const canEdit = promotion.status === "draft" || promotion.status === "pending_approval";
  const canApprove = promotion.status === "pending_approval";
  const canReject = promotion.status === "pending_approval";
  const canMarkEffective = promotion.status === "approved";
  const canDelete = promotion.status === "draft" || promotion.status === "pending_approval";
  const hasDocument = !!promotion.promotion_letter_url;

  const employeeName = employee
    ? `${employee.first_name || ""} ${employee.last_name || ""}`.trim()
    : "Employé";
  const employeeInitials = employee
    ? `${employee.first_name?.charAt(0) || ""}${employee.last_name?.charAt(0) || ""}`.toUpperCase()
    : "??";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between border-b pb-4">
        <div className="flex items-start gap-4 flex-1">
          <Button variant="ghost" size="sm" onClick={handleClose} className="mt-1">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold text-foreground">
              Détails de la promotion
            </h1>
            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
              <span>Date d'effet : {formatDate(promotion.effective_date)}</span>
              {promotion.request_date && (
                <span>Demandé le : {formatDate(promotion.request_date)}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <PromotionBadge status={promotion.status} />
          {canEdit && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditModalOpen(true)}
            >
              <Edit className="h-4 w-4 mr-2" />
              Modifier
            </Button>
          )}
        </div>
      </div>

      {/* Actions rapides selon le statut */}
      {(canApprove || canReject || canMarkEffective) && (
        <Card className="border-l-4 border-l-primary">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <Clock className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="font-semibold">Actions disponibles</p>
                  <p className="text-sm text-muted-foreground">
                    {canApprove && "Approuvez ou rejetez cette promotion"}
                    {canMarkEffective && "Marquez cette promotion comme effective pour appliquer les changements"}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                {canApprove && (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => setApproveDialogOpen(true)}
                      className="text-green-600 border-green-600 hover:bg-green-50"
                    >
                      <CheckCircle2 className="h-4 w-4 mr-2" />
                      Approuver
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setRejectDialogOpen(true)}
                      className="text-red-600 border-red-600 hover:bg-red-50"
                    >
                      <XCircle className="h-4 w-4 mr-2" />
                      Rejeter
                    </Button>
                  </>
                )}
                {canMarkEffective && (
                  <Button
                    onClick={() => setMarkEffectiveDialogOpen(true)}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    Marquer comme effective
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Onglets */}
      <Tabs defaultValue="general" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="general">
            <User className="mr-2 h-4 w-4" />
            Informations
          </TabsTrigger>
          <TabsTrigger value="workflow">
            <Clock className="mr-2 h-4 w-4" />
            Workflow
          </TabsTrigger>
          <TabsTrigger value="documents">
            <FileText className="mr-2 h-4 w-4" />
            Documents
          </TabsTrigger>
          <TabsTrigger value="notes">
            <MessageSquare className="mr-2 h-4 w-4" />
            Notes
          </TabsTrigger>
        </TabsList>

        {/* Onglet 1 : Informations générales */}
        <TabsContent value="general" className="space-y-4">
          {/* Card Résumé */}
          <Card>
            <CardHeader>
              <CardTitle>Résumé</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-4">
                <Avatar className="h-16 w-16">
                  <AvatarFallback className="text-xl">{employeeInitials}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-semibold text-lg">{employeeName}</p>
                  {employee?.job_title && (
                    <p className="text-sm text-muted-foreground">{employee.job_title}</p>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                <div>
                  <p className="text-sm text-muted-foreground">Type</p>
                  <PromotionBadge type={promotion.promotion_type} variant="type" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Statut</p>
                  <PromotionBadge status={promotion.status} />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Date d'effet</p>
                  <p className="font-medium">{formatDate(promotion.effective_date)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Date de demande</p>
                  <p className="font-medium">{formatDate(promotion.request_date)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Card Évolution */}
          <PromotionComparison promotion={promotion} />

          {/* Card Accès RH si applicable */}
          {promotion.grant_rh_access && promotion.new_rh_access && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  Accès RH
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Rôle précédent</p>
                    <p className="font-medium">
                      {promotion.previous_rh_access
                        ? ROLE_LABELS[promotion.previous_rh_access] || promotion.previous_rh_access
                        : "Aucun accès RH"}
                    </p>
                  </div>
                  <div className="text-muted-foreground">→</div>
                  <div>
                    <p className="text-sm text-muted-foreground">Nouveau rôle</p>
                    <p className="font-medium text-green-600">
                      {ROLE_LABELS[promotion.new_rh_access] || promotion.new_rh_access}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Card Justification */}
          <Card>
            <CardHeader>
              <CardTitle>Justification</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {promotion.reason && (
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Raison</p>
                  <p className="font-medium">{promotion.reason}</p>
                </div>
              )}
              {promotion.justification && (
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Justification détaillée</p>
                  <p className="whitespace-pre-wrap">{promotion.justification}</p>
                </div>
              )}
              {promotion.performance_review_id && (
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Entretien annuel lié</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    onClick={() =>
                      navigate(`/annual-reviews/${promotion.performance_review_id}`)
                    }
                  >
                    <MessageSquare className="h-4 w-4" />
                    Voir l'entretien
                  </Button>
                </div>
              )}
              {!promotion.reason && !promotion.justification && (
                <p className="text-sm text-muted-foreground">Aucune justification renseignée.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Onglet 2 : Workflow */}
        <TabsContent value="workflow" className="space-y-4">
          <PromotionTimeline promotion={promotion} />

          {/* Card Demandeur */}
          {promotion.requested_by && (
            <Card>
              <CardHeader>
                <CardTitle>Demandeur</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="font-medium">
                  {requestedByName || "Utilisateur"}
                </p>
                {promotion.request_date && (
                  <p className="text-sm text-muted-foreground mt-1">
                    Le {formatDate(promotion.request_date)}
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Card Validation */}
          {(promotion.approved_by || promotion.rejection_reason) && (
            <Card>
              <CardHeader>
                <CardTitle>Validation</CardTitle>
              </CardHeader>
              <CardContent>
                {promotion.approved_by && (
                  <div className="space-y-2">
                    <p className="font-medium text-green-600">
                      Approuvée par {approvedByName || "Utilisateur"}
                    </p>
                    {promotion.approved_at && (
                      <p className="text-sm text-muted-foreground">
                        Le {formatDateTime(promotion.approved_at)}
                      </p>
                    )}
                  </div>
                )}
                {promotion.rejection_reason && (
                  <div className="space-y-2">
                    <p className="font-medium text-red-600">Rejetée</p>
                    <p className="text-sm">{promotion.rejection_reason}</p>
                    {promotion.updated_at && (
                      <p className="text-sm text-muted-foreground">
                        Le {formatDateTime(promotion.updated_at)}
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Onglet 3 : Documents */}
        <TabsContent value="documents" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Document de promotion</CardTitle>
              <CardDescription>
                Lettre de promotion générée automatiquement lors de l'approbation
              </CardDescription>
            </CardHeader>
            <CardContent>
              {hasDocument ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-4 p-4 border rounded-lg">
                    <FileText className="h-8 w-8 text-muted-foreground" />
                    <div className="flex-1">
                      <p className="font-medium">Lettre de promotion</p>
                      <p className="text-sm text-muted-foreground">
                        Document généré le {formatDate(promotion.approved_at)}
                      </p>
                    </div>
                    <Button onClick={handleDownloadDocument} variant="outline">
                      <FileDown className="h-4 w-4 mr-2" />
                      Télécharger
                    </Button>
                  </div>
                  {promotion.status === "approved" && (
                    <Button
                      variant="outline"
                      onClick={async () => {
                        try {
                          // Régénérer le document en réapprouvant (sans changer le statut)
                          // Ou créer un endpoint dédié pour régénérer
                          toast({
                            title: "Information",
                            description:
                              "La régénération du document sera disponible prochainement.",
                          });
                        } catch (error) {
                          toast({
                            title: "Erreur",
                            description: "Impossible de régénérer le document.",
                            variant: "destructive",
                          });
                        }
                      }}
                    >
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Régénérer le document
                    </Button>
                  )}
                </div>
              ) : (
                <div className="text-center py-8">
                  <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <p className="font-medium mb-1">Aucun document disponible</p>
                  <p className="text-sm text-muted-foreground">
                    {promotion.status === "approved"
                      ? "Le document sera généré automatiquement lors de l'approbation."
                      : "Le document sera généré une fois la promotion approuvée."}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Onglet 4 : Notes internes */}
        <TabsContent value="notes" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Notes internes RH</CardTitle>
              <CardDescription>
                Notes privées visibles uniquement par les RH et administrateurs
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Liste des notes */}
              {promotion.notes && promotion.notes.length > 0 ? (
                <div className="space-y-3">
                  {promotion.notes.map((note, index) => (
                    <div
                      key={index}
                      className="p-4 border rounded-lg bg-muted/30"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <p className="text-sm font-medium">
                          {note.type === "approval_note" ? "Note d'approbation" : "Note"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatDateTime(note.timestamp)}
                        </p>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{note.content}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  Aucune note pour le moment.
                </p>
              )}

              {/* Formulaire pour ajouter une note */}
              {canEdit && (
                <div className="pt-4 border-t space-y-2">
                  <Label htmlFor="new-note">Ajouter une note</Label>
                  <Textarea
                    id="new-note"
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    placeholder="Ajoutez une note interne..."
                    rows={3}
                  />
                  <Button
                    size="sm"
                    onClick={async () => {
                      if (!newNote.trim() || !promotionId) return;
                      try {
                        // Ajouter la note via l'approbation avec notes
                        // Pour l'instant, on peut utiliser approve avec notes même si déjà approuvé
                        // Ou créer un endpoint dédié pour ajouter des notes
                        toast({
                          title: "Information",
                          description:
                            "L'ajout de notes sera disponible prochainement.",
                        });
                        setNewNote("");
                      } catch (error) {
                        toast({
                          title: "Erreur",
                          description: "Impossible d'ajouter la note.",
                          variant: "destructive",
                        });
                      }
                    }}
                    disabled={!newNote.trim()}
                  >
                    Ajouter
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Dialog d'approbation */}
      <Dialog open={approveDialogOpen} onOpenChange={setApproveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approuver la promotion</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="approve-notes">Notes (optionnel)</Label>
              <Textarea
                id="approve-notes"
                placeholder="Ajoutez des notes pour cette approbation..."
                value={approveNotes}
                onChange={(e) => setApproveNotes(e.target.value)}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setApproveDialogOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleApprove} disabled={approveMutation.isPending}>
              {approveMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Approuver
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog de rejet */}
      <Dialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rejeter la promotion</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="reject-reason">Raison du rejet *</Label>
              <Textarea
                id="reject-reason"
                placeholder="Expliquez la raison du rejet..."
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                rows={4}
                required
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectDialogOpen(false)}>
              Annuler
            </Button>
            <Button
              onClick={handleReject}
              disabled={rejectMutation.isPending || !rejectReason.trim()}
              variant="destructive"
            >
              {rejectMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Rejeter
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog marquer comme effective */}
      <AlertDialog open={markEffectiveDialogOpen} onOpenChange={setMarkEffectiveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Marquer comme effective</AlertDialogTitle>
            <AlertDialogDescription>
              Êtes-vous sûr de vouloir marquer cette promotion comme effective ? Les changements
              seront appliqués à l'employé (poste, salaire, statut, classification, accès RH).
              Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => markEffectiveMutation.mutate()}
              disabled={markEffectiveMutation.isPending}
              className="bg-green-600 hover:bg-green-700"
            >
              {markEffectiveMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Confirmer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dialog de suppression */}
      {canDelete && (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive" className="mt-4">
              <Trash2 className="h-4 w-4 mr-2" />
              Supprimer
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Supprimer la promotion</AlertDialogTitle>
              <AlertDialogDescription>
                Êtes-vous sûr de vouloir supprimer cette promotion ? Cette action est
                irréversible.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Annuler</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {deleteMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                Supprimer
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}

      {/* Modal d'édition */}
      <PromotionModal
        isOpen={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        promotion={promotion}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["promotion", promotionId] });
          queryClient.invalidateQueries({ queryKey: ["promotions"] });
          queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
          setEditModalOpen(false);
        }}
      />
    </div>
  );
}
