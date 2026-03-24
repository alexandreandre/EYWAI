import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";
import { useNavigate } from "react-router-dom";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
};

type State = {
  hasError: boolean;
  error: Error | null;
};

/**
 * Error Boundary pour afficher un fallback au lieu d'un écran blanc
 * quand un composant enfant lève une erreur.
 */
export class ErrorBoundaryClass extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.props.onError?.(error, errorInfo);
    console.error("[ErrorBoundary]", error, errorInfo);
  }

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <ErrorFallback error={this.state.error} />
      );
    }
    return this.props.children;
  }
}

function ErrorFallback({ error }: { error: Error }) {
  // useNavigate doit être utilisé dans un composant sous Router
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center min-h-[320px] p-6 text-center">
      <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
      <h2 className="text-lg font-semibold mb-2">Une erreur s&apos;est produite</h2>
      <p className="text-muted-foreground text-sm mb-4 max-w-md">{error.message}</p>
      <Button variant="outline" onClick={() => navigate("/")}>
        Retour à l&apos;accueil
      </Button>
    </div>
  );
}
