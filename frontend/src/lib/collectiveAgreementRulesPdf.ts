/**
 * Export PDF des règles paie extraites — 100 % côté navigateur, sans appel API.
 * Ouvre la boîte de dialogue d'impression (→ « Enregistrer au format PDF »).
 */

function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatEuro(value: unknown): string {
  const n = Number(value);
  if (Number.isNaN(n)) return escapeHtml(value);
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 2,
  }).format(n);
}

function formatPercent(value: unknown): string {
  const n = Number(value);
  if (Number.isNaN(n)) return escapeHtml(value);
  return `${n} %`;
}

type Grille = {
  zone_type?: string;
  zone_libelle?: string;
  departements?: string[];
  regions?: string[];
  date_effet?: string;
  source_titre?: string;
  minima?: Array<{ coefficient?: number; valeur?: number; libelle?: string | null }>;
};

function renderGrille(grille: Grille, index: number): string {
  const titre =
    grille.zone_libelle?.trim() ||
    grille.source_titre?.trim() ||
    `Grille ${index + 1}`;
  const meta: string[] = [];
  if (grille.zone_type) meta.push(`Type : ${escapeHtml(grille.zone_type)}`);
  if (grille.date_effet) meta.push(`Effet : ${escapeHtml(grille.date_effet)}`);
  if (grille.departements?.length) {
    meta.push(`Dép. : ${escapeHtml(grille.departements.join(', '))}`);
  }
  if (grille.regions?.length) {
    meta.push(`Régions : ${escapeHtml(grille.regions.join(', '))}`);
  }

  const rows = (grille.minima ?? [])
    .map(
      (m) => `
      <tr>
        <td>${escapeHtml(m.coefficient)}</td>
        <td>${escapeHtml(m.libelle ?? '—')}</td>
        <td class="num">${formatEuro(m.valeur)}</td>
      </tr>`
    )
    .join('');

  return `
    <section class="block">
      <h3>${escapeHtml(titre)}</h3>
      ${meta.length ? `<p class="meta">${meta.join(' · ')}</p>` : ''}
      ${
        rows
          ? `<table>
        <thead><tr><th>Coeff.</th><th>Libellé</th><th>Minimum</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`
          : '<p class="muted">Aucun minimum extrait pour cette grille.</p>'
      }
    </section>`;
}

