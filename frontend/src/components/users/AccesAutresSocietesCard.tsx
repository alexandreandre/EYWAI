/**
 * Carte « Accès aux sociétés » de l'écran de modification d'un utilisateur.
 *
 * Montre les sociétés où la personne a déjà accès et permet de lui en ouvrir
 * d'autres sans créer de nouveau compte (POST /api/users/grant-access-by-user-id).
 * On ne propose que les sociétés que la personne connectée administre.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Building2, CheckCircle2, AlertCircle, Loader2, Plus } from 'lucide-react';
import {
  getAccessibleCompaniesForUserCreation,
  getUserCompanyAccesses,
  grantCompanyAccessByUserId,
  type AccessibleCompany,
} from '@/api/permissions';
import {
  messageResultatAcces,
  roleParDefaut,
  rolesDonnables,
  societesProposables,
} from '@/lib/accesAutresSocietes';
import { getRoleDisplayLabel, type AppUserRole } from '@/lib/userRoleLabels';
import { log } from '@/lib/logger';

type AccesActuel = { company_id: string; company_name: string; role: string };

function raisonErreur(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' && detail ? detail : 'erreur du serveur';
}

interface Props {
  userId: string;
  /** Rôle de la personne dans la société active, proposé par défaut. */
  roleActuel?: string | null;
}

