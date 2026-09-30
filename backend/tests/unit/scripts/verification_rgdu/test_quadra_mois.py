"""Les éléments du mois utiles à la réduction, lus sur un bulletin Quadra."""
import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.verification_rgdu.quadra_mois import elements_du_mois

pytestmark = pytest.mark.unit


def _b(lignes, cumul_h, cumul_b, **infos):
    b = Bulletin(matricule="ESSAI")
    b.lignes, b.droite, b.infos = lignes, {"cumul_heures": cumul_h, "cumul_bruts": cumul_b}, {"nir": "1999999999999", **infos}
    return b


def test_un_mois_d_arret_avec_maintien():
    fev = _b([Ligne(None, "SALAIRE BRUT", gain=2400.0)], 169.0, 2400.0)
    mars = _b([
        Ligne(None, "SALAIRE DE BASE", base=151.67, gain=1900.0),
        Ligne(None, "Absence maladie 160326-280326", base=70.0, montant_sal=877.0),
        Ligne(None, "Maintien de salaire", gain=310.78),
        Ligne(None, "SALAIRE BRUT", gain=1609.96),
        Ligne(None, "EXO., ECRET. ET ALLEG. COTIS", base=-419.16, montant_pat=-419.16),
    ], 259.0, 4009.96)
    [m] = elements_du_mois({"ESSAI": mars}, {"ESSAI": fev}, "colorplast", 3)
    assert (m.brut_mois, m.heures_mois, m.reduction_mois, m.maintien) == (1609.96, 90.0, 419.16, 310.78)
    assert [(a.nature, a.heures) for a in m.absences] == [("maladie", 70.0)]


def test_forfait_jours_et_absence_non_payee():
    b = _b([
        Ligne(None, "Forfait 216 jours"),
        Ligne(None, "Abs. Abs aut nonpayé 130126", base=2.24, montant_sal=30.0),
        Ligne(None, "SALAIRE BRUT", gain=3750.0),
    ], 0.0, 3750.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "comitech", 1)
    assert m.forfait_jours == 216
    assert [(a.nature, a.heures) for a in m.absences] == [("non_payee", 2.24)]


def test_heures_base_et_heures_sup_sur_un_mois_plein():
    """Salarié A, un mois complet (libellés réels, valeurs réelles de janvier) :
    SALAIRE DE BASE donne la base horaire (151,67 h à temps plein), deux lignes
    d'heures sup payées (25 % et 50 %) s'additionnent ; la ligne patronale EWZB
    (réduction forfaitaire, sans montant côté salarié) n'y entre pas."""
    b = _b([
        Ligne(None, "SALAIRE DE BASE", base=151.67, gain=2123.38),
        Ligne(None, "Heures supplémentaires 25", base=12.00, gain=210.00),
        Ligne(None, "Heures supplémentaires 50", base=8.50, gain=178.50),
        Ligne(None, "EWZB REDUCT HEURES SUPPL. P.P.<= 20", base=37.83, montant_pat=-56.75),
        Ligne(None, "SALAIRE BRUT", gain=3023.40),
    ], 169.0, 3023.40)
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 1)
    assert m.heures_base == 151.67
    assert m.heures_sup == 20.5


def test_heures_sup_inclut_une_petite_ligne_classee_en_retenue():
    """Vu sur les vrais bulletins (ex. Colorplast janvier, salarié A) : une petite ligne
    d'heures sup payées (0,80 h à 17,50 €, base × taux = 14,00 €) atterrit dans la
    colonne retenue (montant_sal) plutôt que gain — un artefact de colonnes de
    colorplast_lignes_quadra pour les montants étroits (jamais une vraie déduction :
    toujours positif, toujours égal à base × taux sur les 705 lignes relues). Elle doit
    compter dans heures_sup comme les autres."""
    b = _b([
        Ligne(None, "H. supp majorées à 25 %", base=0.80, taux=17.50, montant_sal=14.00),
        Ligne(None, "SALAIRE BRUT", gain=2000.0),
    ], 151.67, 2000.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 1)
    assert m.heures_sup == 0.80


def test_heures_comp_ijss_preavis_par_defaut_sans_libelle_reel():
    """Aucun libellé Quadra réel trouvé pour ces trois éléments sur les 21 bulletins-mois
    relus (Colorplast et Comitech janvier à août, Mont-Blanc janvier à juillet 2026) :
    les champs restent à leur valeur par défaut tant qu'un exemple réel ne les confirme
    pas (voir le rapport de tâche, section doutes)."""
    b = _b([Ligne(None, "SALAIRE BRUT", gain=2000.0)], 151.67, 2000.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 1)
    assert (m.heures_comp, m.ijss, m.indemnite_preavis) == (0.0, 0.0, None)


