import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { getDocuments } from '@/api/documents';
import {
  groupGeneratedByFolder,
  sortPayslipsDesc,
  type PayslipItem,
} from '@/components/employee-detail/employeeDetailDocumentsFolders';
import {
  countEmployeeSelfFolderItems,
  filterVisibleGeneratedDocs,
  type ExitDocumentItem,
  type ExpenseReceiptItem,
} from '@/components/documents/employeeDocumentsFolderCounts';
import {
  useCurrentEmployee,
  type CurrentEmployeeRow,
} from '@/hooks/useCurrentEmployee';
import { DOCUMENT_FOLDERS, type DocumentFolderId } from '@/components/employee-detail/employeeDetailDocumentsFolders';

export const QK_EMPLOYEE_SELF_DOCUMENTS = ['employee', 'self-documents'] as const;

interface ContractUrlResponse {
  url: string | null;
  preview_url?: string | null;
}

interface PublishedExitDoc {
  id: string;
  name: string;
  url: string;
  preview_url?: string;
  date?: string;
  is_published?: boolean;
}

interface ExpenseRow {
  id: string;
  date: string;
  type: string;
  receipt_url: string | null;
}

export type EmployeeSelfProfile = CurrentEmployeeRow;

export function useEmployeeSelfDocuments() {
  const { employee, isLoading: empLoading, notConfigured, refetch: refetchEmployee } =
    useCurrentEmployee();

  const contractQuery = useQuery({
    queryKey: [...QK_EMPLOYEE_SELF_DOCUMENTS, 'contract'],
    queryFn: async () => {
      const res = await apiClient.get<ContractUrlResponse>('/api/employees/me/contract');
      return {
        downloadUrl: res.data.url ?? null,
        previewUrl: res.data.preview_url ?? res.data.url ?? null,
      };
    },
    enabled: Boolean(employee?.id),
  });

  const identityQuery = useQuery({
    queryKey: [...QK_EMPLOYEE_SELF_DOCUMENTS, 'identity'],
    queryFn: async () => {
      const res = await apiClient.get<ContractUrlResponse>('/api/employees/me/identity-document');
      return {
        downloadUrl: res.data.url ?? null,
        previewUrl: res.data.preview_url ?? res.data.url ?? null,
      };
    },
    enabled: Boolean(employee?.id),
  });

  const credentialsPdfQuery = useQuery({
    queryKey: [...QK_EMPLOYEE_SELF_DOCUMENTS, 'credentials-pdf'],
    queryFn: async () => {
      const res = await apiClient.get<ContractUrlResponse>('/api/employees/me/credentials-pdf');
      return {
        downloadUrl: res.data.url ?? null,
        previewUrl: res.data.preview_url ?? res.data.url ?? null,
      };
    },
    enabled: Boolean(employee?.id),
    retry: false,
    staleTime: 5 * 60_000,
  });

  const payslipsQuery = useQuery({
    queryKey: [...QK_EMPLOYEE_SELF_DOCUMENTS, 'payslips'],
    queryFn: async () => {
      const res = await apiClient.get<PayslipItem[]>('/api/me/payslips');
      return sortPayslipsDesc(res.data ?? []);
    },
    enabled: Boolean(employee?.id),
  });

  const generatedQuery = useQuery({
    queryKey: [...QK_EMPLOYEE_SELF_DOCUMENTS, 'generated', employee?.id],
    queryFn: () => getDocuments({ employee_id: employee!.id }),
    enabled: Boolean(employee?.id),
  });

  const exitDocsQuery = useQuery({
    queryKey: [...QK_EMPLOYEE_SELF_DOCUMENTS, 'exit'],
    queryFn: async () => {
      const res = await apiClient.get<PublishedExitDoc[]>(
        '/api/employees/me/published-exit-documents'
      );
      return (res.data ?? []).map(
        (doc): ExitDocumentItem => ({
          id: doc.id,
          name: doc.name,
          url: doc.url,
          previewUrl: doc.preview_url ?? doc.url,
          date: doc.date,
          isPublished: doc.is_published ?? true,
        })
      );
    },
    enabled: Boolean(employee?.id),
  });

  const expensesQuery = useQuery({
    queryKey: [...QK_EMPLOYEE_SELF_DOCUMENTS, 'expenses'],
    queryFn: async () => {
      const res = await apiClient.get<ExpenseRow[]>('/api/expenses/me');
      return (res.data ?? [])
        .filter((exp) => exp.receipt_url)
        .map(
          (exp): ExpenseReceiptItem => ({
            id: exp.id,
            name: `Justificatif — ${exp.type}`,
            url: exp.receipt_url!,
            subtitle: `Note de frais du ${new Date(exp.date).toLocaleDateString('fr-FR')}`,
          })
        );
    },
    enabled: Boolean(employee?.id),
  });

  const profile: EmployeeSelfProfile | null = employee;

  const visibleGenerated = useMemo(
    () => filterVisibleGeneratedDocs(generatedQuery.data ?? []),
    [generatedQuery.data]
  );

  const generatedByFolder = useMemo(
    () => groupGeneratedByFolder(visibleGenerated),
    [visibleGenerated]
  );

  const payslips = payslipsQuery.data ?? [];
  const contractUrl = contractQuery.data?.downloadUrl ?? null;
  const contractPreviewUrl = contractQuery.data?.previewUrl ?? null;
  const identityUrl = identityQuery.data?.downloadUrl ?? null;
  const identityPreviewUrl = identityQuery.data?.previewUrl ?? null;
  const credentialsPdfUrl = credentialsPdfQuery.data?.downloadUrl ?? null;
  const credentialsPdfPreviewUrl = credentialsPdfQuery.data?.previewUrl ?? null;
  const exitDocuments = exitDocsQuery.data ?? [];
  const expenseReceipts = expensesQuery.data ?? [];

  const folderCounts = useMemo(() => {
    const opts = {
      contractUrl,
      identityUrl,
      payslips,
      credentialsPdfUrl,
      generatedByFolder,
      exitDocuments,
      expenseReceipts,
    };
    return Object.fromEntries(
      DOCUMENT_FOLDERS.map((f) => [f.id, countEmployeeSelfFolderItems(f.id, opts)])
    ) as Record<DocumentFolderId, number>;
  }, [
    contractUrl,
    contractPreviewUrl,
    identityUrl,
    identityPreviewUrl,
    credentialsPdfUrl,
    credentialsPdfPreviewUrl,
    payslips,
    generatedByFolder,
    exitDocuments,
    expenseReceipts,
  ]);

  const isLoading =
    empLoading ||
    (Boolean(employee?.id) &&
      (contractQuery.isLoading ||
        identityQuery.isLoading ||
        credentialsPdfQuery.isLoading ||
        payslipsQuery.isLoading ||
        generatedQuery.isLoading ||
        exitDocsQuery.isLoading ||
        expensesQuery.isLoading));

  const refetchAll = () => {
    void refetchEmployee();
    void contractQuery.refetch();
    void identityQuery.refetch();
    void credentialsPdfQuery.refetch();
    void payslipsQuery.refetch();
    void generatedQuery.refetch();
    void exitDocsQuery.refetch();
    void expensesQuery.refetch();
  };

  return {
    employee,
    profile,
    notConfigured,
    isLoading,
    contractUrl,
    contractPreviewUrl,
    identityUrl,
    identityPreviewUrl,
    credentialsPdfUrl,
    credentialsPdfPreviewUrl,
    payslips,
    generatedByFolder,
    visibleGenerated,
    exitDocuments,
    expenseReceipts,
    folderCounts,
    queries: {
      contract: contractQuery,
      identity: identityQuery,
      credentialsPdf: credentialsPdfQuery,
      payslips: payslipsQuery,
      generated: generatedQuery,
      exit: exitDocsQuery,
      expenses: expensesQuery,
    },
    refetchAll,
  };
}

export type EmployeeSelfDocumentsData = ReturnType<typeof useEmployeeSelfDocuments>;
