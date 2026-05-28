import { ExternalLink } from 'lucide-react';

type RatesSourceLinksProps = {
  links: string[] | null | undefined;
};

export function RatesSourceLinks({ links }: RatesSourceLinksProps) {
  if (!links?.length) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2 border-t pt-2">
      {links.map((url) => (
        <a
          key={url}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          <ExternalLink className="h-3 w-3" />
          Source officielle
        </a>
      ))}
    </div>
  );
}