def test_accident_du_travail_est_classe_maladie():
    """Libellé réel (Comitech, Mont-Blanc) : « Absence A.T. » = accident du travail,
    abrégé — même famille que l'arrêt maladie pour la réduction (R-H4)."""
    b = _b([
        Ligne(None, "Absence A.T. 050526-140526", base=56.0, taux=12.648, montant_sal=708.29),
        Ligne(None, "SALAIRE BRUT", gain=1200.0),
    ], 93.0, 1200.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "comitech", 5)
    assert [(a.nature, a.heures) for a in m.absences] == [("maladie", 56.0)]


def test_absences_tronquees_sur_une_plage_de_dates():
    """Sur une plage de dates (deux dates séparées par un tiret), Quadra tronque le
    libellé avant le dernier mot : « nonpayé » → « non », « injustifiée » → « injusti »,
    « s.solde » → « s.so ». Trois libellés réels, un par nature."""
    b = _b([
        Ligne(None, "Abs. Abs aut non 010726-020726", base=8.0, montant_sal=100.0),
        Ligne(None, "Abs. Abs injusti 010426-030426", base=16.0, montant_sal=200.0),
        Ligne(None, "Abs. Congés s.so 010626-050626", base=32.0, montant_sal=400.0),
        Ligne(None, "SALAIRE BRUT", gain=1200.0),
    ], 93.0, 1200.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 6)
    assert [(a.nature, a.heures) for a in m.absences] == [
        ("non_payee", 8.0), ("injustifiee", 16.0), ("sans_solde", 32.0),
    ]


def test_enfant_malade_est_classe_non_payee():
    """Libellé réel (Mont-Blanc) : « Abs. Enfant malade » (Art. L1225-61) — jamais
    maintenu sur les bulletins relus, donc une absence non payée au sens de R-H3,
    pas un arrêt maladie du salarié lui-même (R-H4, qui a son propre régime
    IJSS/subrogation)."""
    b = _b([
        Ligne(None, "Abs. Enfant malade 210126", base=1.0, taux=162.9091, montant_sal=162.91),
        Ligne(None, "SALAIRE BRUT", gain=1200.0),
    ], 150.0, 1200.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "mbc", 1)
    assert [(a.nature, a.heures) for a in m.absences] == [("non_payee", 1.0)]


def test_conges_payes_au_forfait_jours():
    """Libellé réel (Comitech, Mont-Blanc) : « Jours Absence Congés Payés » — même
    rubrique que « H.Absence Congés Payés » vue à l'étape 1, en jours pour un salarié
    au forfait."""
    b = _b([
        Ligne(None, "Forfait 216 jours"),
        Ligne(None, "Jours Absence Congés Payés", base=1.0, taux=147.0455, montant_sal=147.05),
        Ligne(None, "SALAIRE BRUT", gain=3750.0),
    ], 0.0, 3750.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "comitech", 1)
    assert [(a.nature, a.heures) for a in m.absences] == [("conges_payes", 1.0)]


def test_entree_n_est_retenue_que_le_mois_de_l_evenement():
    """L'en-tête du bulletin répète la date d'entrée sur tous les mois de présence
    (vérifié sur un salarié réel entré en avril, présent jusqu'en août) : sans filtre
    sur le mois en cours, `entree` serait renseigné chaque mois, pas seulement celui
    de l'entrée."""
    avril = _b([Ligne(None, "SALAIRE BRUT", gain=1000.0)], 100.0, 1000.0, entree="07/04/2026")
    mai = _b([Ligne(None, "SALAIRE BRUT", gain=2000.0)], 250.0, 3000.0, entree="07/04/2026")
    [m_avril] = elements_du_mois({"ESSAI": avril}, None, "colorplast", 4)
    [m_mai] = elements_du_mois({"ESSAI": mai}, {"ESSAI": avril}, "colorplast", 5)
    assert m_avril.entree == "07/04/2026"
    assert m_mai.entree is None


def test_absence_pour_entree_ou_sortie_reste_autre():
    """Libellé réel : la ligne que Quadra imprime pour la retenue du mois d'entrée ou de
    sortie. Elle touche la réduction (base et montant réels) mais ne correspond à aucune
    des natures de l'énoncé : ni une absence R-H3/R-H4/R-H5, ni les congés payés — c'est
    le mécanisme R-H7 (entrée/sortie en cours de mois) lui-même, qui a sa propre formule.
    Laissée « autre » plutôt que devinée ; voir le rapport de tâche."""
    b = _b([
        Ligne(None, "Absence pour entrée ou sortie", base=30.5, taux=12.2, montant_sal=372.1),
        Ligne(None, "SALAIRE BRUT", gain=1000.0),
    ], 40.0, 1000.0, entree="20/04/2026")
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 4)
    assert [(a.nature, a.heures, a.montant) for a in m.absences] == [("autre", 30.5, 372.1)]
