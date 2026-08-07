"""Constantes rubriques DSN (NEODeS / GIP-MDS)."""

from __future__ import annotations

# --- Envoi S10 ---
R_S10_NORME = "S10.G00.00.006"
R_S10_PERIODE = "S10.G00.00.005"
R_S10_TYPE = "S10.G00.00.007"

# --- Déclaration S20.G00.05 (norme courante) ---
R_S20_DECL_NATURE = "S20.G00.05.001"
R_S20_DECL_TYPE = "S20.G00.05.002"
R_S20_DECL_MOIS = "S20.G00.05.005"
# Legacy (exports simplifiés)
R_S20_SIRET_LEGACY = "S20.G00.05.001"
R_S20_RAISON_LEGACY = "S20.G00.05.002"
R_S20_NAF_LEGACY = "S20.G00.05.003"
R_S20_RUE_LEGACY = "S20.G00.05.004"
R_S20_CP_LEGACY = "S20.G00.05.005"
R_S20_VILLE_LEGACY = "S20.G00.05.006"
R_S20_SIRET = R_S20_SIRET_LEGACY
R_S20_RAISON = R_S20_RAISON_LEGACY
R_S20_NAF = R_S20_NAF_LEGACY
R_S20_RUE = R_S20_RUE_LEGACY
R_S20_CP = R_S20_CP_LEGACY
R_S20_VILLE = R_S20_VILLE_LEGACY

# --- Entreprise S21.G00.06 (norme courante P22+) ---
R_S21_ENT_SIREN = "S21.G00.06.001"
R_S21_ENT_NIC_SIEGE = "S21.G00.06.002"
R_S21_ENT_NAF = "S21.G00.06.003"
R_S21_ENT_RUE = "S21.G00.06.004"
R_S21_ENT_CP = "S21.G00.06.005"
R_S21_ENT_VILLE = "S21.G00.06.006"
R_S21_ENT_RAISON = "S21.G00.06.002"

# --- Établissement S21.G00.11 ---
# Norme courante : .001 = NIC (5), .002 = NAF, .003+ = adresse
# Legacy (certains exports) : .001 = SIRET complet (14)
R_S21_ETAB_NIC = "S21.G00.11.001"
R_S21_ETAB_NAF = "S21.G00.11.002"
R_S21_ETAB_RUE = "S21.G00.11.003"
R_S21_ETAB_CP = "S21.G00.11.004"
R_S21_ETAB_VILLE = "S21.G00.11.005"
R_S21_ETAB_EFFECTIF = "S21.G00.11.015"
# Alias legacy
R_S21_ETAB_SIRET = R_S21_ETAB_NIC
R_S21_ETAB_RAISON = "S21.G00.11.002"
R_S21_ETAB_NAF_LEGACY = "S21.G00.11.003"
R_S21_ETAB_RUE_LEGACY = "S21.G00.11.004"
R_S21_ETAB_CP_LEGACY = "S21.G00.11.005"
R_S21_ETAB_VILLE_LEGACY = "S21.G00.11.006"

# --- Individu S21.G00.30 (norme courante P22+) ---
R_S21_IND_NIR = "S21.G00.30.001"
R_S21_IND_NOM = "S21.G00.30.002"
R_S21_IND_NOM_USAGE = "S21.G00.30.003"
R_S21_IND_PRENOM = "S21.G00.30.004"
R_S21_IND_SEXE = "S21.G00.30.005"
R_S21_IND_NAISSANCE = "S21.G00.30.006"
R_S21_IND_LIEU_NAISS = "S21.G00.30.007"
R_S21_IND_RUE = "S21.G00.30.008"
R_S21_IND_CP = "S21.G00.30.009"
R_S21_IND_VILLE = "S21.G00.30.010"
R_S21_IND_MATRICULE = "S21.G00.30.019"
R_S21_IND_NTT = "S21.G00.30.020"
# Alias legacy (exports simplifiés)
R_S21_IND_NOM_LEGACY = "S21.G00.30.001"
R_S21_IND_PRENOM_LEGACY = "S21.G00.30.002"
R_S21_IND_NIR_LEGACY = "S21.G00.30.003"
R_S21_IND_NAISSANCE_LEGACY = "S21.G00.30.004"
R_S21_IND_LIEU_NAISS_LEGACY = "S21.G00.30.005"
R_S21_IND_NATIONALITE_LEGACY = "S21.G00.30.006"

