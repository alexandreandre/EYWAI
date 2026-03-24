import { useEffect, useState, useRef } from "react"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import apiClient from "@/api/apiClient"
import { Loader2, Send, Sparkles, Brain } from "lucide-react"

// --- Types ---
interface CopilotModalProps {
  isOpen: boolean
  onClose: () => void
}

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
}

interface AgentResponse {
  answer: string
  needs_clarification: boolean
  clarification_question?: string
  sql_queries?: string[]
  data?: any
  thought_process?: string
}

// --- Suggestions ---
const suggestions = [
  "Combien gagne Marie Dupont ?",
  "Quel est le salaire moyen des cadres ?",
  "Combien d'employés avons-nous ?",
  "Masse salariale totale du mois dernier",
  "Qui est en congé cette semaine ?",
  "Liste des notes de frais en attente"
]

// --- Composant ---
export function CopilotModalAgent({ isOpen, onClose }: CopilotModalProps) {
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [showDebug, setShowDebug] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll vers le bas
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Reset quand le modal est fermé
  useEffect(() => {
    if (!isOpen) {
      setTimeout(() => {
        setInput("")
        setMessages([])
        setIsLoading(false)
      }, 200)
    }
  }, [isOpen])

  const handleQuery = async (prompt: string) => {
    if (!prompt.trim() || isLoading) return

    // Ajouter le message de l'utilisateur
    const userMessage: Message = { role: 'user', content: prompt }
    setMessages(prev => [...prev, userMessage])
    setInput("")
    setIsLoading(true)

    try {
      // Préparer l'historique de conversation pour l'agent
      const conversationHistory = messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))

      // Appeler le nouvel endpoint agent
      const response = await apiClient.post<AgentResponse>('/api/copilot/query-agent', {
        prompt: prompt,
        conversation_history: conversationHistory
      })

      const data = response.data

      // Si l'agent a besoin de clarification
      if (data.needs_clarification && data.clarification_question) {
        const assistantMessage: Message = {
          role: 'assistant',
          content: data.clarification_question
        }
        setMessages(prev => [...prev, assistantMessage])
      } else {
        // Réponse normale
        const assistantMessage: Message = {
          role: 'assistant',
          content: data.answer
        }
        setMessages(prev => [...prev, assistantMessage])

        // Afficher le debug si disponible (optionnel)
        if (data.thought_process && showDebug) {
          console.log("Processus de pensée:", data.thought_process)
          console.log("Requêtes SQL:", data.sql_queries)
        }
      }
    } catch (e: any) {
      const errorMessage: Message = {
        role: 'assistant',
        content: `❌ Erreur: ${e.response?.data?.detail || e.message || "Erreur de connexion"}`
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    handleQuery(suggestion)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-3xl max-h-[80vh] p-0 gap-0 flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-gradient-to-r from-indigo-50 to-cyan-50">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-gray-900">Assistant IA</h2>
            <span className="text-xs text-gray-500 bg-white px-2 py-0.5 rounded-full">Agent Intelligent</span>
          </div>
          <button
            onClick={() => setShowDebug(!showDebug)}
            className="text-xs text-gray-500 hover:text-gray-700"
            title="Toggle debug mode"
          >
            {showDebug ? "🐛 Debug ON" : ""}
          </button>
        </div>

        {/* Zone de messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[400px] max-h-[500px]">
          {messages.length === 0 ? (
            <div className="space-y-4">
              <div className="text-center text-gray-500 text-sm py-8">
                <Sparkles className="h-12 w-12 mx-auto mb-3 text-indigo-400" />
                <p className="font-medium mb-1">Posez-moi n'importe quelle question !</p>
                <p className="text-xs">Je suis un agent intelligent qui peut chercher des informations et vous demander des précisions si nécessaire.</p>
              </div>

              {/* Suggestions */}
              <div className="grid grid-cols-1 gap-2">
                <p className="text-xs font-medium text-gray-600 mb-1">Suggestions :</p>
                {suggestions.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestionClick(s)}
                    className="text-left p-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-all text-sm group"
                  >
                    <Sparkles className="h-3 w-3 inline mr-2 text-cyan-500 group-hover:text-indigo-500" />
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] p-3 rounded-lg ${
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 p-3 rounded-lg flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />
                    <span className="text-sm text-gray-600">Je réfléchis...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Zone de saisie */}
        <div className="p-4 border-t bg-gray-50">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleQuery(input)
                }
              }}
              placeholder="Posez votre question..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none text-sm"
              disabled={isLoading}
            />
            <Button
              onClick={() => handleQuery(input)}
              disabled={isLoading || !input.trim()}
              size="icon"
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Appuyez sur Entrée pour envoyer. L'agent peut vous demander des précisions si nécessaire.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  )
}
