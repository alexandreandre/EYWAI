import { useEffect, useState } from "react"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Dialog, DialogContent, DialogClose } from "@/components/ui/dialog"
import apiClient from "@/api/apiClient"
import { Loader2, Send, CornerDownLeft, Sparkles, X } from "lucide-react"

// --- Types de Réponse ---
interface CopilotModalProps {
  isOpen: boolean
  onClose: () => void
}

type AnswerType = 'text' | 'data' | 'error';

// Correspond à la QueryResponse de Pydantic
interface Answer {
  answer: any;
  type: AnswerType;
  sql_query?: string; // Pour le debug
}

// --- Suggestions de Prompts ---
const suggestions = [
  "Masse salariale totale du mois dernier ?",
  "Quels sont les employés en fin de période d'essai ce mois-ci ?",
  "Liste des absents aujourd'hui.",
  "Coût total des notes de frais de 'Transport' en Octobre ?",
];

// --- Composant ---
export function CopilotModal({ isOpen, onClose }: CopilotModalProps) {
  const [input, setInput] = useState("")
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  

  // Reset le modal quand il est fermé
  useEffect(() => {
    if (!isOpen) {
      setTimeout(() => {
        setInput("")
        setAnswer(null)
        setIsLoading(false)
      }, 200); // Laisse le temps à l'animation de fermeture
    }
  }, [isOpen])

  const handleQuery = async (prompt: string) => {
    if (!prompt || isLoading) return;
    
    setIsLoading(true);
    setAnswer(null); // Efface l'ancienne réponse
    setInput(prompt); // Met le prompt dans la barre de recherche
    
    try {
      const response = await apiClient.post<Answer>('/api/copilot/query', { prompt: prompt });
      setAnswer(response.data);
    } catch (e: any) {
      setAnswer({
        answer: e.response?.data?.detail || e.message || "Erreur de connexion",
        type: 'error'
      });
    } finally {
      setIsLoading(false);
    }
  }
  
  const renderAnswer = () => {
    if (isLoading) {
      return (
        <div className="p-4 flex items-center text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 mr-2 animate-spin text-indigo-500" />
          Recherche en cours...
        </div>
      );
    }
    
    if (!answer) {
       return (
         <CommandGroup heading="Suggestions">
           {suggestions.map((s) => (
             <CommandItem key={s} onSelect={() => handleQuery(s)}>
               <Sparkles className="h-4 w-4 mr-2 text-cyan-500" />
               {s}
             </CommandItem>
           ))}
         </CommandGroup>
       );
    }
    
    if (answer.type === 'error') {
      return <div className="p-4 text-sm text-red-500">{String(answer.answer)}</div>;
    }
    
    // TODO: Ajouter un rendu pour le type 'data' (ex: afficher des avatars)
    return (
      <div className="p-4 text-sm whitespace-pre-wrap leading-relaxed">
        {String(answer.answer)}
      </div>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="p-0 gap-0 max-w-2xl shadow-2xl">
        <Command className="[&_[cmdk-input-wrapper]]:flex-1 [&_[cmdk-input-wrapper]_svg]:hidden">
          <div className="flex items-center border-b px-3">
            <Sparkles className="mr-2 h-5 w-5 shrink-0 text-cyan-500" />
            <CommandInput 
              placeholder="Ex: 'Qui est absent aujourd'hui ?'" 
              value={input}
              onValueChange={setInput}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !isLoading) {
                  handleQuery(input);
                }
              }}
              className="h-12 border-0 focus:ring-0 shadow-none"
            />
            <button 
                onClick={() => handleQuery(input)} 
                disabled={isLoading}
                className="p-2 mr-6 rounded-md hover:bg-muted disabled:opacity-50"
            >


              <Send className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>
          
          <CommandList className="max-h-[400px]">
            {renderAnswer()}
          </CommandList>
          
          <div className="border-t p-2 flex justify-end text-xs text-muted-foreground">
            Appuyez sur <CornerDownLeft className="h-3 w-3 mx-1" /> pour envoyer
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  )
}