# --- Contrat S21.G00.40 ---
R_S21_CTR_NATURE = "S21.G00.40.007"
R_S21_CTR_STATUT = "S21.G00.40.002"
R_S21_CTR_PCS = "S21.G00.40.004"
R_S21_CTR_DATE_DEBUT = "S21.G00.40.001"
# S21.G00.40.010 « Date de fin prévisionnelle du contrat ». Pointait sur .003,
# qui est le « Code statut catégoriel Retraite Complémentaire obligatoire » : un
# code, jamais une date. À l'import, tout CDD perdait donc sa date de fin ; à
# l'export, EYWAI écrivait cette date dans le champ du statut retraite.
R_S21_CTR_DATE_FIN = "S21.G00.40.010"
R_S21_CTR_DISPOSITIF = "S21.G00.40.008"
R_S21_CTR_NUMERO = "S21.G00.40.009"
# Norme courante : .011 = unité de mesure de la quotité, .012 = quotité de référence
# entreprise, .013 = quotité du contrat, .014 = modalité d'exercice du temps de travail
R_S21_CTR_UNITE_QUOTITE = "S21.G00.40.011"
R_S21_CTR_QUOTITE_REF = "S21.G00.40.012"
R_S21_CTR_QUOTITE = "S21.G00.40.013"
R_S21_CTR_MODALITE_TEMPS = "S21.G00.40.014"
R_S21_CTR_IDCC = "S21.G00.40.017"
R_S21_CTR_POSITION = "S21.G00.40.018"
R_S21_CTR_LIBELLE_EMPLOI = "S21.G00.40.006"

# --- Versement S21.G00.50 ---
R_S21_VER_DATE = "S21.G00.50.001"
R_S21_VER_NET_FISCAL = "S21.G00.50.002"
# Legacy (P21-) : .003 = montant PAS ; norme courante : .003 = n° versement, .009 = montant PAS
R_S21_VER_NUMERO = "S21.G00.50.003"
R_S21_VER_NET_VERSE = "S21.G00.50.004"
R_S21_VER_PAS_LEGACY = R_S21_VER_NUMERO
R_S21_VER_PAS_TAUX = "S21.G00.50.006"
R_S21_VER_PAS_TYPE = "S21.G00.50.007"
R_S21_VER_PAS_ID = "S21.G00.50.008"
R_S21_VER_PAS = "S21.G00.50.009"
R_S21_VER_PAS_ASSIETTE = "S21.G00.50.013"

# --- Activité S21.G00.53 ---
R_S21_ACT_TYPE = "S21.G00.53.001"
R_S21_ACT_MESURE = "S21.G00.53.002"
R_S21_ACT_UNITE = "S21.G00.53.003"

# --- Rémunération S21.G00.51 ---
# Legacy (P21-) : .001 = type, .011 = heures, .013 = montant
R_S21_REM_TYPE_LEGACY = "S21.G00.51.001"
R_S21_REM_HEURES_LEGACY = "S21.G00.51.011"
# Norme courante (P22+) : .001/.002 = dates période, .011 = type, .012 = heures, .013 = montant
R_S21_REM_PERIODE_DEB = "S21.G00.51.001"
R_S21_REM_PERIODE_FIN = "S21.G00.51.002"
R_S21_REM_TYPE = "S21.G00.51.011"
R_S21_REM_HEURES = "S21.G00.51.012"
R_S21_REM_MONTANT = "S21.G00.51.013"
# Alias legacy (compat)
R_S21_REM_TYPE_OLD = R_S21_REM_TYPE_LEGACY

# --- Cotisation S21.G00.78 (legacy) / Base assujettie (P22+) ---
R_S21_COT_CODE = "S21.G00.78.001"
R_S21_COT_BASE = "S21.G00.78.002"
R_S21_COT_TAUX_SAL = "S21.G00.78.003"
R_S21_COT_TAUX_PAT = "S21.G00.78.004"
R_S21_COT_MONTANT_SAL = "S21.G00.78.005"
R_S21_COT_MONTANT_PAT = "S21.G00.78.006"
# P22+ bases assujetties
R_S21_BA_CODE = R_S21_COT_CODE
R_S21_BA_DATE_DEB = R_S21_COT_BASE
R_S21_BA_DATE_FIN = R_S21_COT_TAUX_SAL
R_S21_BA_MONTANT = R_S21_COT_TAUX_PAT

