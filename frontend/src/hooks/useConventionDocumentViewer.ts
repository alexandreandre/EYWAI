import { useCallback, useEffect, useRef, useState } from 'react';
import * as collectiveAgreementsApi from '@/api/collectiveAgreements';
import { useToast } from '@/components/ui/use-toast';
import { createBlobPreviewUrl, downloadBlob } from '@/lib/downloadBlob';
import {
  conventionDocumentFilename,
  getCachedConventionDocument,
  setCachedConventionDocument,
  type ConventionDocumentKind,
} from '@/lib/collectiveAgreementDocumentCache';

type ViewerState = {
  open: boolean;
  title: string;
  subtitle: string;
  pdfUrl: string | null;
  filename: string;
  loading: boolean;
  blob: Blob | null;
};

const DOC_LABELS: Record<
  ConventionDocumentKind,
  { title: string; generating: string; ready: string }
> = {
  'full-text': {
    title: 'Convention complète',
    generating: 'Assemblage du texte intégral…',
    ready: 'Texte intégral prêt à consulter.',
  },
  synthesis: {
    title: 'Guide simplifié',
    generating: 'Génération de la synthèse (une seule fois si le texte n’a pas changé)…',
    ready: 'Synthèse enregistrée — les prochaines ouvertures seront instantanées.',
  },
};

const EMPTY_VIEWER: ViewerState = {
  open: false,
  title: '',
  subtitle: '',
  pdfUrl: null,
  filename: '',
  loading: false,
  blob: null,
};

async function parseApiErrorDetail(err: unknown, fallback: string): Promise<string> {
  const error = err as { response?: { data?: unknown }; message?: string };
  let detail = fallback;
  const data = error?.response?.data;
  if (typeof data === 'object' && data !== null && 'detail' in data) {
    detail = String((data as { detail: unknown }).detail);
  } else if (error?.message) {
    detail = error.message;
  }
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      detail = JSON.parse(text)?.detail || detail;
    } catch {
      /* garde le message par défaut */
    }
  }
  return detail;
}

export function useConventionDocumentViewer() {
  const { toast } = useToast();
  const [viewer, setViewer] = useState<ViewerState>(EMPTY_VIEWER);
  const pdfUrlRef = useRef<string | null>(null);

  const revokePdfUrl = useCallback((url: string | null) => {
    if (url) URL.revokeObjectURL(url);
  }, []);

  useEffect(() => {
    pdfUrlRef.current = viewer.pdfUrl;
  }, [viewer.pdfUrl]);

  useEffect(() => {
    return () => revokePdfUrl(pdfUrlRef.current);
  }, [revokePdfUrl]);

  const closeViewer = useCallback(() => {
    setViewer((current) => {
      revokePdfUrl(current.pdfUrl);
      return { ...EMPTY_VIEWER };
    });
  }, [revokePdfUrl]);

  const openDocument = useCallback(
    async (params: {
      agreementId: string;
      idcc: string;
      agreementName: string;
      kind: ConventionDocumentKind;
      sourceTextHash?: string | null;
    }) => {
      const { agreementId, idcc, agreementName, kind, sourceTextHash } = params;
      const labels = DOC_LABELS[kind];
      const filename = conventionDocumentFilename(idcc, kind);
      const subtitle = `${agreementName} · IDCC ${idcc}`;

      const cached = getCachedConventionDocument(agreementId, kind, sourceTextHash);
      if (cached) {
        const url = createBlobPreviewUrl(cached.blob);
        setViewer((current) => {
          revokePdfUrl(current.pdfUrl);
          return {
            open: true,
            title: labels.title,
            subtitle,
            pdfUrl: url,
            filename: cached.filename,
            loading: false,
            blob: cached.blob,
          };
        });
        return;
      }

      setViewer((current) => {
        revokePdfUrl(current.pdfUrl);
        return {
          open: true,
          title: labels.title,
          subtitle,
          pdfUrl: null,
          filename,
          loading: true,
          blob: null,
        };
      });

      try {
        const res =
          kind === 'full-text'
            ? await collectiveAgreementsApi.getConventionFullTextPdf(agreementId)
            : await collectiveAgreementsApi.getConventionSynthesisPdf(agreementId);

        const blob = new Blob([res.data as BlobPart], { type: 'application/pdf' });
        setCachedConventionDocument(agreementId, kind, sourceTextHash, blob, filename);
        const url = createBlobPreviewUrl(blob);

        setViewer((current) => {
          revokePdfUrl(current.pdfUrl);
          return {
            open: true,
            title: labels.title,
            subtitle,
            pdfUrl: url,
            filename,
            loading: false,
            blob,
          };
        });

        if (kind === 'synthesis') {
          toast({
            title: 'Guide simplifié prêt',
            description: labels.ready,
          });
        }
      } catch (err: unknown) {
        closeViewer();
        toast({
          title: 'Erreur',
          description: await parseApiErrorDetail(
            err,
            labels.generating.replace('…', ' impossible.')
          ),
          variant: 'destructive',
        });
      }
    },
    [closeViewer, revokePdfUrl, toast]
  );

  const downloadFromViewer = useCallback(() => {
    if (viewer.blob) {
      downloadBlob(viewer.blob, viewer.filename);
    }
  }, [viewer.blob, viewer.filename]);

  return {
    viewer,
    openDocument,
    closeViewer,
    downloadFromViewer,
  };
}