function renderRulesDocumentHtml(params: {
  rules: Record<string, unknown>;
  agreementName: string;
  idcc: string;
}): string {
  const { rules, agreementName, idcc } = params;
  const completude = rules.completude as
    | { niveau?: string; grilles_count?: number; avertissements?: string[] }
    | undefined;
  const grilles = (rules.grilles_salaires as Grille[] | undefined) ?? [];
  const salairesLegacy = (rules.salaires_minima as Grille['minima']) ?? [];
  const prime = rules.prime_anciennete as
    | {
        bareme?: Array<{ annees_min?: number; taux?: number }>;
        base_de_calcul?: { methode?: string; valeur?: number };
      }
    | undefined;
  const meta = rules.meta as
    | { extracted_at?: string; model?: string; confidence?: string }
    | undefined;

  const avertissements = (completude?.avertissements ?? [])
    .map((msg) => `<li>${escapeHtml(msg)}</li>`)
    .join('');

  const baremeRows = (prime?.bareme ?? [])
    .map(
      (p) =>
        `<tr><td>${escapeHtml(p.annees_min)} an(s) et +</td><td class="num">${formatPercent(p.taux)}</td></tr>`
    )
    .join('');

  const legacyRows = (salairesLegacy ?? [])
    .map(
      (m) =>
        `<tr><td>${escapeHtml(m?.coefficient)}</td><td>${escapeHtml(m?.libelle ?? '—')}</td><td class="num">${formatEuro(m?.valeur)}</td></tr>`
    )
    .join('');

  const grillesHtml =
    grilles.length > 0
      ? grilles.map((g, i) => renderGrille(g, i)).join('')
      : legacyRows
        ? `<section class="block"><h2>Salaires minima</h2>
        <table><thead><tr><th>Coeff.</th><th>Libellé</th><th>Minimum</th></tr></thead>
        <tbody>${legacyRows}</tbody></table></section>`
        : '<p class="muted">Aucune grille salariale extraite.</p>';

  const generatedAt = new Date().toLocaleDateString('fr-FR');

  return `<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Règles paie — IDCC ${escapeHtml(idcc)}</title>
<style>
  @page { size: A4; margin: 18mm 16mm; }
  body { font-family: Arial, sans-serif; font-size: 10.5pt; color: #1e293b; line-height: 1.45; }
  h1 { font-size: 16pt; color: #1e3a8a; margin: 0 0 4px 0; }
  h2 { font-size: 13pt; color: #1e3a8a; margin: 20px 0 8px 0; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }
  h3 { font-size: 11pt; color: #334155; margin: 14px 0 6px 0; }
  .header { border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; margin-bottom: 18px; }
  .kicker { font-size: 8pt; letter-spacing: 0.1em; text-transform: uppercase; color: #1e3a8a; font-weight: 700; }
  .meta { font-size: 9pt; color: #64748b; margin: 4px 0 0 0; }
  .muted { color: #64748b; font-style: italic; }
  .block { margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 9.5pt; }
  th, td { border: 1px solid #cbd5e1; padding: 5px 7px; text-align: left; }
  th { background: #f1f5f9; }
  td.num { text-align: right; white-space: nowrap; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #e2e8f0; font-size: 9pt; }
  .warn { background: #fffbeb; border-left: 3px solid #f59e0b; padding: 8px 10px; margin: 10px 0; font-size: 9pt; }
  .footer { margin-top: 24px; font-size: 8pt; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 8px; }
  ul { margin: 6px 0; padding-left: 18px; }
</style></head><body>
<div class="header">
  <div class="kicker">Convention collective — Règles paie extraites</div>
  <h1>${escapeHtml(agreementName)}</h1>
  <p class="meta">IDCC ${escapeHtml(idcc)} · Généré le ${generatedAt}</p>
</div>

<section class="block">
  <h2>Synthèse extraction</h2>
  <p>
    Complétude : <span class="badge">${escapeHtml(completude?.niveau ?? 'inconnu')}</span>
    ${typeof completude?.grilles_count === 'number' ? ` · ${completude.grilles_count} grille(s) salariale(s)` : ''}
    ${meta?.confidence ? ` · Confiance : ${escapeHtml(meta.confidence)}` : ''}
  </p>
  ${
    avertissements
      ? `<div class="warn"><strong>Avertissements</strong><ul>${avertissements}</ul></div>`
      : ''
  }
</section>

<section class="block">
  <h2>Grilles salariales</h2>
  ${grillesHtml}
</section>

${
  prime
    ? `<section class="block">
  <h2>Prime d'ancienneté</h2>
  ${
    prime.base_de_calcul
      ? `<p class="meta">Base de calcul : ${escapeHtml(prime.base_de_calcul.methode ?? '—')}${prime.base_de_calcul.valeur != null ? ` (${escapeHtml(prime.base_de_calcul.valeur)})` : ''}</p>`
      : ''
  }
  ${
    baremeRows
      ? `<table><thead><tr><th>Ancienneté</th><th>Taux</th></tr></thead><tbody>${baremeRows}</tbody></table>`
      : '<p class="muted">Barème non extrait.</p>'
  }
</section>`
    : ''
}

<div class="footer">
  Document généré localement à partir des règles paie extraites (JSON).
  À titre informatif — vérifiez le texte officiel sur Légifrance et validez avec votre expert paie.
  ${meta?.extracted_at ? `Extraction : ${escapeHtml(meta.extracted_at)}` : ''}
  ${meta?.model ? ` · Modèle : ${escapeHtml(meta.model)}` : ''}
</div>
</body></html>`;
}

/** Ouvre l'impression navigateur pour enregistrer en PDF (aucun appel réseau). */
export function printRulesPdfFromJson(params: {
  rules: Record<string, unknown>;
  agreementName: string;
  idcc: string;
}): void {
  const html = renderRulesDocumentHtml(params);
  const iframe = document.createElement('iframe');
  iframe.setAttribute('aria-hidden', 'true');
  iframe.style.cssText =
    'position:fixed;right:0;bottom:0;width:0;height:0;border:none;visibility:hidden';
  document.body.appendChild(iframe);

  const doc = iframe.contentDocument ?? iframe.contentWindow?.document;
  if (!doc) {
    document.body.removeChild(iframe);
    throw new Error('Impossible de préparer le document PDF');
  }

  doc.open();
  doc.write(html);
  doc.close();

  const print = () => {
    iframe.contentWindow?.focus();
    iframe.contentWindow?.print();
    window.setTimeout(() => {
      if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
    }, 1500);
  };

  if (iframe.contentWindow?.document.readyState === 'complete') {
    window.setTimeout(print, 150);
  } else {
    iframe.onload = () => window.setTimeout(print, 150);
  }
}

export function hasCachedTextSource(source?: string | null): boolean {
  return source === 'kali' || source === 'text' || source === 'pdf';
}