# --- Composant base S21.G00.79 ---
R_S21_CB_CODE = "S21.G00.79.001"
R_S21_CB_MONTANT = "S21.G00.79.004"

# --- Cotisation agrégée S21.G00.86 ---
R_S21_CA_CODE = "S21.G00.86.001"
R_S21_CA_BASE = "S21.G00.86.002"
R_S21_CA_TAUX = "S21.G00.86.003"
R_S21_CA_MONTANT = "S21.G00.86.005"

# --- Composant cotisation établissement S21.G00.23 ---
R_S21_CCET_CODE = "S21.G00.23.001"
R_S21_CCET_REGIME = "S21.G00.23.002"
R_S21_CCET_TAUX = "S21.G00.23.003"
R_S21_CCET_ASSIETTE = "S21.G00.23.004"
R_S21_CCET_MONTANT = "S21.G00.23.005"

# --- Versement organisme S21.G00.20 ---
R_S21_VO_IDENT = "S21.G00.20.001"
R_S21_VO_LIBELLE = "S21.G00.20.002"
R_S21_VO_BIC = "S21.G00.20.003"
R_S21_VO_IBAN = "S21.G00.20.004"
R_S21_VO_MONTANT = "S21.G00.20.005"
R_S21_VO_DATE_DEB = "S21.G00.20.006"
R_S21_VO_DATE_FIN = "S21.G00.20.007"
R_S21_VO_MODE = "S21.G00.20.010"

# --- Bordereau S21.G00.22 ---
R_S21_BORD_IDENT = "S21.G00.22.001"
R_S21_BORD_DATE_DEB = "S21.G00.22.003"
R_S21_BORD_DATE_FIN = "S21.G00.22.004"
R_S21_BORD_MONTANT = "S21.G00.22.005"

# --- Compteur annuel S21.G00.44 ---
R_S21_CPT_CODE = "S21.G00.44.001"
R_S21_CPT_MONTANT = "S21.G00.44.002"
R_S21_CPT_ANNEE = "S21.G00.44.003"

# --- Arrêt travail S21.G00.41 ---
R_S21_ARRET_DEB = "S21.G00.41.001"
R_S21_ARRET_MOTIF = "S21.G00.41.003"
R_S21_ARRET_FIN = "S21.G00.41.004"
R_S21_ARRET_CAISSE = "S21.G00.41.012"

# --- Suspension S21.G00.60 ---
R_S21_SUSP_TYPE = "S21.G00.60.001"
R_S21_SUSP_DEB = "S21.G00.60.002"
R_S21_SUSP_FIN = "S21.G00.60.003"
R_S21_SUSP_MOTIF = "S21.G00.60.004"

# --- Fin contrat S21.G00.62 ---
R_S21_FIN_DATE = "S21.G00.62.001"
R_S21_FIN_MOTIF = "S21.G00.62.002"
R_S21_FIN_NOTIF = "S21.G00.62.006"

# --- Ancienneté S21.G00.65 ---
R_S21_ANC_TYPE = "S21.G00.65.001"
R_S21_ANC_DEB = "S21.G00.65.002"
R_S21_ANC_FIN = "S21.G00.65.003"

# --- Prime S21.G00.52 / avantage S21.G00.54 ---
R_S21_PRIME_CODE = "S21.G00.52.001"
R_S21_PRIME_MONTANT = "S21.G00.52.002"
R_S21_AVANT_CODE = "S21.G00.54.001"
R_S21_AVANT_MONTANT = "S21.G00.54.002"
R_S21_AVANT_DEB = "S21.G00.54.003"
R_S21_AVANT_FIN = "S21.G00.54.004"

# --- Contrat champs complémentaires ---
R_S21_CTR_CLASSIF = "S21.G00.40.040"
R_S21_CTR_NIVEAU = "S21.G00.40.041"
R_S21_CTR_TAUX_AT = "S21.G00.40.043"
R_S21_CTR_STATUT_BOETH = "S21.G00.40.072"
R_S21_CHG_ANCIEN_BOETH = "S21.G00.41.048"

