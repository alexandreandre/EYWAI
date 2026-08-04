"""Vue de présentation du bulletin de paie — gabarit Cegid.

Transforme le `bulletin_final` produit par le moteur en boîtes prêtes à
afficher. Fonction pure : aucun accès base, fichier ou horloge, tout vient du
dictionnaire reçu. C'est le seul endroit où vivent les replis, les agrégations
et le formatage — le template ne fait que parcourir le résultat.
"""

from __future__ import annotations

import calendar
from typing import Any, Dict, List, Optional

CIVILITES_MASCULINES = {"M", "H", "MR", "MASCULIN", "1"}
CIVILITES_FEMININES = {"F", "MME", "FEMININ", "FÉMININ", "2"}

# Découpage du NIR tel que Cegid l'imprime : 1 02 09 85 191 239 74
GROUPES_NIR = (1, 2, 2, 2, 3, 3, 2)

# Codes de rubriques du bulletin Cegid. Vérifiés sur les bulletins de juin 2026
# des sept sociétés : ce sont les seuls utilisés, il n'existe pas de Q700.
# La prévoyance et la mutuelle n'ont pas de code chez Cegid (références de
# contrat internes à son paramétrage) : elles restent sans code chez nous.
CODES_CEGID: Dict[str, str] = {
    "sante": "Q100",
    "at_mp": "Q200",
    "retraite": "Q300",
    "famille": "Q400",
    "chomage": "Q500",
    "autres_contributions_employeur": "Q600",
    "csg_deductible": "Q800",
    "csg_non_deductible": "Q801",
    "exonerations": "Q802",
}

LIBELLES_CEGID: Dict[str, str] = {
    "sante": "SANTÉ",
    "at_mp": "AT-MP",
    "retraite": "RETRAITE",
    "famille": "FAMILLE",
    "chomage": "ASSURANCE CHÔMAGE",
    "autres_contributions_employeur": "AUTRES CONTRIB. DUES PAR EMPL.",
    "cotisations_statutaires": "COTISATIONS STATUTAIRES ET CONVENTIONNELLES",
    "csg_deductible": "CSG DÉDUCTIBLE À L'IR",
    "csg_non_deductible": "CSG/CRDS NON DÉDUCTIBLE À L'IR",
    "exonerations": "EXO., ÉCRÊT. ET ALLÈG. COTIS",
}

# La CSG/CRDS non déductible est imprimée après le net imposable et n'entre pas
# dans le total des retenues (vérifié sur CARTOL juin 2026 : 308,14 sans elle).
RUBRIQUE_APRES_NET_IMPOSABLE = "csg_non_deductible"

# Cotisations salariales supprimées en 2018 (maladie 0,75 % + chômage 2,40 %)
# et hausse de CSG qui les a compensées (1,7 %). Formule retrouvée sur le
# bulletin CARTOL de juin 2026, exacte au centime.
TAUX_COTISATIONS_SUPPRIMEES = 0.0315
TAUX_HAUSSE_CSG = 0.017

MENTION_EVOLUTION_REMUNERATION = (
    "dont évolution de la rémunération liée à la suppression des cotisations "
    "salariales chômage et maladie"
)

MODES_PAIEMENT = {
    "virement": "par Virement",
    "cheque": "par Chèque",
    "chèque": "par Chèque",
    "especes": "en Espèces",
    "espèces": "en Espèces",
}


def _civilite(sexe: Any) -> Optional[str]:
    valeur = str(sexe or "").strip().upper()
    if valeur in CIVILITES_MASCULINES:
        return "MR"
    if valeur in CIVILITES_FEMININES:
        return "MME"
    return None


def _formater_nir(valeur: Any) -> str:
    brut = "".join(c for c in str(valeur or "") if c.isalnum()).upper()
    if len(brut) != 15:
        return brut
    morceaux: List[str] = []
    position = 0
    for taille in GROUPES_NIR:
        morceaux.append(brut[position : position + taille])
        position += taille
    return " ".join(morceaux)


def _date_fr(valeur: Any) -> str:
    if not valeur:
        return ""
    texte = str(valeur)[:10]
    if len(texte) == 10 and texte[4] == "-" and texte[7] == "-":
        return f"{texte[8:10]}/{texte[5:7]}/{texte[0:4]}"
    return texte


