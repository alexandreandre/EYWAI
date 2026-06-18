// frontend/src/components/payslip-edit/PreviewPanel.tsx

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Eye, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface PreviewPanelProps {
  data: any;
  pdfNotes?: string;
  cumuls?: any;
}

export default function PreviewPanel({ data, pdfNotes, cumuls }: PreviewPanelProps) {
  const formatCurrency = (amount: number | undefined | null): string => {
    if (amount == null) return 'N/A';
    return amount.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
  };

  return (
    <div className="space-y-4">
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Cet aperçu montre une version HTML détaillée. Le PDF final sera généré lors de la sauvegarde.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader className="bg-primary text-primary-foreground">
          <CardTitle className="text-center text-2xl">
            Bulletin de Paie - {data.en_tete?.periode}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          {/* En-tête */}
          <div className="grid grid-cols-2 gap-6 pb-4 border-b-2">
            <div>
              <h3 className="font-bold mb-2 text-lg">Entreprise</h3>
              <p className="font-medium">{data.en_tete?.entreprise?.raison_sociale}</p>
              <p className="text-sm text-muted-foreground">
                SIRET: {data.en_tete?.entreprise?.siret}
              </p>
              {data.en_tete?.entreprise?.naf_ape && (
                <p className="text-sm text-muted-foreground">
                  NAF/APE: {data.en_tete.entreprise.naf_ape}
                </p>
              )}
              <p className="text-sm text-muted-foreground">
                {data.en_tete?.entreprise?.adresse?.rue}
              </p>
              <p className="text-sm text-muted-foreground">
                {data.en_tete?.entreprise?.adresse?.code_postal} {data.en_tete?.entreprise?.adresse?.ville}
              </p>
            </div>
            <div>
              <h3 className="font-bold mb-2 text-lg">Collaborateur</h3>
              <p className="font-medium">{data.en_tete?.salarie?.nom_complet}</p>
              <p className="text-sm text-muted-foreground">
                Emploi: {data.en_tete?.salarie?.emploi}
              </p>
              {data.en_tete?.salarie?.classification && (
                <p className="text-sm text-muted-foreground">
                  Classification: {data.en_tete.salarie.classification}
                </p>
              )}
              {data.en_tete?.salarie?.convention_collective && (
                <p className="text-sm text-muted-foreground">
                  CCN: {data.en_tete.salarie.convention_collective}
                </p>
              )}
              <p className="text-sm text-muted-foreground">
                Statut: {data.en_tete?.salarie?.statut}
              </p>
              <p className="text-sm text-muted-foreground">
                NIR: {data.en_tete?.salarie?.nir}
              </p>
            </div>
          </div>

          {/* Calcul du brut - avec absences et congés intégrés */}
          <div>
            <h3 className="font-bold mb-3 text-lg">Rémunération Brute</h3>
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th className="text-left p-2 font-medium">Libellé</th>
                    <th className="text-right p-2 font-medium">Base / Qté</th>
                    <th className="text-right p-2 font-medium">Taux</th>
                    <th className="text-right p-2 font-medium">Gains</th>
                    <th className="text-right p-2 font-medium">Retenues</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Lignes du calcul du brut */}
                  {data.calcul_du_brut && data.calcul_du_brut.map((ligne: any, idx: number) => (
                    <tr key={`brut-${idx}`} className={ligne.is_sous_total ? "border-t-2 bg-muted/50 font-bold" : "border-t"}>
                      <td className="p-2">{ligne.libelle}</td>
                      <td className="text-right p-2">
                        {!ligne.is_sous_total && ligne.quantite ? ligne.quantite.toFixed(2) : ''}
                      </td>
                      <td className="text-right p-2">
                        {!ligne.is_sous_total && ligne.taux ? ligne.taux.toFixed(4) : ''}
                      </td>
                      <td className="text-right p-2 font-medium text-green-600">
                        {ligne.gain ? formatCurrency(ligne.gain) : ''}
                      </td>
                      <td className="text-right p-2 font-medium text-red-600">
                        {ligne.perte ? formatCurrency(ligne.perte) : ''}
                      </td>
                    </tr>
                  ))}

                  {/* Absences */}
                  {data.details_absences && data.details_absences.map((absence: any, idx: number) => (
                    <tr key={`absence-${idx}`} className="border-t">
                      <td className="p-2">{absence.libelle}</td>
                      <td className="text-right p-2">{absence.quantite?.toFixed(2) || ''}</td>
                      <td className="text-right p-2">{absence.taux?.toFixed(4) || ''}</td>
                      <td className="text-right p-2 font-medium text-green-600">
                        {absence.gain ? formatCurrency(absence.gain) : ''}
                      </td>
                      <td className="text-right p-2 font-medium text-red-600">
                        {absence.perte ? formatCurrency(absence.perte) : ''}
                      </td>
                    </tr>
                  ))}

                  {/* Congés */}
                  {data.details_conges && data.details_conges.map((conge: any, idx: number) => (
                    <tr key={`conge-${idx}`} className="border-t">
                      <td className="p-2">{conge.libelle}</td>
                      <td className="text-right p-2">{conge.quantite?.toFixed(2) || ''}</td>
                      <td className="text-right p-2">{conge.taux?.toFixed(4) || ''}</td>
                      <td className="text-right p-2 font-medium text-green-600">
                        {conge.gain ? formatCurrency(conge.gain) : ''}
                      </td>
                      <td className="text-right p-2 font-medium text-red-600">
                        {conge.perte ? formatCurrency(conge.perte) : ''}
                      </td>
                    </tr>
                  ))}

                  {/* Total Salaire Brut */}
                  <tr className="border-t-2 bg-blue-50 font-bold">
                    <td className="p-2" colSpan={3}>Total Salaire Brut</td>
                    <td className="text-right p-2 text-blue-600" colSpan={2}>
                      {formatCurrency(data.salaire_brut)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Cotisations — regroupement officiel par risque */}
          {(data.cotisations_officielles?.length > 0 || data.structure_cotisations) && (
            <div>
              <h3 className="font-bold mb-3 text-lg">Cotisations et contributions sociales</h3>

              {data.cotisations_officielles && data.cotisations_officielles.length > 0 ? (
                data.cotisations_officielles.map((rubrique: any, rIdx: number) => (
                  <div key={`rub-${rIdx}`} className="mb-4">
                    <h4 className="font-medium mb-2 text-sm bg-muted/50 p-2 rounded">{rubrique.libelle}</h4>
                    <div className="border rounded-lg overflow-hidden">
                      <table className="w-full text-xs">
                        <thead className="bg-muted">
                          <tr>
                            <th className="text-left p-2">Libellé</th>
                            <th className="text-right p-2">Base</th>
                            <th className="text-right p-2">Montant Sal.</th>
                            <th className="text-right p-2">Montant Pat.</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rubrique.lignes?.map((cot: any, idx: number) => (
                            <tr key={idx} className="border-t text-xs">
                              <td className="p-2">{cot.libelle}</td>
                              <td className="text-right p-2">{formatCurrency(cot.base)}</td>
                              <td className="text-right p-2 text-red-600">{formatCurrency(cot.montant_salarial)}</td>
                              <td className="text-right p-2">{formatCurrency(cot.montant_patronal)}</td>
                            </tr>
                          ))}
                          <tr className="border-t bg-muted/30 font-semibold">
                            <td className="p-2" colSpan={2}>Sous-total</td>
                            <td className="text-right p-2 text-red-600">{formatCurrency(rubrique.total_salarial)}</td>
                            <td className="text-right p-2">{formatCurrency(rubrique.total_patronal)}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))
              ) : (
                /* Fallback structure_cotisations legacy */
                data.structure_cotisations?.bloc_principales && data.structure_cotisations.bloc_principales.length > 0 && (
                  <div className="mb-4">
                    <div className="border rounded-lg overflow-hidden">
                      <table className="w-full text-xs">
                        <thead className="bg-muted">
                          <tr>
                            <th className="text-left p-2">Libellé</th>
                            <th className="text-right p-2">Montant Sal.</th>
                            <th className="text-right p-2">Montant Pat.</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.structure_cotisations.bloc_principales.map((cot: any, idx: number) => (
                            <tr key={idx} className="border-t text-xs">
                              <td className="p-2">{cot.libelle}</td>
                              <td className="text-right p-2 text-red-600">{formatCurrency(cot.montant_salarial)}</td>
                              <td className="text-right p-2">{formatCurrency(cot.montant_patronal)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )
              )}

              {data.total_exonerations > 0 && (
                <div className="p-3 bg-green-50 rounded-lg mb-4 text-sm font-medium">
                  Exonérations, allègements et réductions (total) : {formatCurrency(data.total_exonerations)}
                </div>
              )}

              <div className="p-3 bg-blue-50 rounded-lg space-y-2 mt-4">
                <div className="flex justify-between font-bold text-base">
                  <span>Total Cotisations Salariales:</span>
                  <span className="text-red-600">
                    {formatCurrency(data.structure_cotisations?.total_salarial)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Primes non soumises */}
          {data.primes_non_soumises && data.primes_non_soumises.length > 0 && (
            <div>
              <h3 className="font-bold mb-3 text-lg">Primes Non Soumises</h3>
              <div className="border rounded-lg overflow-hidden bg-green-50">
                <table className="w-full text-sm">
                  <thead className="bg-green-100">
                    <tr>
                      <th className="text-left p-2 font-medium">Libellé</th>
                      <th className="text-right p-2 font-medium">Montant</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.primes_non_soumises.map((prime: any, idx: number) => (
                      <tr key={idx} className="border-t">
                        <td className="p-2">{prime.libelle}</td>
                        <td className="text-right p-2 font-medium text-green-600">
                          + {formatCurrency(prime.montant)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-2 text-right font-bold text-green-600">
                Total: + {formatCurrency(data.primes_non_soumises.reduce((sum: number, p: any) => sum + (p.montant || 0), 0))}
              </div>
            </div>
          )}

          {/* Notes de Frais */}
          {data.notes_de_frais && data.notes_de_frais.length > 0 && (
            <div>
              <h3 className="font-bold mb-3 text-lg">Notes de Frais</h3>
              <div className="border rounded-lg overflow-hidden bg-blue-50">
                <table className="w-full text-sm">
                  <thead className="bg-blue-100">
                    <tr>
                      <th className="text-left p-2 font-medium">Libellé</th>
                      <th className="text-left p-2 font-medium">Type</th>
                      <th className="text-center p-2 font-medium">Date</th>
                      <th className="text-right p-2 font-medium">Montant</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.notes_de_frais.map((note: any, idx: number) => (
                      <tr key={idx} className="border-t">
                        <td className="p-2">{note.libelle}</td>
                        <td className="p-2">{note.type}</td>
                        <td className="text-center p-2">{note.date}</td>
                        <td className="text-right p-2 font-medium text-blue-600">
                          + {formatCurrency(note.montant)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-2 text-right font-bold text-blue-600">
                Total: + {formatCurrency(data.notes_de_frais.reduce((sum: number, n: any) => sum + (n.montant || 0), 0))}
              </div>
            </div>
          )}

          {/* Notes PDF */}
          {pdfNotes && (
            <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
              <h3 className="font-bold mb-2 text-yellow-900 flex items-center gap-2">
                <Eye className="h-4 w-4" />
                Notes (visibles sur le PDF)
              </h3>
              <p className="text-sm text-yellow-800 whitespace-pre-wrap">{pdfNotes}</p>
            </div>
          )}

          {/* Synthèse Net - Format correspondant au bulletin réel */}
          <div className="border-t-2 pt-6 space-y-3">
            <div className="space-y-3">
              {data.synthese_net?.montant_net_social != null && (
                <div className="flex justify-between py-2 border-b font-bold text-base text-blue-700">
                  <span>Montant net social:</span>
                  <span>{formatCurrency(data.synthese_net.montant_net_social)}</span>
                </div>
              )}

              <div className="flex justify-between py-2 border-b font-bold text-base">
                <span>Net à payer avant impôt:</span>
                <span className="text-green-600">
                  {formatCurrency(data.synthese_net?.net_social_avant_impot)}
                </span>
              </div>

              <div className="flex justify-between py-2 border-b font-medium text-base">
                <span>Net Imposable:</span>
                <span>
                  {formatCurrency(data.synthese_net?.net_imposable)}
                </span>
              </div>

              {data.synthese_net?.impot_prelevement_a_la_source && (
                <div className="flex justify-between py-2 border-b font-medium text-base">
                  <span>Impôt sur le revenu (Prélèvement à la source):</span>
                  <span className="text-red-600">
                    - {formatCurrency(data.synthese_net.impot_prelevement_a_la_source.montant)}
                  </span>
                </div>
              )}

              {data.synthese_net?.remboursement_transport && data.synthese_net.remboursement_transport > 0 && (
                <div className="flex justify-between py-2 border-b text-green-600 font-medium">
                  <span>Remboursement transport (50%):</span>
                  <span className="font-medium">
                    + {formatCurrency(data.synthese_net.remboursement_transport)}
                  </span>
                </div>
              )}

              {data.synthese_net?.indemnite_transport_fixe && data.synthese_net.indemnite_transport_fixe > 0 && (
                <div className="flex justify-between py-2 border-b text-green-600 font-medium">
                  <span>Indemnité transport contractuelle:</span>
                  <span className="font-medium">
                    + {formatCurrency(data.synthese_net.indemnite_transport_fixe)}
                  </span>
                </div>
              )}
            </div>

            <div className="flex justify-between text-2xl font-bold text-green-600 py-4 border-t-4 border-green-600 mt-4">
              <span>NET À PAYER:</span>
              <span>{formatCurrency(data.net_a_payer)}</span>
            </div>
            {data.en_tete?.date_paiement && (
              <div className="flex justify-between py-2 text-sm text-muted-foreground">
                <span>Date de paiement:</span>
                <span>{data.en_tete.date_paiement}</span>
              </div>
            )}
          </div>

          {/* Total versé par l'employeur */}
          {data.pied_de_page && (
            <div className="text-base border-t-2 pt-4 mt-4 space-y-2">
              <div className="flex justify-between font-bold text-lg">
                <span>Total versé par l'employeur:</span>
                <span className="text-xl">
                  {formatCurrency(data.pied_de_page.cout_total_employeur)}
                </span>
              </div>
              {data.pied_de_page.total_exonerations > 0 && (
                <div className="flex justify-between text-sm text-muted-foreground">
                  <span>Total exonérations et allègements:</span>
                  <span>{formatCurrency(data.pied_de_page.total_exonerations)}</span>
                </div>
              )}
            </div>
          )}

          {/* Cumuls annuels */}
          {cumuls && cumuls.cumuls && (
            <div className="mt-8 p-6 bg-gradient-to-br from-amber-50 to-yellow-50 border-2 border-amber-500 rounded-lg">
              <h3 className="text-xl font-bold text-amber-800 text-center mb-6 pb-3 border-b-2 border-amber-500">
                Cumuls de l'Année {cumuls.periode?.annee_en_cours}
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white border border-amber-300 rounded-lg p-4 text-center shadow-sm">
                  <div className="text-xs font-bold text-amber-900 uppercase mb-2 tracking-wide">
                    Salaire Brut Total
                  </div>
                  <div className="text-lg font-bold text-blue-900 font-mono">
                    {formatCurrency(cumuls.cumuls.brut_total)}
                  </div>
                </div>
                <div className="bg-white border border-amber-300 rounded-lg p-4 text-center shadow-sm">
                  <div className="text-xs font-bold text-amber-900 uppercase mb-2 tracking-wide">
                    Net Imposable
                  </div>
                  <div className="text-lg font-bold text-blue-900 font-mono">
                    {formatCurrency(cumuls.cumuls.net_imposable)}
                  </div>
                </div>
                <div className="bg-white border border-amber-300 rounded-lg p-4 text-center shadow-sm">
                  <div className="text-xs font-bold text-amber-900 uppercase mb-2 tracking-wide">
                    Impôt à la Source
                  </div>
                  <div className="text-lg font-bold text-blue-900 font-mono">
                    {formatCurrency(cumuls.cumuls.impot_preleve_a_la_source)}
                  </div>
                </div>
                <div className="bg-white border border-amber-300 rounded-lg p-4 text-center shadow-sm">
                  <div className="text-xs font-bold text-amber-900 uppercase mb-2 tracking-wide">
                    Heures Rémunérées
                  </div>
                  <div className="text-lg font-bold text-green-700 font-mono">
                    {cumuls.cumuls.heures_remunerees?.toFixed(2)} h
                  </div>
                </div>
                <div className="bg-white border border-amber-300 rounded-lg p-4 text-center shadow-sm">
                  <div className="text-xs font-bold text-amber-900 uppercase mb-2 tracking-wide">
                    Heures Supplémentaires
                  </div>
                  <div className="text-lg font-bold text-green-700 font-mono">
                    {cumuls.cumuls.heures_supplementaires_remunerees?.toFixed(2)} h
                  </div>
                </div>
                {cumuls.cumuls.reduction_generale_patronale && (
                  <div className="bg-white border border-amber-300 rounded-lg p-4 text-center shadow-sm">
                    <div className="text-xs font-bold text-amber-900 uppercase mb-2 tracking-wide">
                      Réduction Générale
                    </div>
                    <div className="text-lg font-bold text-blue-900 font-mono">
                      {formatCurrency(Math.abs(cumuls.cumuls.reduction_generale_patronale))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
