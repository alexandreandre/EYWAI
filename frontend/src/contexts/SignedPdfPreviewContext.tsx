import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { SignedPdfPreviewDialog } from '@/components/documents/SignedPdfPreviewDialog';
import { createBlobPreviewUrl, downloadBlob } from '@/lib/downloadBlob';
import { registerSignedPdfPreviewOpener, registerSignedPdfBlobOpener } from '@/lib/openSignedUrlPreview';

const PREVIEW_LOAD_ERROR = 'Échec de chargement du document PDF.';

type PreviewOptions = {
  title?: string;
  subtitle?: string;
  downloadUrl?: string | null;
  downloadName?: string;
};

type PreviewState = {
  open: boolean;
  title: string;
  subtitle: string;
  pdfUrl: string | null;
  loading: boolean;
  error: string | null;
  downloadUrl: string | null;
  downloadName: string;
  blob: Blob | null;
};

const EMPTY_STATE: PreviewState = {
  open: false,
  title: 'Aperçu du document',
  subtitle: '',
  pdfUrl: null,
  loading: false,
  error: null,
  downloadUrl: null,
  downloadName: 'document.pdf',
  blob: null,
};

type SignedPdfPreviewContextValue = {
  openPreview: (url: string, options?: PreviewOptions) => void;
};

const SignedPdfPreviewContext = createContext<SignedPdfPreviewContextValue | null>(null);

async function fetchPreviewBlob(url: string): Promise<Blob> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(PREVIEW_LOAD_ERROR);
  }
  const blob = await response.blob();
  if (blob.size === 0) {
    throw new Error(PREVIEW_LOAD_ERROR);
  }
  const type = blob.type.toLowerCase();
  if (type.includes('json') || type.includes('html')) {
    throw new Error(PREVIEW_LOAD_ERROR);
  }
  if (type.includes('pdf')) {
    return blob;
  }
  if (type.startsWith('image/')) {
    return blob;
  }
  return new Blob([blob], { type: 'application/pdf' });
}

export function SignedPdfPreviewProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PreviewState>(EMPTY_STATE);
  const pdfUrlRef = useRef<string | null>(null);
  const loadIdRef = useRef(0);

  const revokePdfUrl = useCallback((url: string | null) => {
    if (url?.startsWith('blob:')) {
      URL.revokeObjectURL(url);
    }
  }, []);

  useEffect(() => {
    pdfUrlRef.current = state.pdfUrl;
  }, [state.pdfUrl]);

  useEffect(() => {
    return () => revokePdfUrl(pdfUrlRef.current);
  }, [revokePdfUrl]);

  const closePreview = useCallback(() => {
    loadIdRef.current += 1;
    setState((current) => {
      revokePdfUrl(current.pdfUrl);
      return { ...EMPTY_STATE };
    });
  }, [revokePdfUrl]);

  const openPreview = useCallback(
    (url: string, options?: PreviewOptions) => {
      const trimmed = url.trim();
      if (!trimmed) return;

      const loadId = loadIdRef.current + 1;
      loadIdRef.current = loadId;

      setState((current) => {
        revokePdfUrl(current.pdfUrl);
        return {
          open: true,
          title: options?.title?.trim() || 'Aperçu du document',
          subtitle: options?.subtitle?.trim() || '',
          pdfUrl: null,
          loading: true,
          error: null,
          downloadUrl: options?.downloadUrl?.trim() || trimmed,
          downloadName: options?.downloadName?.trim() || 'document.pdf',
          blob: null,
        };
      });

      void (async () => {
        try {
          const blob = await fetchPreviewBlob(trimmed);
          if (loadIdRef.current !== loadId) return;
          const objectUrl = createBlobPreviewUrl(blob);
          setState((current) => {
            if (loadIdRef.current !== loadId) {
              revokePdfUrl(objectUrl);
              return current;
            }
            revokePdfUrl(current.pdfUrl);
            return {
              ...current,
              pdfUrl: objectUrl,
              loading: false,
              error: null,
              blob,
            };
          });
        } catch {
          if (loadIdRef.current !== loadId) return;
          setState((current) => ({
            ...current,
            loading: false,
            error: PREVIEW_LOAD_ERROR,
            pdfUrl: null,
            blob: null,
          }));
        }
      })();
    },
    [revokePdfUrl]
  );

  const openBlobPreview = useCallback(
    (blob: Blob, options?: PreviewOptions) => {
      const loadId = loadIdRef.current + 1;
      loadIdRef.current = loadId;
      const objectUrl = createBlobPreviewUrl(blob);

      setState((current) => {
        revokePdfUrl(current.pdfUrl);
        return {
          open: true,
          title: options?.title?.trim() || 'Aperçu du document',
          subtitle: options?.subtitle?.trim() || '',
          pdfUrl: objectUrl,
          loading: false,
          error: null,
          downloadUrl: options?.downloadUrl?.trim() || null,
          downloadName: options?.downloadName?.trim() || 'document.pdf',
          blob,
        };
      });
    },
    [revokePdfUrl]
  );

  useEffect(() => {
    registerSignedPdfPreviewOpener(openPreview);
    registerSignedPdfBlobOpener(openBlobPreview);
    return () => {
      registerSignedPdfPreviewOpener(null);
      registerSignedPdfBlobOpener(null);
    };
  }, [openPreview, openBlobPreview]);

  const handleDownload = useCallback(() => {
    if (state.blob) {
      downloadBlob(state.blob, state.downloadName);
      return;
    }
    const href = state.downloadUrl?.trim();
    if (!href) return;
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.download = state.downloadName;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  }, [state.blob, state.downloadName, state.downloadUrl]);

  return (
    <SignedPdfPreviewContext.Provider value={{ openPreview }}>
      {children}
      <SignedPdfPreviewDialog
        open={state.open}
        onOpenChange={(open) => {
          if (!open) closePreview();
        }}
        title={state.title}
        subtitle={state.subtitle || undefined}
        pdfUrl={state.pdfUrl}
        loading={state.loading}
        error={state.error}
        canDownload={Boolean(state.blob || state.downloadUrl)}
        onDownload={handleDownload}
      />
    </SignedPdfPreviewContext.Provider>
  );
}

export function useSignedPdfPreview() {
  const ctx = useContext(SignedPdfPreviewContext);
  if (!ctx) {
    throw new Error('useSignedPdfPreview must be used within SignedPdfPreviewProvider');
  }
  return ctx;
}
