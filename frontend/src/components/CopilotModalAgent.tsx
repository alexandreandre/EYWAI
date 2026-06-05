import { useEffect, useState, useRef } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import apiClient from "@/api/apiClient"
import { getUserErrorMessage } from "@/lib/errorMessages"
import { cn } from "@/lib/utils"
import { AssistantMessageContent } from "@/lib/simpleMarkdown"
import { Loader2, Send, Sparkles } from "lucide-react"

const AI_BUTTON_CLASS =
  "border-0 bg-gradient-to-r from-pink-500 via-rose-500 to-fuchsia-500 text-white shadow-md shadow-pink-500/30 hover:from-pink-600 hover:via-rose-600 hover:to-fuchsia-600 hover:shadow-lg hover:shadow-pink-500/40 transition-all"

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
  data?: unknown
  thought_process?: string
}

export function CopilotModalAgent({ isOpen, onClose }: CopilotModalProps) {
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

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

    const userMessage: Message = { role: 'user', content: prompt }
    setMessages(prev => [...prev, userMessage])
    setInput("")
    setIsLoading(true)

    try {
      const conversationHistory = messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))

      const response = await apiClient.post<AgentResponse>('/api/copilot/query-agent', {
        prompt: prompt,
        conversation_history: conversationHistory
      })

      const data = response.data

      if (data.needs_clarification && data.clarification_question) {
        const assistantMessage: Message = {
          role: 'assistant',
          content: data.clarification_question
        }
        setMessages(prev => [...prev, assistantMessage])
      } else {
        const assistantMessage: Message = {
          role: 'assistant',
          content: data.answer
        }
        setMessages(prev => [...prev, assistantMessage])
      }
    } catch (e: unknown) {
      const errorMessage: Message = {
        role: 'assistant',
        content: getUserErrorMessage(
          e,
          "Le service d'assistance est momentanément indisponible. Réessayez.",
        ),
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleOpenChange = (open: boolean) => {
    if (!open) onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="flex max-h-[85vh] max-w-3xl flex-col gap-0 overflow-hidden p-0 sm:rounded-xl">
        <DialogHeader className="space-y-1.5 border-b bg-gradient-to-r from-pink-50 via-rose-50 to-fuchsia-50 px-6 py-5">
          <DialogTitle className="flex items-center gap-2 text-foreground">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-pink-100 via-rose-100 to-fuchsia-100">
              <Sparkles className="h-4 w-4 text-rose-500" />
            </span>
            Assistant RH IA
          </DialogTitle>
          <DialogDescription className="text-sm leading-relaxed">
            Posez n&apos;importe quelle question, en langage naturel. L&apos;assistant
            interroge vos données RH (effectifs, paie, absences, notes de frais),
            répond sur vos conventions collectives et vous guide dans l&apos;utilisation
            du logiciel — comment faire une action ou où trouver une fonctionnalité.
          </DialogDescription>
        </DialogHeader>

        <div className="flex min-h-[360px] max-h-[480px] flex-1 flex-col overflow-y-auto px-6 py-5">
          {messages.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-pink-100 via-rose-50 to-fuchsia-100 shadow-sm">
                <Sparkles className="h-8 w-8 text-rose-500" />
              </div>
              <p className="max-w-lg text-sm leading-relaxed text-muted-foreground">
                Formulez votre question comme vous le feriez à un collègue RH : une
                donnée à retrouver, une règle de convention collective, ou de l&apos;aide
                pour utiliser le logiciel. L&apos;assistant vous répond directement ici.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={cn(
                    "flex",
                    msg.role === 'user' ? 'justify-end' : 'justify-start',
                  )}
                >
                  {msg.role === 'assistant' && (
                    <span className="mr-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-pink-100 to-rose-100">
                      <Sparkles className="h-3.5 w-3.5 text-rose-500" />
                    </span>
                  )}
                  <div
                    className={cn(
                      "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
                      msg.role === 'user'
                        ? cn(AI_BUTTON_CLASS, "rounded-br-md shadow-sm")
                        : "rounded-bl-md border bg-card text-foreground shadow-sm",
                    )}
                  >
                    {msg.role === 'assistant' ? (
                      <AssistantMessageContent content={msg.content} />
                    ) : (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    )}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <span className="mr-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-pink-100 to-rose-100">
                    <Sparkles className="h-3.5 w-3.5 text-rose-500" />
                  </span>
                  <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border bg-card px-4 py-3 shadow-sm">
                    <Loader2 className="h-4 w-4 animate-spin text-rose-500" />
                    <span className="text-sm text-muted-foreground">Analyse en cours…</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="border-t bg-muted/30 px-6 py-4">
          <div
            className={cn(
              "flex items-center gap-2 rounded-xl border bg-card p-2 shadow-sm transition-colors focus-within:border-rose-300 focus-within:ring-1 focus-within:ring-rose-200",
            )}
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void handleQuery(input)
                }
              }}
              placeholder="Ex. : comment lancer la paie ? ou combien d'employés sont en CDI ?"
              className="border-0 bg-transparent shadow-none focus-visible:ring-0"
              disabled={isLoading}
            />
            <Button
              onClick={() => void handleQuery(input)}
              disabled={isLoading || !input.trim()}
              size="icon"
              className={cn("shrink-0 rounded-lg", AI_BUTTON_CLASS)}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Appuyez sur Entrée pour envoyer.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  )
}
