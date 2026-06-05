import { Fragment, type ReactNode } from 'react';

/** Rend le gras Markdown ``**texte**`` sans afficher les astérisques. */
export function renderInlineBold(text: string, keyPrefix = ''): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g).filter((part) => part.length > 0);
  return parts.map((part, index) => {
    const boldMatch = part.match(/^\*\*(.+)\*\*$/);
    if (boldMatch) {
      return (
        <strong key={`${keyPrefix}b${index}`} className="font-semibold text-foreground">
          {boldMatch[1]}
        </strong>
      );
    }
    return <Fragment key={`${keyPrefix}t${index}`}>{part}</Fragment>;
  });
}

/** Affiche une réponse assistant : retours à la ligne + gras ``**…**``. */
export function AssistantMessageContent({ content }: { content: string }) {
  const lines = content.split('\n');

  return (
    <div className="space-y-1">
      {lines.map((line, lineIndex) => {
        if (!line.trim()) {
          return <div key={lineIndex} className="h-2" aria-hidden />;
        }
        return (
          <p key={lineIndex} className="m-0">
            {renderInlineBold(line, `l${lineIndex}-`)}
          </p>
        );
      })}
    </div>
  );
}
