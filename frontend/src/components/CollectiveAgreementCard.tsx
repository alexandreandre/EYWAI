// frontend/src/components/CollectiveAgreementCard.tsx

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/use-toast';
import { Building, Download, FileText, Loader2, Plus, Trash2, MessageSquare, Send } from 'lucide-react';
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
} from "@/components/ui/alert-dialog";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Check, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export default function CollectiveAgreementCard() {
  const { toast } = useToast();

  // États pour les conventions assignées à l'entreprise
  const [assignments, setAssignments] = useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // États pour le catalogue (dropdown)
  const [catalog, setCatalog] = useState<collectiveAgreementsApi.CollectiveAgreementCatalog[]>([]);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(false);

  // États pour le modal d'ajout
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedAgreementId, setSelectedAgreementId] = useState<string>('');
  const [comboboxOpen, setComboboxOpen] = useState(false);

  // États pour la suppression
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [assignmentToDelete, setAssignmentToDelete] = useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails | null>(null);

  // États pour le chat IA
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [selectedAgreementForChat, setSelectedAgreementForChat] = useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails | null>(null);
  const [chatQuestion, setChatQuestion] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);

  // Historique de conversation
  interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
  }
  const [conversationHistory, setConversationHistory] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll vers le bas quand un nouveau message arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [conversationHistory]);

  const fetchAssignments = async () => {
    setIsLoading(true);
    try {
      const response = await collectiveAgreementsApi.getMyCompanyAgreements();
      setAssignments(response.data || []);
    } catch (err: any) {
      console.error('Erreur lors de la récupération des conventions assignées:', err);
      setAssignments([]);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchCatalog = async () => {
    setIsLoadingCatalog(true);
    try {
      const response = await collectiveAgreementsApi.getCatalog({ active_only: true });
      setCatalog(response.data || []);
    } catch (err: any) {
      console.error('Erreur lors de la récupération du catalogue:', err);
      setCatalog([]);
    } finally {
      setIsLoadingCatalog(false);
    }
  };

  useEffect(() => {
    fetchAssignments();
  }, []);

  const handleOpenModal = () => {
    setSelectedAgreementId('');
    setIsModalOpen(true);
    fetchCatalog();
  };

  const handleSubmit = async () => {
    if (!selectedAgreementId) {
      toast({ title: 'Erreur', description: 'Veuillez sélectionner une convention collective.', variant: 'destructive' });
      return;
    }

    setIsSubmitting(true);
    try {
      await collectiveAgreementsApi.assignAgreement(selectedAgreementId);
      toast({ title: 'Succès', description: 'Convention collective assignée avec succès.' });
      setIsModalOpen(false);
      await fetchAssignments();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Une erreur est survenue.';
      toast({ title: 'Erreur', description: errorMsg, variant: 'destructive' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownload = (assignment: collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails) => {
    const pdfUrl = assignment.agreement_details?.rules_pdf_url;
    if (!pdfUrl) {
      toast({ title: 'Erreur', description: 'Aucun fichier PDF disponible pour cette convention.', variant: 'destructive' });
      return;
    }

    window.open(pdfUrl, '_blank');
  };

  const handleDeleteClick = (assignment: collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails) => {
    setAssignmentToDelete(assignment);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!assignmentToDelete) return;

    try {
      await collectiveAgreementsApi.unassignAgreement(assignmentToDelete.id);
      toast({ title: 'Succès', description: 'Convention collective retirée.' });
      setDeleteDialogOpen(false);
      setAssignmentToDelete(null);
      await fetchAssignments();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Une erreur est survenue.';
      toast({ title: 'Erreur', description: errorMsg, variant: 'destructive' });
    }
  };

  const handleOpenChat = (assignment: collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails) => {
    setSelectedAgreementForChat(assignment);
    setChatQuestion('');
    setConversationHistory([]);
    setIsChatOpen(true);
  };

  const handleAskQuestion = async () => {
    if (!chatQuestion.trim() || !selectedAgreementForChat) return;

    // Ajouter la question de l'utilisateur à l'historique
    const userMessage: ChatMessage = { role: 'user', content: chatQuestion };
    setConversationHistory(prev => [...prev, userMessage]);

    const currentQuestion = chatQuestion;
    setChatQuestion('');
    setIsChatLoading(true);

    try {
      const response = await collectiveAgreementsApi.askQuestion({
        agreement_id: selectedAgreementForChat.collective_agreement_id,
        question: currentQuestion
      });

      // Ajouter la réponse de l'assistant à l'historique
      const assistantMessage: ChatMessage = { role: 'assistant', content: response.data.answer };
      setConversationHistory(prev => [...prev, assistantMessage]);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Une erreur est survenue.';
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
            <Building className="mr-2 h-5 w-5 text-indigo-600" /> Conventions Collectives
          </CardTitle>
        </CardHeader>
        <CardContent className="flex justify-center items-center h-32">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="flex items-center">
            <Building className="mr-2 h-5 w-5 text-indigo-600" /> Conventions Collectives
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={handleOpenModal}
          >
            <Plus className="mr-1 h-3 w-3" />
            Ajouter
          </Button>
        </CardHeader>
        <CardContent>
          {assignments.length > 0 ? (
            <div className="space-y-4">
              {assignments.map((assignment) => (
                <div key={assignment.id} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">Nom</p>
                        <p className="text-sm font-semibold">{assignment.agreement_details?.name}</p>
                      </div>
                      <div className="mt-2">
                        <p className="text-sm font-medium text-muted-foreground">IDCC</p>
                        <p className="text-sm font-semibold">{assignment.agreement_details?.idcc}</p>
                      </div>
                      {assignment.agreement_details?.sector && (
                        <div className="mt-2">
                          <p className="text-sm font-medium text-muted-foreground">Secteur</p>
                          <p className="text-sm text-muted-foreground">{assignment.agreement_details.sector}</p>
                        </div>
                      )}
                      {assignment.agreement_details?.description && (
                        <div className="mt-2">
                          <p className="text-sm font-medium text-muted-foreground">Description</p>
                          <p className="text-sm text-muted-foreground">{assignment.agreement_details.description}</p>
                        </div>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteClick(assignment)}
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Actions</p>
                    <div className="flex gap-2 mt-1">
                      {assignment.agreement_details?.rules_pdf_path ? (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDownload(assignment)}
                          >
                            <Download className="mr-2 h-4 w-4" />
                            Télécharger le PDF
                          </Button>
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() => handleOpenChat(assignment)}
                            className="bg-indigo-600 hover:bg-indigo-700"
                          >
                            <MessageSquare className="mr-2 h-4 w-4" />
                            Poser une question
                          </Button>
                        </>
                      ) : (
                        <p className="text-xs text-muted-foreground italic">Aucun PDF disponible</p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6">
              <FileText className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">Aucune convention collective assignée</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={handleOpenModal}
              >
                <Plus className="mr-1 h-3 w-3" />
                Ajouter
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modal de sélection */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Ajouter une Convention Collective</DialogTitle>
            <DialogDescription>
              Sélectionnez une convention collective dans le catalogue pour l'assigner à votre entreprise.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Convention collective *</Label>
              <Popover open={comboboxOpen} onOpenChange={setComboboxOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={comboboxOpen}
                    className="w-full justify-between"
                  >
                    {selectedAgreementId
                      ? catalog.find((c) => c.id === selectedAgreementId)?.name
                      : "Rechercher une convention..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[450px] p-0">
                  <Command>
                    <CommandInput placeholder="Rechercher par nom ou IDCC..." />
                    <CommandEmpty>
                      {isLoadingCatalog ? "Chargement..." : "Aucune convention trouvée."}
                    </CommandEmpty>
                    <CommandGroup className="max-h-64 overflow-auto">
                      {catalog.map((agreement) => (
                        <CommandItem
                          key={agreement.id}
                          value={`${agreement.name} ${agreement.idcc}`}
                          onSelect={() => {
                            setSelectedAgreementId(agreement.id);
                            setComboboxOpen(false);
                          }}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              selectedAgreementId === agreement.id ? "opacity-100" : "opacity-0"
                            )}
                          />
                          <div className="flex-1">
                            <p className="font-medium">{agreement.name}</p>
                            <p className="text-xs text-muted-foreground">
                              IDCC: {agreement.idcc}
                              {agreement.sector && ` • ${agreement.sector}`}
                            </p>
                          </div>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </Command>
                </PopoverContent>
              </Popover>
              {selectedAgreementId && (
                <p className="text-xs text-muted-foreground">
                  Convention sélectionnée : {catalog.find((c) => c.id === selectedAgreementId)?.name}
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsModalOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting || !selectedAgreementId}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Assigner
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog de confirmation de suppression */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Êtes-vous sûr ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action retirera la convention collective "{assignmentToDelete?.agreement_details?.name}" de votre entreprise.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} className="bg-red-600 hover:bg-red-700">
              Retirer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Modal de chat IA */}
      <Dialog open={isChatOpen} onOpenChange={setIsChatOpen}>
        <DialogContent className="sm:max-w-[700px] max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-indigo-600" />
              Assistant IA - {selectedAgreementForChat?.agreement_details?.name}
            </DialogTitle>
            <DialogDescription>
              Posez vos questions sur cette convention collective. L'IA spécialisée vous répondra en se basant sur le texte complet de la convention.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 flex flex-col space-y-4 py-4">
            {/* Historique de conversation */}
            {conversationHistory.length > 0 && (
              <div className="flex-1 border rounded-lg p-4 bg-muted/20 overflow-auto max-h-[400px]">
                <div className="space-y-4">
                  {conversationHistory.map((message, idx) => (
                    <div
                      key={idx}
                      className={cn(
                        "p-3 rounded-lg",
                        message.role === 'user'
                          ? "bg-indigo-100 ml-auto max-w-[80%]"
                          : "bg-white border max-w-[95%]"
                      )}
                    >
                      <p className="text-xs font-medium mb-1 text-muted-foreground">
                        {message.role === 'user' ? 'Vous' : 'Assistant IA'}
                      </p>
                      <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                    </div>
                  ))}
                  {isChatLoading && (
                    <div className="p-3 rounded-lg bg-white border max-w-[95%]">
                      <p className="text-xs font-medium mb-1 text-muted-foreground">Assistant IA</p>
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

            {/* Zone de saisie de question */}
            <div className="space-y-2">
              <Label htmlFor="chat-question">Votre question</Label>
              <div className="flex gap-2">
                <Input
                  id="chat-question"
                  placeholder="Ex: Combien de jours de congés payés par an ?"
                  value={chatQuestion}
                  onChange={(e) => setChatQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleAskQuestion();
                    }
                  }}
                  disabled={isChatLoading}
                />
                <Button
                  onClick={handleAskQuestion}
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
              <p className="text-xs text-muted-foreground">
                Appuyez sur Entrée pour envoyer votre question
              </p>
            </div>

            {/* Suggestions de questions */}
            {conversationHistory.length === 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">Exemples de questions :</p>
                <div className="grid grid-cols-1 gap-2">
                  {[
                    "Combien de jours de congés payés ai-je droit par an ?",
                    "Quelle est la durée légale du travail ?",
                    "Quelles sont les conditions de la période d'essai ?",
                    "Quels sont les jours fériés chômés et payés ?"
                  ].map((example, idx) => (
                    <button
                      key={idx}
                      onClick={() => setChatQuestion(example)}
                      className="text-left text-xs p-2 rounded border hover:bg-muted transition-colors"
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
    </>
  );
}
