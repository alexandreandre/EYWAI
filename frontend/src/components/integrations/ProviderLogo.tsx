import { useState } from 'react';
import { cn } from '@/lib/utils';
import { getProviderMeta } from '@/features/accounting-integration/providers';

type ProviderLogoProps = {
  providerKey: string;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
};

const SIZE_CLASS = {
  sm: 'h-6 max-w-[72px]',
  md: 'h-8 max-w-[96px]',
  lg: 'h-10 max-w-[120px]',
} as const;

export function ProviderLogo({ providerKey, className, size = 'md' }: ProviderLogoProps) {
  const meta = getProviderMeta(providerKey);
  const src = `/integrations/${meta.logoKey}.svg`;
  const [imgError, setImgError] = useState(false);

  if (imgError) {
    return (
      <span
        className={cn(
          'inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold',
          SIZE_CLASS[size],
          className,
        )}
        style={{
          backgroundColor: `${meta.brandColor}18`,
          color: meta.brandColor,
        }}
      >
        {meta.name}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={meta.name}
      className={cn('object-contain', SIZE_CLASS[size], className)}
      onError={() => setImgError(true)}
    />
  );
}
