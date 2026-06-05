// frontend/src/components/CollectiveAgreementCard.tsx

import { log } from '@/lib/logger';
import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/use-toast';
import { Building, FileText, Loader2, Plus, MessageSquare, Send } from 'lucide-react';
import * as collectiveAgreementsApi from '@/api/collectiveAgreements';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';
import { CollectiveAgreementRow } from '@/components/collective-agreements/CollectiveAgreementRow';
import { ConventionDocumentViewerDialog } from '@/components/collective-agreements/ConventionDocumentViewerDialog';
import type { DocumentLoadingKind } from '@/components/collective-agreements/CollectiveAgreementRow';
import { formatCatalogConventionName } from '@/lib/collectiveAgreementDisplay';
import {
  getReadinessFromRulesStatus,
  getPayrollGridUnavailableReason,
  hasCachedTextFromSource,
  hasPayrollGridFromRules,
  extractLegifranceUrlFromDescription,
} from '@/lib/collectiveAgreementReadiness';
import { printRulesPdfFromJson } from '@/lib/collectiveAgreementRulesPdf';
import { useConventionDocumentViewer } from '@/hooks/useConventionDocumentViewer';
import type { ConventionDocumentKind } from '@/lib/collectiveAgreementDocumentCache';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { CollectiveAgreementAssignDialog } from '@/components/collective-agreements/CollectiveAgreementAssignDialog';

export type CollectiveAgreementCardProps = {
  /** Entreprise cible (fiche admin). Sinon entreprise active du contexte RH. */
  companyId?: string;
  companyName?: string;
};