# --- Cotisation individuelle S21.G00.81 ---
R_S21_BASE_CODE = "S21.G00.81.001"
# Legacy : .002 = montant ; norme P22+ : .002 = identifiant OPS, .003 = assiette, .004 = cotisation
R_S21_BASE_MONTANT = "S21.G00.81.002"
R_S21_CI_OPS_IDENT = "S21.G00.81.002"
R_S21_CI_ASSIETTE = "S21.G00.81.003"
R_S21_CI_MONTANT = "S21.G00.81.004"
# Alias historiques (tests / imports existants)
R_S21_CI_MONTANT_SAL = R_S21_CI_ASSIETTE
R_S21_CI_MONTANT_PAT = R_S21_CI_MONTANT
R_S21_CI_IDENT_AFF = "S21.G00.81.005"
R_S21_CI_TAUX = "S21.G00.81.007"

# --- Organisme PSC S21.G00.15 (établissement) ---
R_S21_ORG_REF = "S21.G00.15.001"
R_S21_ORG_CODE = "S21.G00.15.002"
R_S21_ORG_NATURE = "S21.G00.15.004"
R_S21_ORG_RANG = "S21.G00.15.005"

# --- Affiliation PSC S21.G00.70 ---
R_S21_AFF_REF_CONTRAT = "S21.G00.70.001"
R_S21_AFF_CODE_ORG = "S21.G00.70.002"
R_S21_AFF_CODE_DELEG = "S21.G00.70.003"
R_S21_AFF_CODE_OPTION = "S21.G00.70.004"
R_S21_AFF_CODE_POP = "S21.G00.70.005"
R_S21_AFF_NB_ENFANTS = "S21.G00.70.007"
R_S21_AFF_NB_ADULTES = "S21.G00.70.008"
R_S21_AFF_IDENT = "S21.G00.70.012"

PSC_COTISATION_CODE = "059"

# Blocs G00 (3e segment) déclenchant une nouvelle instance
BLOCK_G00 = {
    "06": "entreprise",
    "11": "etablissement",
    "15": "organisme_psc",
    "20": "versement_organisme",
    "22": "bordereau",
    "23": "composant_cotisation_etab",
    "30": "individu",
    "40": "contrat",
    "41": "arret_travail",
    "44": "compteur_annuel",
    "50": "versement",
    "51": "remuneration",
    "52": "prime",
    "54": "avantage",
    "60": "suspension",
    "62": "fin_contrat",
    "65": "anciennete",
    "70": "affiliation",
    "78": "base_assujettie",
    "79": "composant_base",
    "81": "cotisation_individuelle",
    "86": "cotisation_agregee",
    "53": "activite",
}

# Codes nature contrat DSN -> libellé EYWAI
CONTRACT_NATURE_MAP = {
    "01": "CDI",
    "02": "CDD",
    "03": "CDD",
    "04": "CDD",
    "29": "apprentissage",
    "32": "professionnalisation",
    "50": "stage",
    "70": "CDI",
    "80": "CDD",
    "81": "CDD",
    "82": "CDD",
    "89": "CDD",
}

STATUT_CADRE_CODES = {"03", "04", "06", "07", "08", "09"}
# Types obligatoires DSN : vues différentes du même salaire — ne pas les additionner
REMUNERATION_BRUT_PRIMARY = ("001", "010", "002", "003")
REMUNERATION_BRUT_TYPES = set(REMUNERATION_BRUT_PRIMARY)
# Types de rémunération dont .012 = nombre d'heures
REMUNERATION_HEURES_TYPES = {
    "001", "010", "012", "013", "016", "017", "018", "019", "020", "025",
}
# Unités d'activité comptées en heures (S21.G00.53.003)
ACTIVITE_UNITE_HEURES = {"10", "21"}
# Journées / forfait jour — converties en heures pour la synthèse (7 h/j)
ACTIVITE_UNITE_JOURS = {"12", "20"}
ACTIVITE_HEURES_PAR_JOUR = 7.0
# Bases assujetties DSN utilisées comme repli brut (assiette brute)
BASE_ASSUJETTIE_BRUT_CODES = {"02", "03", "04", "11"}
REDUCTION_GENERALE_COT_CODES = {
    "114", "115", "116", "117", "118", "119",
    "214", "215", "216", "217", "218", "219",
}
