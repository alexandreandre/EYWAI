import type { ReactNode } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';

type AdminPageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function AdminPageHeader({ title, description, actions }: AdminPageHeaderProps) {
  return <PageHeader title={title} description={description} actions={actions} />;
}