export default function CollectiveAgreementCard({
  companyId: companyIdProp,
  companyName: companyNameProp,
}: CollectiveAgreementCardProps = {}) {
  const { toast } = useToast();
  const activeCompanyId = useActiveCompanyId();
  const companyId = companyIdProp ?? activeCompanyId;
  const companyName = companyNameProp;
  const { viewer, openDocument, closeViewer, downloadFromViewer } =
    useConventionDocumentViewer();

  const [assignments, setAssignments] = useState<
    collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]
  >([]);
  const [rulesStatusMap, setRulesStatusMap] = useState<
    Record<string, collectiveAgreementsApi.RulesStatusResponse>
  >({});
  const [docLoading, setDocLoading] = useState<{
    id: string;
    kind: DocumentLoadingKind;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [isModalOpen, setIsModalOpen] = useState(false);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [assignmentToDelete, setAssignmentToDelete] =
    useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails | null>(null);

  const [isChatOpen, setIsChatOpen] = useState(false);
  const [selectedAgreementForChat, setSelectedAgreementForChat] =
    useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails | null>(null);
  const [chatQuestion, setChatQuestion] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);

  interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
  }
  const [conversationHistory, setConversationHistory] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversationHistory]);

  const loadRulesStatus = async (
    items: collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]
  ) => {
    const results = await Promise.allSettled(
      items.map((item) =>
        collectiveAgreementsApi.getRulesStatus(item.collective_agreement_id)
      )
    );
    const map: Record<string, collectiveAgreementsApi.RulesStatusResponse> = {};
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        map[items[index].collective_agreement_id] = result.value.data;
      }
    });
    setRulesStatusMap(map);
  };

  const fetchAssignments = async (targetCompanyId?: string) => {
    const scopedCompanyId = targetCompanyId ?? companyId;
    if (!scopedCompanyId) {
      setAssignments([]);
      setRulesStatusMap({});
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const response = await collectiveAgreementsApi.getMyCompanyAgreements(scopedCompanyId);
      const data = response.data || [];
      setAssignments(data);
      if (data.length > 0) {
        await loadRulesStatus(data);
      } else {
        setRulesStatusMap({});
      }
    } catch (err: unknown) {
      log.error('Erreur lors de la récupération des conventions assignées:', err);
      setAssignments([]);
      setRulesStatusMap({});
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void fetchAssignments(companyId);
  }, [companyId]);

  const handleOpenModal = () => {
    if (!companyId) {
      toast({
        title: 'Entreprise requise',
        description: 'Sélectionnez une entreprise du groupe pour assigner une convention.',
        variant: 'destructive',
      });
      return;
    }
    setIsModalOpen(true);
  };

  const handleDownloadSource = (
    assignment: collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails
  ) => {
    const pdfUrl = assignment.agreement_details?.rules_pdf_url;
    if (!pdfUrl) {
      toast({
        title: 'Erreur',
        description: 'Aucun fichier PDF disponible pour cette convention.',
        variant: 'destructive',
      });
      return;
    }
    window.open(pdfUrl, '_blank');
  };

  const handleViewDocument = async (
    assignment: collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails,
    kind: ConventionDocumentKind
  ) => {
    const agreementId = assignment.agreement_details?.id;
    if (!agreementId) return;

    setDocLoading({ id: assignment.id, kind });
    try {
      await openDocument({
        agreementId,
        idcc: assignment.agreement_details?.idcc ?? 'cc',
        agreementName: formatCatalogConventionName(assignment.agreement_details?.name),
        kind,
        sourceTextHash: rulesStatusMap[assignment.collective_agreement_id]?.source_text_hash,
      });
    } finally {
      setDocLoading(null);
    }
  };

  const handleExportRulesPdf = (
    assignment: collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails
  ) => {
    const agreementId = assignment.collective_agreement_id;
    const rules = rulesStatusMap[agreementId]?.rules;
    if (!rules || !hasPayrollGridFromRules(rules)) {
      toast({
        title: 'Grille indisponible',
        description:
          getPayrollGridUnavailableReason(rulesStatusMap[agreementId]) ??
          'Les minima salariaux ne sont pas encore extraits pour cette convention.',
        variant: 'destructive',
      });
      return;
    }
    setDocLoading({ id: assignment.id, kind: 'rules' });
    try {
      printRulesPdfFromJson({
        rules,
        agreementName: formatCatalogConventionName(assignment.agreement_details?.name),
        idcc: assignment.agreement_details?.idcc ?? '',
      });
    } catch (err: unknown) {
      const error = err as Error;
      toast({
        title: 'Erreur',
        description: error.message ?? 'Export PDF impossible',
        variant: 'destructive',
      });
    } finally {
      window.setTimeout(() => setDocLoading(null), 400);
    }
  };

  const handleDeleteClick = (
    assignment: collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails
  ) => {
    setAssignmentToDelete(assignment);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!assignmentToDelete) return;

    try {
      await collectiveAgreementsApi.unassignAgreement(assignmentToDelete.id, companyId);
      toast({ title: 'Succès', description: 'Convention collective retirée.' });
      setDeleteDialogOpen(false);
      setAssignmentToDelete(null);
      await fetchAssignments();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      const errorMsg =
        error.response?.data?.detail || error.message || 'Une erreur est survenue.';
      toast({ title: 'Erreur', description: errorMsg, variant: 'destructive' });
    }
  };

  const handleOpenChat = (
    assignment: collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails
  ) => {
    setSelectedAgreementForChat(assignment);
    setChatQuestion('');
    setConversationHistory([]);
    setIsChatOpen(true);
  };

  const handleAskQuestion = async () => {
    if (!chatQuestion.trim() || !selectedAgreementForChat) return;

    const userMessage: ChatMessage = { role: 'user', content: chatQuestion };
    setConversationHistory((prev) => [...prev, userMessage]);

    const currentQuestion = chatQuestion;
    setChatQuestion('');
    setIsChatLoading(true);

    try {
      const response = await collectiveAgreementsApi.askQuestion({
        agreement_id: selectedAgreementForChat.collective_agreement_id,
        question: currentQuestion,
      });
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.data.answer,
      };
      setConversationHistory((prev) => [...prev, assistantMessage]);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      const errorMsg =
        error.response?.data?.detail || error.message || 'Une erreur est survenue.';
      toast({ title: 'Erreur', description: errorMsg, variant: 'destructive' });
    } finally {
      setIsChatLoading(false);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Building className="mr-2 h-5 w-5 text-indigo-600" /> Conventions collectives
          </CardTitle>
        </CardHeader>
        <CardContent className="flex h-32 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="flex flex-col items-start gap-0.5 text-base sm:flex-row sm:items-center">
            <span className="flex items-center">
              <Building className="mr-2 h-5 w-5 text-indigo-600" /> Conventions collectives
            </span>
            {companyName ? (
              <span className="text-xs font-normal text-muted-foreground sm:ml-2">
                {companyName}
              </span>
            ) : null}
          </CardTitle>
          <Button variant="outline" size="sm" onClick={handleOpenModal} disabled={!companyId}>
            <Plus className="mr-1 h-3 w-3" />
            Ajouter
          </Button>
        </CardHeader>
        <CardContent>
          {assignments.length > 0 ? (
            <div className="space-y-3">
              {assignments.map((assignment) => {
                const agreementId = assignment.collective_agreement_id;
                const status = rulesStatusMap[agreementId];
                const hasText =
                  hasCachedTextFromSource(status?.text_source) ||
                  Boolean(assignment.agreement_details?.rules_pdf_path);
                const hasRules = Boolean(status?.has_rules);
                const hasPayrollGrid = hasPayrollGridFromRules(status?.rules);
                const loadingKind =
                  docLoading?.id === assignment.id ? docLoading.kind : null;

                return (
                  <CollectiveAgreementRow
                    key={assignment.id}
                    variant="rh"
                    name={formatCatalogConventionName(assignment.agreement_details?.name)}
                    idcc={assignment.agreement_details?.idcc ?? ''}
                    sector={assignment.agreement_details?.sector}
                    readiness={getReadinessFromRulesStatus(status)}
                    hasText={hasText}
                    legifranceUrl={extractLegifranceUrlFromDescription(
                      assignment.agreement_details?.description
                    )}
                    hasRules={hasRules}
                    hasPayrollGrid={hasPayrollGrid}
                    payrollGridUnavailableReason={getPayrollGridUnavailableReason(status)}
                    hasUploadedPdf={Boolean(assignment.agreement_details?.rules_pdf_path)}
                    loading={loadingKind}
                    onAskQuestion={() => handleOpenChat(assignment)}
                    onViewFullText={() => void handleViewDocument(assignment, 'full-text')}
                    onViewSynthesis={() => void handleViewDocument(assignment, 'synthesis')}
                    onExportRulesPdf={() => handleExportRulesPdf(assignment)}
                    onDownloadSourcePdf={() => handleDownloadSource(assignment)}
                    onUnassign={() => handleDeleteClick(assignment)}
                  />
                );
              })}
            </div>
          ) : (
            <div className="py-6 text-center">
              <FileText className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Aucune convention collective assignée</p>
              <Button variant="outline" size="sm" className="mt-3" onClick={handleOpenModal} disabled={!companyId}>
                <Plus className="mr-1 h-3 w-3" />
                Ajouter
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <CollectiveAgreementAssignDialog
        open={isModalOpen}
        onOpenChange={setIsModalOpen}
        companies={[]}
        fixedCompanyId={companyId}
        fixedCompanyName={companyName}
        excludedAgreementIds={assignments.map((a) => a.collective_agreement_id)}
        onAssigned={() => void fetchAssignments(companyId)}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Retirer cette convention ?</AlertDialogTitle>
            <AlertDialogDescription>
              La convention &laquo;{' '}
              {formatCatalogConventionName(assignmentToDelete?.agreement_details?.name)} &raquo;
              ne sera plus assignée à{' '}
              {companyName ? `l'entreprise ${companyName}` : 'cette entreprise'}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void handleDeleteConfirm()}
              className="bg-red-600 hover:bg-red-700"
            >
              Retirer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={isChatOpen} onOpenChange={setIsChatOpen}>
        <DialogContent className="flex max-h-[80vh] flex-col sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-indigo-600" />
              Assistant —{' '}
              {formatCatalogConventionName(selectedAgreementForChat?.agreement_details?.name)}
            </DialogTitle>
            <DialogDescription>
              Posez vos questions sur cette convention collective.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-1 flex-col space-y-4 py-4">
            {conversationHistory.length > 0 && (
              <div className="max-h-[400px] flex-1 overflow-auto rounded-lg border bg-muted/20 p-4">
                <div className="space-y-4">
                  {conversationHistory.map((message, idx) => (
                    <div
                      key={idx}
                      className={cn(
                        'rounded-lg p-3',
                        message.role === 'user'
                          ? 'ml-auto max-w-[80%] bg-indigo-100'
                          : 'max-w-[95%] border bg-white'
                      )}
                    >
                      <p className="mb-1 text-xs font-medium text-muted-foreground">
                        {message.role === 'user' ? 'Vous' : 'Assistant'}
                      </p>
                      <div className="whitespace-pre-wrap text-sm">{message.content}</div>
                    </div>
                  ))}
                  {isChatLoading && (
                    <div className="max-w-[95%] rounded-lg border bg-white p-3">
                      <p className="mb-1 text-xs font-medium text-muted-foreground">Assistant</p>
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
                        <span className="text-sm text-muted-foreground">En train de répondre...</span>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="chat-question">Votre question</Label>
              <div className="flex gap-2">
                <Input
                  id="chat-question"
                  placeholder="Ex : combien de jours de congés payés ?"
                  value={chatQuestion}
                  onChange={(e) => setChatQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void handleAskQuestion();
                    }
                  }}
                  disabled={isChatLoading}
                />
                <Button
                  onClick={() => void handleAskQuestion()}
                  disabled={!chatQuestion.trim() || isChatLoading}
                  className="bg-indigo-600 hover:bg-indigo-700"
                >
                  {isChatLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            {conversationHistory.length === 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">Exemples :</p>
                <div className="grid grid-cols-1 gap-2">
                  {[
                    'Combien de jours de congés payés par an ?',
                    'Quelle est la durée légale du travail ?',
                    'Quelles sont les conditions de la période d\'essai ?',
                  ].map((example, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setChatQuestion(example)}
                      className="rounded border p-2 text-left text-xs transition-colors hover:bg-muted"
                      disabled={isChatLoading}
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsChatOpen(false)}>
              Fermer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConventionDocumentViewerDialog
        open={viewer.open}
        onOpenChange={(open) => {
          if (!open) closeViewer();
        }}
        title={viewer.title}
        subtitle={viewer.subtitle}
        pdfUrl={viewer.pdfUrl}
        loading={viewer.loading}
        canDownload={Boolean(viewer.blob)}
        onDownload={downloadFromViewer}
      />
    </>
  );
}
