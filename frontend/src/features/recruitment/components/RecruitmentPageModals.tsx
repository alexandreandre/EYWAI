import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, AlertTriangle, UserPlus } from "lucide-react";
import type { Job } from "@/api/recruitment";
import type { RecruitmentPageModel } from "@/features/recruitment/hooks/useRecruitmentPageModel";

type Props = Pick<
  RecruitmentPageModel,
  | "navigate"
  | "showCreateJob"
  | "setShowCreateJob"
  | "newJob"
  | "setNewJob"
  | "createJobMutation"
  | "showEditJob"
  | "setShowEditJob"
  | "editJob"
  | "setEditJob"
  | "updateJobMutation"
  | "showCreateCandidate"
  | "setShowCreateCandidate"
  | "newCandidateJobId"
  | "setNewCandidateJobId"
  | "activeJobs"
  | "newCandidate"
  | "setNewCandidate"
  | "createCandidateMutation"
  | "showRejectModal"
  | "setShowRejectModal"
  | "rejectReason"
  | "setRejectReason"
  | "rejectDetail"
  | "setRejectDetail"
  | "rejectionReasons"
  | "rejectCandidateId"
  | "rejectStageId"
  | "setRejectCandidateId"
  | "setRejectStageId"
  | "moveCandidateMutation"
  | "showHireModal"
  | "setShowHireModal"
  | "hireData"
  | "setHireData"
  | "hireJobTitle"
  | "hireCandidateId"
  | "setHireCandidateId"
  | "servicesQuery"
  | "hireMutation"
  | "hireSuccessInfo"
  | "setHireSuccessInfo"
  | "showDuplicateEmployeeModal"
  | "setShowDuplicateEmployeeModal"
  | "duplicateEmployeeInfo"
  | "setDuplicateEmployeeInfo"
  | "showInterviewModal"
  | "setShowInterviewModal"
  | "interviewData"
  | "setInterviewData"
  | "interviewParticipantIds"
  | "setInterviewParticipantIds"
  | "interviewCompanyUsers"
  | "loadingInterviewCompanyUsers"
  | "createInterviewMutation"
>;