const AccesAutresSocietesCard: React.FC<Props> = ({ userId, roleActuel }) => {
  const [chargement, setChargement] = useState(true);
  const [erreurChargement, setErreurChargement] = useState<string | null>(null);
  const [accesActuels, setAccesActuels] = useState<AccesActuel[]>([]);
  const [administrables, setAdministrables] = useState<AccessibleCompany[]>([]);

  const [ouvert, setOuvert] = useState(false);
  const [cochees, setCochees] = useState<string[]>([]);
  const [role, setRole] = useState<AppUserRole | ''>('');
  const [enregistrement, setEnregistrement] = useState(false);
  const [succes, setSucces] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async () => {
    setChargement(true);
    setErreurChargement(null);
    try {
      const [acces, societes] = await Promise.all([
        getUserCompanyAccesses(userId),
        getAccessibleCompaniesForUserCreation(),
      ]);
      setAccesActuels(acces);
      setAdministrables(societes);
    } catch (err) {
      log.error('[AccesAutresSocietesCard] chargement', err);
      setErreurChargement(
        `Impossible de lire les sociétés de cette personne (${raisonErreur(err)}).`,
      );
    } finally {
      setChargement(false);
    }
  }, [userId]);

  useEffect(() => {
    void charger();
  }, [charger]);

  const proposables = useMemo(
    () => societesProposables(administrables, accesActuels),
    [administrables, accesActuels],
  );
  const societesCochees = useMemo(
    () => proposables.filter((s) => cochees.includes(s.company_id)),
    [proposables, cochees],
  );
  const roles = useMemo(() => rolesDonnables(societesCochees), [societesCochees]);

  // Le rôle choisi doit rester permis dans toutes les sociétés cochées.
  useEffect(() => {
    if (role && roles.includes(role)) return;
    setRole(roleParDefaut(roles, roleActuel));
  }, [roles, role, roleActuel]);

  const basculer = (companyId: string) => {
    setSucces(null);
    setErreur(null);
    setCochees((prev) =>
      prev.includes(companyId) ? prev.filter((id) => id !== companyId) : [...prev, companyId],
    );
  };

  const enregistrer = async () => {
    if (societesCochees.length === 0) {
      setErreur('Cochez au moins une société.');
      return;
    }
    if (!role) {
      setErreur('Aucun rôle commun ne peut être donné dans toutes les sociétés cochées.');
      return;
    }
    setEnregistrement(true);
    setSucces(null);
    setErreur(null);
    const reussies: string[] = [];
    const echouees: Array<{ nom: string; raison: string }> = [];
    for (const societe of societesCochees) {
      try {
        await grantCompanyAccessByUserId({
          user_id: userId,
          company_id: societe.company_id,
          role,
        });
        reussies.push(societe.company_name);
      } catch (err) {
        log.error('[AccesAutresSocietesCard] accès', err);
        echouees.push({ nom: societe.company_name, raison: raisonErreur(err) });
      }
    }
    const message = messageResultatAcces(reussies, echouees, role);
    setSucces(message.succes);
    setErreur(message.erreur);
    setEnregistrement(false);
    setCochees([]);
    if (echouees.length === 0) setOuvert(false);
    await charger();
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Building2 className="h-6 w-6 text-blue-600" />
          <h2 className="text-xl font-semibold text-gray-900">Accès aux sociétés</h2>
        </div>
        {!chargement && !erreurChargement && proposables.length > 0 && !ouvert && (
          <button
            type="button"
            onClick={() => {
              setOuvert(true);
              setSucces(null);
              setErreur(null);
            }}
            className="px-4 py-2 border border-blue-600 text-blue-700 rounded-lg hover:bg-blue-50 transition-colors flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Donner accès à d&apos;autres sociétés
          </button>
        )}
      </div>

      {chargement && (
        <p className="text-sm text-gray-500 flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Lecture des sociétés…
        </p>
      )}

      {erreurChargement && <p className="text-sm text-red-700">{erreurChargement}</p>}

      {!chargement && !erreurChargement && (
        <>
          <p className="text-sm text-gray-700 mb-2">
            {accesActuels.length === 0
              ? "Aucune société visible pour cette personne."
              : `A accès à ${accesActuels.length} société${accesActuels.length > 1 ? 's' : ''} :`}
          </p>
          {accesActuels.length > 0 && (
            <ul className="text-sm text-gray-800 space-y-1 mb-4">
              {accesActuels.map((a) => (
                <li key={a.company_id}>
                  {a.company_name}{' '}
                  <span className="text-gray-500">
                    ({getRoleDisplayLabel(a.role as AppUserRole)})
                  </span>
                </li>
              ))}
            </ul>
          )}

          {proposables.length === 0 && (
            <p className="text-sm text-gray-500">
              Aucune autre société à ouvrir : la personne a déjà accès à toutes les sociétés que
              vous administrez.
            </p>
          )}

          {ouvert && proposables.length > 0 && (
            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-4">
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">
                  Sociétés à ouvrir (celles que vous administrez)
                </p>
                <div className="space-y-2">
                  {proposables.map((s) => (
                    <label
                      key={s.company_id}
                      className="flex items-center gap-2 text-sm text-gray-800 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={cochees.includes(s.company_id)}
                        onChange={() => basculer(s.company_id)}
                        className="h-4 w-4"
                      />
                      {s.company_name}
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label
                  htmlFor="acces-autres-societes-role"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Rôle dans ces sociétés
                </label>
                {societesCochees.length === 0 ? (
                  <p className="text-sm text-gray-500">Cochez d&apos;abord une société.</p>
                ) : roles.length === 0 ? (
                  <p className="text-sm text-red-700">
                    Aucun rôle ne peut être donné dans toutes ces sociétés à la fois : enregistrez-les
                    en deux fois.
                  </p>
                ) : (
                  <select
                    id="acces-autres-societes-role"
                    value={role}
                    onChange={(e) => setRole(e.target.value as AppUserRole)}
                    className="w-full sm:w-auto px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    {roles.map((r) => (
                      <option key={r} value={r}>
                        {getRoleDisplayLabel(r)}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setOuvert(false);
                    setCochees([]);
                    setErreur(null);
                  }}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                >
                  Annuler
                </button>
                <button
                  type="button"
                  onClick={() => void enregistrer()}
                  disabled={enregistrement || societesCochees.length === 0 || !role}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
                >
                  {enregistrement && <Loader2 className="h-4 w-4 animate-spin" />}
                  Enregistrer
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {succes && (
        <p className="mt-4 text-sm text-green-800 bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" />
          {succes}
        </p>
      )}
      {erreur && (
        <p className="mt-4 text-sm text-red-800 bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          {erreur}
        </p>
      )}
    </div>
  );
};

export default AccesAutresSocietesCard;