def _lignes_adresse(adresse: Any) -> List[str]:
    """Adresse postale sur deux lignes : rue, puis code postal + ville."""
    if not isinstance(adresse, dict):
        return []
    lignes: List[str] = []
    rue = str(adresse.get("rue") or "").strip()
    if rue:
        lignes.append(rue)
    localite = f"{adresse.get('code_postal') or ''} {adresse.get('ville') or ''}".strip()
    if localite:
        lignes.append(localite)
    return lignes


def construire_bandeau(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    en_tete = bulletin.get("en_tete") or {}
    entreprise = en_tete.get("entreprise") or {}
    annee = en_tete.get("annee")
    mois = en_tete.get("mois")
    du = au = ""
    if annee and mois:
        dernier_jour = calendar.monthrange(int(annee), int(mois))[1]
        du = f"01/{int(mois):02d}/{int(annee)}"
        au = f"{dernier_jour:02d}/{int(mois):02d}/{int(annee)}"
    return {
        "raison_sociale": entreprise.get("raison_sociale") or "",
        "adresse": _lignes_adresse(entreprise.get("adresse")),
        "siret": entreprise.get("siret") or "",
        "naf_ape": entreprise.get("naf_ape") or "",
        "periode": en_tete.get("periode") or "",
        # Le moteur produit une date ISO ; le bulletin s'imprime en français.
        "date_paiement": _date_fr(en_tete.get("date_paiement")),
        "du": du,
        "au": au,
    }


def construire_salarie(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    nom = str(salarie.get("nom") or "").strip()
    prenom = str(salarie.get("prenom") or "").strip()
    if nom:
        nom_ligne = f"{nom.upper()} {prenom}".strip()
    else:
        nom_ligne = str(salarie.get("nom_complet") or "").strip()
    return {
        "civilite": _civilite(salarie.get("sexe")),
        "nom_ligne": nom_ligne,
        "adresse": _lignes_adresse(salarie.get("adresse")),
    }


def construire_identite(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    classification = salarie.get("classification_brute")
    if not isinstance(classification, dict):
        classification = {}
    date_entree = _date_fr(salarie.get("date_entree"))
    return {
        "matricule": salarie.get("matricule") or "",
        "nir": _formater_nir(salarie.get("nir")),
        "date_entree": date_entree,
        "emploi": salarie.get("emploi") or "",
        # Repli documenté : 81 actifs sur 241 n'ont pas de date de reprise
        # d'ancienneté, leur ancienneté part de la date d'entrée.
        "anciennete": _date_fr(salarie.get("date_anciennete")) or date_entree,
        "qualification": classification.get("qualification") or "",
        "classification": classification.get("niveau")
        or classification.get("classification")
        or "",
        "coefficient": classification.get("coefficient") or "",
    }


def _colonne_compteur(titre: str, compteur: Any) -> Dict[str, Any]:
    donnees = compteur if isinstance(compteur, dict) else {}
    return {
        "titre": titre,
        "acquis": float(donnees.get("acquis") or 0.0),
        "pris": float(donnees.get("pris") or 0.0),
        "solde": float(donnees.get("solde") or 0.0),
    }


def _compteur_alimente(compteur: Any) -> bool:
    donnees = compteur if isinstance(compteur, dict) else {}
    return any(float(donnees.get(cle) or 0.0) for cle in ("acquis", "pris", "solde"))


def construire_compteurs(bulletin: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    solde = ((bulletin.get("pied_de_page") or {}).get("solde_conges")) or {}
    if not solde:
        return None

    colonnes: List[Dict[str, Any]] = []
    precedente = solde.get("conges_payes_periode_precedente")
    if _compteur_alimente(precedente):
        colonnes.append(_colonne_compteur("CP N-1", precedente))
    colonnes.append(_colonne_compteur("CP N", solde.get("conges_payes")))
    if _compteur_alimente(solde.get("rtt")):
        colonnes.append(_colonne_compteur("RTT", solde.get("rtt")))
    if _compteur_alimente(solde.get("repos_compensateur")):
        colonnes.append(
            _colonne_compteur("Repos comp.", solde.get("repos_compensateur"))
        )

    notes: List[str] = []
    fractionnement = solde.get("fractionnement") or {}
    if float(fractionnement.get("jours_acquis") or 0) > 0:
        libelle = fractionnement.get("libelle") or "Jours de fractionnement"
        reference = fractionnement.get("reference_date")
        notes.append(f"{libelle} (réf. {reference})" if reference else str(libelle))
    jours_anciennete = float(solde.get("cp_seniority_days") or 0)
    if jours_anciennete > 0:
        notes.append(f"Dont {jours_anciennete:.0f} j CP ancienneté conventionnels")
    if solde.get("cp_seniority_forfait_note"):
        notes.append(str(solde["cp_seniority_forfait_note"]))

    return {
        "date_reference": solde.get("date_reference") or "",
        "colonnes": colonnes,
        "notes": notes,
    }


def _ligne(
    type_ligne: str,
    libelle: str,
    *,
    code: Optional[str] = None,
    base: Optional[float] = None,
    taux: Optional[float] = None,
    montant_salarial: Optional[float] = None,
    montant_patronal: Optional[float] = None,
) -> Dict[str, Any]:
    return {
        "type": type_ligne,
        "code": code,
        "libelle": libelle,
        "base": base,
        "taux": taux,
        "montant_salarial": montant_salarial,
        "montant_patronal": montant_patronal,
    }


def _ligne_brut(source: Dict[str, Any]) -> Dict[str, Any]:
    """Une ligne de rémunération : le gain va au salarial, la perte le diminue."""
    gain = source.get("gain")
    perte = source.get("perte")
    montant = None
    if gain is not None:
        montant = float(gain)
    elif perte is not None:
        montant = -float(perte)
    return _ligne(
        "detail",
        source.get("libelle") or "",
        base=source.get("quantite"),
        taux=source.get("taux"),
        montant_salarial=montant,
    )


def _montant_ou_vide(valeur: Any) -> Optional[float]:
    """Cegid laisse la case vide plutôt que d'imprimer un zéro."""
    montant = float(valeur or 0.0)
    return montant if montant else None


def _ligne_cotisation(source: Dict[str, Any]) -> Dict[str, Any]:
    # La colonne est celle du taux salarial : une cotisation purement patronale
    # n'y met rien, comme sur le bulletin du cabinet.
    taux = source.get("taux_salarial")
    return _ligne(
        "detail",
        source.get("libelle") or "",
        base=source.get("base"),
        taux=float(taux) * 100 if taux is not None else None,
        montant_salarial=_montant_ou_vide(source.get("montant_salarial")),
        montant_patronal=_montant_ou_vide(source.get("montant_patronal")),
    )


def _lignes_rubrique(rubrique: Dict[str, Any]) -> List[Dict[str, Any]]:
    code = rubrique.get("code") or ""
    entete = _ligne(
        "rubrique",
        LIBELLES_CEGID.get(code, str(rubrique.get("libelle") or "").upper()),
        code=CODES_CEGID.get(code),
    )
    details = [
        _ligne_cotisation(ligne)
        for ligne in rubrique.get("lignes") or []
        if isinstance(ligne, dict)
    ]
    return [entete, *details]


def _lignes_hors_brut(bulletin: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ce qui s'ajoute ou se retient après le net imposable."""
    lignes: List[Dict[str, Any]] = []

    for prime in bulletin.get("primes_non_soumises") or []:
        if not isinstance(prime, dict):
            continue
        lignes.append(
            _ligne(
                "hors_brut",
                prime.get("libelle") or "Prime non soumise",
                montant_salarial=prime.get("montant"),
            )
        )

    # Volontairement agrégé : le détail des notes de frais reste dans l'appli.
    notes_de_frais = [
        note for note in bulletin.get("notes_de_frais") or [] if isinstance(note, dict)
    ]
    if notes_de_frais:
        total = round(
            sum(float(note.get("montant") or 0.0) for note in notes_de_frais), 2
        )
        lignes.append(
            _ligne(
                "hors_brut",
                "Remboursement de frais professionnels",
                montant_salarial=total,
            )
        )

    synthese = bulletin.get("synthese_net") or {}
    for cle, libelle in (
        ("remboursement_transport", "Indemnité de transport"),
        ("indemnite_transport_fixe", "Indemnité transport contractuelle"),
    ):
        montant = float(synthese.get(cle) or 0.0)
        if montant > 0:
            lignes.append(_ligne("hors_brut", libelle, montant_salarial=montant))

    # L'enrichissement « saisies et avances » n'a pas toujours tourné : dans ce
    # cas l'acompte ne subsiste que dans la synthèse des nets.
    acomptes = float(
        (bulletin.get("remboursements_avances") or {}).get("total_rembourse") or 0.0
    ) or float(synthese.get("acompte_verse") or 0.0)

    retenues = (
        (acomptes, "Acomptes et avances"),
        (
            (bulletin.get("retenues_saisies") or {}).get("total_preleve"),
            "Retenues sur salaire",
        ),
        (
            (bulletin.get("remboursements_prets") or {}).get("total_rembourse"),
            "Remboursement prêt employeur",
        ),
    )
    # Retenues sur le net : négatives, comme les absences dans le brut, pour
    # qu'on ne confonde pas ce qui s'ajoute et ce qui se retire.
    for montant, libelle in retenues:
        valeur = float(montant or 0.0)
        if valeur > 0:
            lignes.append(_ligne("hors_brut", libelle, montant_salarial=-valeur))

    return lignes


def construire_lignes(bulletin: Dict[str, Any]) -> List[Dict[str, Any]]:
    lignes: List[Dict[str, Any]] = []

    for source in (
        "calcul_du_brut",
        "details_conges",
        "details_absences",
        "details_maintien",
    ):
        for detail in bulletin.get(source) or []:
            if isinstance(detail, dict):
                lignes.append(_ligne_brut(detail))

    # Ligne de note libre, comme Cegid en pose dans le corps du bulletin
    # (« SOLDE MODUL.au 21/06=8.25h ») : ici, la règle retenue pour l'indemnité
    # de congés payés.
    if bulletin.get("arbitrage_conges"):
        lignes.append(_ligne("note", str(bulletin["arbitrage_conges"])))

    lignes.append(
        _ligne("total", "SALAIRE BRUT", montant_salarial=bulletin.get("salaire_brut"))
    )

    rubriques = [
        rubrique
        for rubrique in bulletin.get("cotisations_officielles") or []
        if isinstance(rubrique, dict)
    ]
    rubriques_principales = [
        r for r in rubriques if r.get("code") != RUBRIQUE_APRES_NET_IMPOSABLE
    ]
    rubriques_apres = [
        r for r in rubriques if r.get("code") == RUBRIQUE_APRES_NET_IMPOSABLE
    ]

    for rubrique in rubriques_principales:
        lignes.extend(_lignes_rubrique(rubrique))

    total_salarial = round(
        sum(float(r.get("total_salarial") or 0.0) for r in rubriques_principales), 2
    )
    total_patronal = round(
        sum(float(r.get("total_patronal") or 0.0) for r in rubriques_principales), 2
    )
    lignes.append(
        _ligne(
            "total",
            "TOTAL DES RETENUES",
            montant_salarial=total_salarial,
            montant_patronal=total_patronal,
        )
    )
    lignes.append(
        _ligne(
            "total",
            "NET IMPOSABLE",
            montant_salarial=(bulletin.get("synthese_net") or {}).get("net_imposable"),
        )
    )

    lignes.extend(_lignes_hors_brut(bulletin))
    for rubrique in rubriques_apres:
        lignes.extend(_lignes_rubrique(rubrique))

    return lignes


def _montant_fr(valeur: Any) -> str:
    """Format français : espace pour les milliers, virgule décimale."""
    nombre = float(valeur or 0.0)
    return f"{nombre:,.2f}".replace(",", " ").replace(".", ",")


def _bloc_lateral(titre: str, valeurs: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    valeurs_utiles = [valeur for valeur in valeurs if valeur["valeur"]]
    if not valeurs_utiles:
        return None
    return {"titre": titre, "valeurs": valeurs_utiles}


def construire_lateral(bulletin: Dict[str, Any]) -> List[Dict[str, Any]]:
    parametres = bulletin.get("parametres") or {}
    cumuls = ((bulletin.get("cumuls") or {}).get("cumuls")) or {}
    pied = bulletin.get("pied_de_page") or {}
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}

    def valeur(libelle: str, montant: Any) -> Dict[str, str]:
        return {
            "libelle": libelle,
            "valeur": _montant_fr(montant) if montant else "",
        }

    blocs = [
        _bloc_lateral(
            "BARÈMES",
            [
                valeur("SMIC horaire", parametres.get("smic_horaire")),
                valeur("Plafond Sécu", parametres.get("pss_mensuel")),
            ],
        ),
        _bloc_lateral(
            "HEURES",
            [
                valeur("Cumul heures", cumuls.get("heures_remunerees")),
                valeur("Cumul h. sup", cumuls.get("heures_supplementaires_remunerees")),
            ],
        ),
        _bloc_lateral(
            "CUMULS",
            [
                valeur("Bruts", cumuls.get("brut_total")),
                valeur("Net imposable", cumuls.get("net_imposable")),
                valeur("Allègement cotis. employeur", pied.get("total_exonerations")),
                valeur("Total versé employeur", pied.get("cout_total_employeur")),
            ],
        ),
        _bloc_lateral(
            "PAIEMENT",
            [
                {
                    "libelle": "Mode",
                    "valeur": MODES_PAIEMENT.get(
                        str(salarie.get("mode_paiement") or "").strip().lower(), ""
                    ),
                }
            ],
        ),
    ]
    return [bloc for bloc in blocs if bloc]


def calculer_evolution_remuneration(salaire_brut: float, base_csg: float) -> float:
    """Mention obligatoire de l'article R3243-1 du Code du travail."""
    brut = float(salaire_brut or 0.0)
    base = float(base_csg or 0.0) or brut
    montant = brut * TAUX_COTISATIONS_SUPPRIMEES - base * TAUX_HAUSSE_CSG
    return round(max(0.0, montant), 2)


def _base_csg(bulletin: Dict[str, Any]) -> float:
    """Base de la CSG, prise sur la première ligne de la rubrique dédiée."""
    for rubrique in bulletin.get("cotisations_officielles") or []:
        if not isinstance(rubrique, dict):
            continue
        if rubrique.get("code") not in {"csg_deductible", "csg_non_deductible"}:
            continue
        for ligne in rubrique.get("lignes") or []:
            if isinstance(ligne, dict) and ligne.get("base"):
                return float(ligne["base"])
    return 0.0


def construire_pied(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    synthese = bulletin.get("synthese_net") or {}
    pas = synthese.get("impot_prelevement_a_la_source") or {}
    cumuls = ((bulletin.get("cumuls") or {}).get("cumuls")) or {}
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    mentions = ((bulletin.get("pied_de_page") or {}).get("mentions_legales")) or {}

    rectification = ""
    if bulletin.get("manually_edited"):
        edite_le = bulletin.get("edited_at")
        rectification = (
            f"Bulletin rectifié le {edite_le}" if edite_le else "Bulletin rectifié"
        )

    return {
        "montant_net_social": synthese.get("montant_net_social"),
        "net_avant_impot": synthese.get("net_social_avant_impot"),
        "evolution_remuneration": calculer_evolution_remuneration(
            float(bulletin.get("salaire_brut") or 0.0), _base_csg(bulletin)
        ),
        "mention_evolution": MENTION_EVOLUTION_REMUNERATION,
        "impot": {
            "net_imposable": synthese.get("net_imposable"),
            "base": pas.get("base"),
            "taux": pas.get("taux"),
            "montant": pas.get("montant"),
            "cumul_net_imposable": cumuls.get("net_imposable"),
            "cumul_impot": cumuls.get("impot_preleve_a_la_source"),
            "exoneration_apprenti": bool(synthese.get("exoneration_ir_apprenti")),
        },
        "net_a_payer": bulletin.get("net_a_payer"),
        "convention_collective": salarie.get("convention_collective") or "",
        "mentions_legales": [
            texte
            for texte in (mentions.get("conservation"), mentions.get("information"))
            if texte
        ],
        "note": bulletin.get("pdf_notes") or "",
        "rectification": rectification,
    }


def construire_vue_bulletin(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    """Point d'entrée unique : le bulletin du moteur, vu par le gabarit."""
    return {
        "bandeau": construire_bandeau(bulletin),
        "compteurs": construire_compteurs(bulletin),
        "salarie": construire_salarie(bulletin),
        "identite": construire_identite(bulletin),
        "lignes": construire_lignes(bulletin),
        "lateral": construire_lateral(bulletin),
        "pied": construire_pied(bulletin),
    }