export function RecruitmentPageModals({
  navigate,
  showCreateJob,
  setShowCreateJob,
  newJob,
  setNewJob,
  createJobMutation,
  showEditJob,
  setShowEditJob,
  editJob,
  setEditJob,
  updateJobMutation,
  showCreateCandidate,
  setShowCreateCandidate,
  newCandidateJobId,
  setNewCandidateJobId,
  activeJobs,
  newCandidate,
  setNewCandidate,
  createCandidateMutation,
  showRejectModal,
  setShowRejectModal,
  rejectReason,
  setRejectReason,
  rejectDetail,
  setRejectDetail,
  rejectionReasons,
  rejectCandidateId,
  rejectStageId,
  setRejectCandidateId,
  setRejectStageId,
  moveCandidateMutation,
  showHireModal,
  setShowHireModal,
  hireData,
  setHireData,
  hireJobTitle,
  hireCandidateId,
  setHireCandidateId,
  servicesQuery,
  hireMutation,
  hireSuccessInfo,
  setHireSuccessInfo,
  showDuplicateEmployeeModal,
  setShowDuplicateEmployeeModal,
  duplicateEmployeeInfo,
  setDuplicateEmployeeInfo,
  showInterviewModal,
  setShowInterviewModal,
  interviewData,
  setInterviewData,
  interviewParticipantIds,
  setInterviewParticipantIds,
  interviewCompanyUsers,
  loadingInterviewCompanyUsers,
  createInterviewMutation,
}: Props) {
  return (
    <>
      <Dialog open={showCreateJob} onOpenChange={setShowCreateJob}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nouveau poste</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Titre du poste *</Label>
              <Input
                value={newJob.title}
                onChange={(e) => setNewJob({ ...newJob, title: e.target.value })}
                placeholder="Ex: Développeur Full Stack"
              />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea
                value={newJob.description}
                onChange={(e) => setNewJob({ ...newJob, description: e.target.value })}
                placeholder="Description du poste..."
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label>Localisation</Label>
                <Input
                  value={newJob.location}
                  onChange={(e) => setNewJob({ ...newJob, location: e.target.value })}
                  placeholder="Paris"
                />
              </div>
              <div>
                <Label>Type de contrat</Label>
                <Select
                  value={newJob.contract_type}
                  onValueChange={(v) => setNewJob({ ...newJob, contract_type: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["CDI", "CDD", "Alternance", "Stage", "Intérim", "Freelance", "Autre"].map(
                      (t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ),
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateJob(false)}>
              Annuler
            </Button>
            <Button
              onClick={() => createJobMutation.mutate()}
              disabled={!newJob.title.trim() || createJobMutation.isPending}
            >
              {createJobMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Créer le poste
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showEditJob} onOpenChange={setShowEditJob}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Modifier le poste</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Titre du poste *</Label>
              <Input
                value={editJob.title}
                onChange={(e) => setEditJob({ ...editJob, title: e.target.value })}
              />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea
                value={editJob.description}
                onChange={(e) => setEditJob({ ...editJob, description: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label>Localisation</Label>
                <Input
                  value={editJob.location}
                  onChange={(e) => setEditJob({ ...editJob, location: e.target.value })}
                />
              </div>
              <div>
                <Label>Type de contrat</Label>
                <Select
                  value={editJob.contract_type}
                  onValueChange={(v) => setEditJob({ ...editJob, contract_type: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["CDI", "CDD", "Alternance", "Stage", "Intérim", "Freelance", "Autre"].map(
                      (t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ),
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label>Statut</Label>
              <Select
                value={editJob.status}
                onValueChange={(v) => setEditJob({ ...editJob, status: v as Job["status"] })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Actif</SelectItem>
                  <SelectItem value="draft">Brouillon</SelectItem>
                  <SelectItem value="archived">Archivé</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditJob(false)}>
              Annuler
            </Button>
            <Button
              onClick={() => updateJobMutation.mutate()}
              disabled={!editJob.title.trim() || updateJobMutation.isPending}
            >
              {updateJobMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showCreateCandidate} onOpenChange={setShowCreateCandidate}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nouveau candidat</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Poste *</Label>
              <Select value={newCandidateJobId} onValueChange={setNewCandidateJobId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir un poste" />
                </SelectTrigger>
                <SelectContent>
                  {activeJobs.map((j) => (
                    <SelectItem key={j.id} value={j.id} textValue={j.title}>
                      {j.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label>Prénom *</Label>
                <Input
                  value={newCandidate.first_name}
                  onChange={(e) =>
                    setNewCandidate({ ...newCandidate, first_name: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Nom *</Label>
                <Input
                  value={newCandidate.last_name}
                  onChange={(e) => setNewCandidate({ ...newCandidate, last_name: e.target.value })}
                />
              </div>
            </div>
            <div>
              <Label>Email</Label>
              <Input
                type="email"
                value={newCandidate.email}
                onChange={(e) => setNewCandidate({ ...newCandidate, email: e.target.value })}
              />
            </div>
            <div>
              <Label>Téléphone</Label>
              <Input
                value={newCandidate.phone}
                onChange={(e) => setNewCandidate({ ...newCandidate, phone: e.target.value })}
              />
            </div>
            <div>
              <Label>Source</Label>
              <Input
                value={newCandidate.source}
                onChange={(e) => setNewCandidate({ ...newCandidate, source: e.target.value })}
                placeholder="LinkedIn, Indeed, Cooptation..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateCandidate(false)}>
              Annuler
            </Button>
            <Button
              onClick={() => createCandidateMutation.mutate()}
              disabled={
                !newCandidateJobId ||
                !newCandidate.first_name.trim() ||
                !newCandidate.last_name.trim() ||
                createCandidateMutation.isPending
              }
            >
              {createCandidateMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Ajouter le candidat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showRejectModal} onOpenChange={setShowRejectModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Refuser le candidat
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Motif de refus *</Label>
              <Select value={rejectReason} onValueChange={setRejectReason}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionner un motif" />
                </SelectTrigger>
                <SelectContent>
                  {(rejectionReasons?.reasons || []).map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {rejectReason === "Autre" && (
              <div>
                <Label>Précisez</Label>
                <Textarea value={rejectDetail} onChange={(e) => setRejectDetail(e.target.value)} />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowRejectModal(false);
                setRejectReason("");
                setRejectDetail("");
              }}
            >
              Annuler
            </Button>
            <Button
              variant="destructive"
              disabled={!rejectReason || moveCandidateMutation.isPending}
              onClick={() => {
                if (rejectCandidateId && rejectStageId) {
                  moveCandidateMutation.mutate({
                    candidateId: rejectCandidateId,
                    stageId: rejectStageId,
                    reason: rejectReason,
                    detail: rejectReason === "Autre" ? rejectDetail : undefined,
                  });
                  setShowRejectModal(false);
                  setRejectCandidateId(null);
                  setRejectStageId(null);
                  setRejectReason("");
                  setRejectDetail("");
                }
              }}
            >
              Confirmer le refus
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showHireModal} onOpenChange={setShowHireModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UserPlus className="h-5 w-5 text-green-600" />
              Marquer comme recruté — Créer le salarié
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Date d&apos;entrée *</Label>
              <Input
                type="date"
                value={hireData.hire_date}
                onChange={(e) => setHireData({ ...hireData, hire_date: e.target.value })}
              />
            </div>
            <div>
              <Label>Intitulé du poste</Label>
              <Input
                value={hireData.job_title}
                onChange={(e) => setHireData({ ...hireData, job_title: e.target.value })}
                placeholder={hireJobTitle}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label>Type de contrat</Label>
                <Select
                  value={hireData.contract_type}
                  onValueChange={(v) => setHireData({ ...hireData, contract_type: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["CDI", "CDD", "Alternance", "Stage", "Intérim"].map((t) => (
                      <SelectItem key={t} value={t}>
                        {t}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Établissement / Site</Label>
                <Input
                  value={hireData.site}
                  onChange={(e) => setHireData({ ...hireData, site: e.target.value })}
                  placeholder="Siège, Paris..."
                />
              </div>
            </div>
            <div>
              <Label>Service / Département</Label>
              <Select
                value={hireData.service_id ? hireData.service_id : "__none__"}
                onValueChange={(v) =>
                  setHireData({ ...hireData, service_id: v === "__none__" ? "" : v })
                }
                disabled={servicesQuery.isLoading}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Aucun service" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Aucun service</SelectItem>
                  {(servicesQuery.data ?? []).map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowHireModal(false);
                setHireCandidateId(null);
              }}
            >
              Annuler
            </Button>
            <Button
              className="bg-green-600 hover:bg-green-700"
              disabled={!hireData.hire_date || hireMutation.isPending}
              onClick={() => {
                if (hireCandidateId) {
                  hireMutation.mutate({ candidateId: hireCandidateId, data: hireData });
                }
              }}
            >
              {hireMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Créer le salarié
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!hireSuccessInfo}
        onOpenChange={(open) => {
          if (!open) setHireSuccessInfo(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Collaborateur embauché</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <p className="text-muted-foreground">
              Une checklist d&apos;onboarding a été créée. Le compte collaborateur est prêt.
            </p>
            {hireSuccessInfo?.generatedPassword && (
              <div className="rounded-lg border bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800 p-3 space-y-2">
                <p className="font-medium text-amber-900 dark:text-amber-100">
                  Identifiants de connexion (à transmettre une seule fois)
                </p>
                {hireSuccessInfo.username && (
                  <p>
                    <span className="text-muted-foreground">Nom d&apos;utilisateur : </span>
                    <span className="font-mono">{hireSuccessInfo.username}</span>
                  </p>
                )}
                {hireSuccessInfo.email && (
                  <p>
                    <span className="text-muted-foreground">Email : </span>
                    <span className="font-mono">{hireSuccessInfo.email}</span>
                  </p>
                )}
                <p>
                  <span className="text-muted-foreground">Mot de passe temporaire : </span>
                  <span className="font-mono font-semibold">{hireSuccessInfo.generatedPassword}</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  Le PDF « Identifiants de connexion » est disponible dans Documents → Autres.
                  Le collaborateur devra le changer à la première connexion.
                </p>
              </div>
            )}
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" type="button" onClick={() => setHireSuccessInfo(null)}>
              Fermer
            </Button>
            <Button
              type="button"
              onClick={() => {
                if (hireSuccessInfo?.employeeId) {
                  navigate(`/onboarding/${hireSuccessInfo.employeeId}`);
                  setHireSuccessInfo(null);
                }
              }}
            >
              Voir l&apos;onboarding
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showDuplicateEmployeeModal} onOpenChange={setShowDuplicateEmployeeModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Salarié existant détecté
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Un salarié avec cet email existe déjà dans votre entreprise :
            </p>
            {duplicateEmployeeInfo && (
              <div className="border rounded-lg p-3 bg-muted/50">
                <p className="text-sm font-medium">
                  {duplicateEmployeeInfo.first_name} {duplicateEmployeeInfo.last_name}
                </p>
                <p className="text-xs text-muted-foreground">{duplicateEmployeeInfo.email}</p>
              </div>
            )}
            <p className="text-sm">Que souhaitez-vous faire ?</p>
          </div>
          <DialogFooter className="flex flex-col gap-2 sm:flex-row">
            <Button
              variant="outline"
              className="flex-1"
              disabled={hireMutation.isPending}
              onClick={() => {
                if (hireCandidateId) {
                  hireMutation.mutate({
                    candidateId: hireCandidateId,
                    data: hireData,
                    skipDuplicateCheck: true,
                  });
                  setShowDuplicateEmployeeModal(false);
                  setDuplicateEmployeeInfo(null);
                }
              }}
            >
              {hireMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Créer une nouvelle fiche
            </Button>
            <Button
              className="flex-1 bg-green-600 hover:bg-green-700"
              disabled={hireMutation.isPending}
              onClick={() => {
                if (hireCandidateId && duplicateEmployeeInfo) {
                  hireMutation.mutate({
                    candidateId: hireCandidateId,
                    data: hireData,
                    linkToEmployeeId: duplicateEmployeeInfo.id,
                  });
                  setShowDuplicateEmployeeModal(false);
                  setDuplicateEmployeeInfo(null);
                }
              }}
            >
              {hireMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Lier au salarié existant
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showInterviewModal} onOpenChange={setShowInterviewModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Planifier un entretien</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Type d&apos;entretien</Label>
              <Select
                value={interviewData.interview_type}
                onValueChange={(v) => setInterviewData({ ...interviewData, interview_type: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[
                    "Entretien RH",
                    "Entretien technique",
                    "Entretien manager",
                    "Entretien final",
                    "Appel téléphonique",
                  ].map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Date et heure *</Label>
              <Input
                type="datetime-local"
                value={interviewData.scheduled_at}
                onChange={(e) =>
                  setInterviewData({ ...interviewData, scheduled_at: e.target.value })
                }
              />
            </div>
            <div>
              <Label>Durée (minutes)</Label>
              <Input
                type="number"
                value={interviewData.duration_minutes}
                onChange={(e) =>
                  setInterviewData({
                    ...interviewData,
                    duration_minutes: parseInt(e.target.value) || 60,
                  })
                }
              />
            </div>
            <div>
              <Label>Lieu</Label>
              <Input
                value={interviewData.location}
                onChange={(e) => setInterviewData({ ...interviewData, location: e.target.value })}
                placeholder="Bureau, salle de réunion..."
              />
            </div>
            <div>
              <Label>Lien visioconférence</Label>
              <Input
                value={interviewData.meeting_link}
                onChange={(e) =>
                  setInterviewData({ ...interviewData, meeting_link: e.target.value })
                }
                placeholder="https://meet.google.com/..."
              />
            </div>
            <div className="space-y-2">
              <Label>Participants</Label>
              <p className="text-xs text-muted-foreground">
                Utilisateurs invités comme intervieweurs (même liste que la gestion des
                utilisateurs).
              </p>
              <ScrollArea className="h-[200px] rounded-md border bg-muted/20">
                <div className="p-3 space-y-2">
                  {loadingInterviewCompanyUsers ? (
                    <>
                      <Skeleton className="h-9 w-full" />
                      <Skeleton className="h-9 w-full" />
                      <Skeleton className="h-9 w-full" />
                    </>
                  ) : interviewCompanyUsers.length === 0 ? (
                    <p className="text-xs text-muted-foreground py-2">
                      Aucun utilisateur chargé pour cette entreprise.
                    </p>
                  ) : (
                    interviewCompanyUsers.map((u) => {
                      const label =
                        `${u.first_name ?? ""} ${u.last_name ?? ""}`.trim() || u.email || u.id;
                      return (
                        <label
                          key={u.id}
                          htmlFor={`interview-participant-${u.id}`}
                          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted/80 cursor-pointer"
                        >
                          <Checkbox
                            id={`interview-participant-${u.id}`}
                            checked={interviewParticipantIds.includes(u.id)}
                            onCheckedChange={(checked) => {
                              setInterviewParticipantIds((prev) =>
                                checked === true
                                  ? prev.includes(u.id)
                                    ? prev
                                    : [...prev, u.id]
                                  : prev.filter((id) => id !== u.id),
                              );
                            }}
                          />
                          <span className="truncate">{label}</span>
                        </label>
                      );
                    })
                  )}
                </div>
              </ScrollArea>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowInterviewModal(false)}>
              Annuler
            </Button>
            <Button
              disabled={!interviewData.scheduled_at || createInterviewMutation.isPending}
              onClick={() => createInterviewMutation.mutate()}
            >
              {createInterviewMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Planifier
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
