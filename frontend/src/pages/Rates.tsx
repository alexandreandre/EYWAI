import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, AlertTriangle, Inbox } from "lucide-react";
import apiClient from "@/api/apiClient";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

// --- Types de Données (INCHANGÉ) ---

type RateCategory = {
  config_data: any;
  version: number;
  last_checked_at: string | null;
  comment: string | null;
  source_links: string[] | null;
};

type RatesResponse = Record<string, RateCategory>;

type Cotisation = {
  id: string;
  libelle: string;
  base: string;
  salarial?: null | number | Record<string, number>;
  patronal?: null | number | Record<string, number>;
  patronal_plein?: number;
  patronal_reduit?: number;
  salarial_Alsace_Moselle?: number;
};

// --- Composant Principal ---

export default function Rates() {
  const [data, setData] = useState<RatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRates = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.get<RatesResponse>("/api/rates/all");
        setData(response.data);
      } catch (e: any) {
        const errorMsg = e.response?.data?.detail || e.message || "Une erreur est survenue.";
        setError(errorMsg);
      } finally {
        setLoading(false);
      }
    };
    fetchRates();
  }, []);

  // --- Fonctions Utilitaires (INCHANGÉ) ---

  const formatDate = (d?: string | null) => {
    if (!d) return "Inconnue";
    return new Date(d).toLocaleString("fr-FR", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  };

  const formatPercent = (val: any): string => {
    if (val === null || val === undefined) return "-";
    const num = Number(val);
    if (isNaN(num)) return String(val);
    
    const v = num < 10 ? num * 100 : num;
    return `${v.toFixed(2).replace(".", ",")} %`;
  };

  const formatKey = (key: string): string => {
    return key
      .replace(/_/g, " ")
      .replace("taux moins 50", "Taux < 50")
      .replace("taux 50 et plus", "Taux 50+")
      .replace("patronal ", "")
      .replace("salarial ", "")
      .replace(/^./, (match) => match.toUpperCase());
  };

  /**
   * Retourne la classe de couleur en fonction de l'ancienneté de la date.
   * Vert: < 2 semaines, Orange: entre 2 semaines et 6 mois, Rouge: > 6 mois
   */
  const getDateColor = (d?: string | null): string => {
    if (!d) return "text-red-500";

    const checkDate = new Date(d);
    const now = new Date();
    const diffMs = now.getTime() - checkDate.getTime();
    const diffDays = diffMs / (1000 * 60 * 60 * 24);

    if (diffDays < 14) return "text-green-600";
    if (diffDays < 180) return "text-orange-500";
    return "text-red-500";
  };

  // --- Fonctions de Rendu Spécialisées (INCHANGÉ) ---

  /**
   * Affiche une valeur de taux, qu'elle soit simple (nombre) ou complexe (objet).
   */
  const renderRateValue = (value: any) => {
    if (value === null || value === undefined) {
      return <span className="text-muted-foreground">-</span>;
    }
    if (typeof value === "number") {
      return <span>{formatPercent(value)}</span>;
    }
    if (typeof value === "object") {
      return (
        <div className="flex flex-col items-end">
          {Object.entries(value).map(([key, val]) => (
            <div key={key}>
              <span className="text-xs text-muted-foreground">{formatKey(key)}: </span>
              <span className="font-medium">{formatPercent(val)}</span>
            </div>
          ))}
        </div>
      );
    }
    return <span>{String(value)}</span>;
  };

  /**
   * Affiche la carte la plus complexe : la liste des cotisations.
   * (Léger ajustement pour une meilleure densité)
   */
  const renderCotisations = (list: Cotisation[]) => {
    return (
      <div className="space-y-4">
        {list.map((coti) => (
          <div key={coti.id} className="border-b border-border/50 pb-3 last:border-b-0">
            <div className="flex justify-between items-start mb-1">
              <span className="font-medium text-foreground">{coti.libelle}</span>
              <Badge variant="secondary" className="text-xs whitespace-nowrap ml-2">{coti.base}</Badge>
            </div>
            <Table className="mt-1">
              <TableBody>
                {Object.entries(coti)
                  .filter(([key]) => 
                    key.includes("salarial") || key.includes("patronal")
                  )
                  .map(([key, value]) => (
                    <TableRow key={key}>
                      <TableCell className="text-muted-foreground p-1 text-xs h-auto">{formatKey(key)}</TableCell>
                      <TableCell className="text-right font-medium p-1 h-auto">
                        {renderRateValue(value)}
                      </TableCell>
                    </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ))}
      </div>
    );
  };

  /**
   * Affiche une simple liste de clé/valeur pour SMIC, PSS, etc.
   * (Ajustement pour un style plus "widget")
   */
  const renderSimpleObject = (obj: any, unit?: string) => (
    <Table>
      <TableBody>
        {Object.entries(obj).map(([k, v]) => (
          <TableRow key={k}>
            <TableCell className="p-1 h-auto text-muted-foreground">{formatKey(k)}</TableCell>
            <TableCell className="p-1 h-auto text-right font-bold text-lg text-foreground">
              {String(v)}{unit ? ` ${unit}` : ''}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );

  /**
   * Affiche les barèmes complexes (PAS, Frais Pro, Avantages).
   * (INCHANGÉ)
   */
  const renderComplexObject = (obj: any, title: string = ""): JSX.Element => {
    if (obj === null || obj === undefined) return <></>;

    if (Array.isArray(obj)) {
      return (
        <div className="space-y-2">
          {obj.map((item, index) => (
            <div key={index} className="border rounded-md p-2">
              {renderComplexObject(item, `Élément ${index + 1}`)}
            </div>
          ))}
        </div>
      );
    }

    if (typeof obj === "object") {
      return (
        <div className="space-y-2">
          {title && <div className="font-medium text-xs text-muted-foreground uppercase">{title}</div>}
          <div className="pl-2 space-y-1">
            {Object.entries(obj).map(([k, v]) => (
              <div key={k}>
                <div className="text-sm font-medium">{formatKey(k)}</div>
                <div className="pl-2">{renderComplexObject(v)}</div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    return <span className="font-medium">{String(obj)}</span>;
  };
  
  /**
   * Affiche la carte pour le Prélèvement à la Source (PAS).
   * (INCHANGÉ)
   */
  const renderPas = (obj: any) => (
    <div className="space-y-4">
      {obj.baremes.map((b: any) => (
        <div key={b.zone} className="border rounded-lg p-3">
          <div className="font-medium mb-2 capitalize">
            Zone : {b.zone.replaceAll("_", " ")}
          </div>
          <Table>
            <TableBody>
              {b.tranches.map((t: any, i: number) => (
                <TableRow key={i}>
                  <TableCell className="text-muted-foreground p-1 h-auto">Plafond : {t.plafond ?? "∞"} €</TableCell>
                  <TableCell className="text-right font-medium p-1 h-auto">{formatPercent(t.taux)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ))}
    </div>
  );

  // --- NOUVEAU : Composants "Widget" pour les petits blocs ---

  /**
   * Wrapper pour un "petit bloc" (SMIC, PSS).
   */
  const renderSimpleWidget = (
    title: string,
    cat: RateCategory,
    content: JSX.Element
  ) => (
    <Card className="shadow-sm hover:shadow-lg transition-all transform hover:-translate-y-1 flex flex-col">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-lg font-semibold">{title}</CardTitle>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="outline">v{cat.version ?? "?"}</Badge>
            </TooltipTrigger>
            <TooltipContent>
              <p>{cat.comment || "Version de la configuration"}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </CardHeader>
      <CardContent className="flex-grow">
        {content}
        <p className={`text-xs mt-4 text-right font-medium ${getDateColor(cat.last_checked_at)}`}>
          Contrôlé le: {formatDate(cat.last_checked_at)}
        </p>
      </CardContent>
    </Card>
  );

  /**
   * Wrapper pour un "bloc complexe" (PAS, Frais Pro).
   */
  const renderComplexWidget = (
    title: string,
    cat: RateCategory,
    content: JSX.Element
  ) => (
    <Card key={title} className="shadow-sm hover:shadow-lg transition-all transform hover:-translate-y-1 flex flex-col">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-lg font-semibold capitalize">
          {title.replaceAll("_", " ")}
        </CardTitle>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="outline">v{cat.version ?? "?"}</Badge>
            </TooltipTrigger>
            <TooltipContent>
              <p>{cat.comment || "Version de la configuration"}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </CardHeader>
      <CardContent className="flex-grow">
        {content}
        <p className={`text-xs mt-4 text-right font-medium ${getDateColor(cat.last_checked_at)}`}>
          Contrôlé le: {formatDate(cat.last_checked_at)}
        </p>
      </CardContent>
    </Card>
  );

  // --- Rendu des États (INCHANGÉ) ---

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-3 text-muted-foreground">Chargement des taux...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-500/50 bg-red-500/5">
        <CardHeader>
          <CardTitle className="flex items-center text-red-600">
            <AlertTriangle className="mr-2 h-5 w-5" />
            Échec du chargement des taux
          </CardTitle>
        </CardHeader>
        <CardContent className="text-red-500">
          <p>L'API a retourné une erreur :</p>
          <p className="font-mono bg-red-500/10 p-2 rounded-md mt-2 text-sm">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="flex flex-col justify-center items-center h-64 text-muted-foreground">
        <Inbox className="h-10 w-10" />
        <span className="mt-4 text-lg font-medium">Aucune donnée de configuration</span>
        <span className="text-sm">Aucune configuration active n'a été trouvée dans la base de données.</span>
      </div>
    );
  }

  // --- NOUVEAU : Rendu Principal (Organisation par Sections) ---

  return (
    <div className="space-y-12 animate-fade-in">
      {/* === EN-TÊTE === */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Suivi des Taux</h1>
        <p className="text-muted-foreground mt-1">
          Contrôle et gestion centralisée des taux et plafonds réglementaires actifs.
        </p>
      </div>

      {/* === SECTION 1: PARAMÈTRES CLÉS === */}
      <section>
        <h2 className="text-2xl font-semibold text-foreground mb-4 border-b border-border/70 pb-2">
          Paramètres Clés
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {data.smic && renderSimpleWidget("SMIC", data.smic, renderSimpleObject(data.smic.config_data.smic_horaire || data.smic.config_data, "€/h"))}
          {data.pss && renderSimpleWidget("Plafond Sécurité Sociale (PSS)", data.pss, renderSimpleObject(data.pss.config_data.pss || data.pss.config_data, "€"))}
          {data.ij_plafonds && renderSimpleWidget("Plafonds IJSS", data.ij_plafonds, renderSimpleObject(data.ij_plafonds.config_data.plafonds_indemnites_journalieres || data.ij_plafonds.config_data, "€/jour"))}
        </div>
      </section>

      {/* === SECTION 2: COTISATIONS SOCIALES === */}
      {data.cotisations && (
        <section>
          <div className="flex justify-between items-end mb-4 border-b border-border/70 pb-2">
            <h2 className="text-2xl font-semibold text-foreground">
              Cotisations Sociales
            </h2>
            {/* Métadonnées directement dans l'en-tête de section */}
            <div className="flex items-center gap-3 text-sm">
              <span className={`font-medium ${getDateColor(data.cotisations.last_checked_at)}`}>
                Dernier contrôle: {formatDate(data.cotisations.last_checked_at)}
              </span>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline">v{data.cotisations.version ?? "?"}</Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{data.cotisations.comment || "Version de la configuration"}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
          {/* La liste des cotisations dans un conteneur simple, pas une grosse Card */}
          <div className="bg-card border rounded-lg p-4 shadow-sm">
            {renderCotisations(data.cotisations.config_data.cotisations || [])}
          </div>
        </section>
      )}

      {/* === SECTION 3: BARÈMES & ABATTEMENTS (UI Corrigée) === */}
      <section>
        <h2 className="text-2xl font-semibold text-foreground mb-4 border-b border-border/70 pb-2">
          Barèmes & Abattements
        </h2>
        
        {/* Nous utilisons "column-count" pour créer une disposition en maçonnerie.
          - 'lg:column-count-2' : 2 colonnes sur les grands écrans.
          - 'gap-6' : Espace horizontal entre les colonnes.
          - 'space-y-6' : Espace vertical entre les éléments *dans* une même colonne.
          - 'break-inside-avoid' : Appliqué à chaque enfant pour éviter qu'une carte ne soit coupée en deux.
        */}
        <div className="lg:column-count-2 gap-6 space-y-6">
          
          {data.pas && (
            <div className="break-inside-avoid">
              {renderComplexWidget("Prélèvement à la source (PAS)", data.pas, renderPas(data.pas.config_data))}
            </div>
          )}
          
          {data.frais_pro && (
            <div className="break-inside-avoid">
              {renderComplexWidget("Frais professionnels", data.frais_pro, renderComplexObject(data.frais_pro.config_data.FRAIS_PRO?.[0]?.sections || {}))}
            </div>
          )}
          
          {data.avantages_en_nature && (
            <div className="break-inside-avoid">
              {renderComplexWidget("Avantages en nature", data.avantages_en_nature, renderComplexObject(data.avantages_en_nature.config_data || {}))}
            </div>
          )}
          
          {/* Fallback pour les autres clés non triées */}
          {Object.entries(data)
            .filter(([key]) => !['smic', 'pss', 'ij_plafonds', 'cotisations', 'pas', 'frais_pro', 'avantages_en_nature'].includes(key))
            .map(([key, cat]) => 
              cat?.config_data 
              ? (
                <div key={key} className="break-inside-avoid">
                  {renderComplexWidget(key, cat, renderComplexObject(cat.config_data))}
                </div>
              )
              : null
            )
          }
        </div>
      </section>
    </div>
  );
}