"""Les éléments du mois utiles à la réduction, lus sur un bulletin Quadra."""
import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.verification_rgdu import quadra_mois
from scripts.verification_rgdu.quadra_mois import elements_du_mois, lire_societe

pytestmark = pytest.mark.unit


def _b(lignes, cumul_h, cumul_b, heures_periode=None, **infos):
    b = Bulletin(matricule="ESSAI")
    droite = {"cumul_heures": cumul_h, "cumul_bruts": cumul_b}
    if heures_periode is not None:
        droite["heures_periode"] = heures_periode
    b.lignes, b.droite, b.infos = lignes, droite, {"nir": "1999999999999", **infos}
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
    fev = _b([Ligne(None, "SALAIRE BRUT", gain=3000.0)], 169.0, 3000.0)
    fev.droite["cumul_hs"] = 10.0
    b = _b([
        Ligne(None, "SALAIRE DE BASE", base=151.67, gain=2123.38),
        Ligne(None, "Heures supplémentaires 25", base=12.00, gain=210.00),
        Ligne(None, "Heures supplémentaires 50", base=8.50, gain=178.50),
        Ligne(None, "EWZB REDUCT HEURES SUPPL. P.P.<= 20", base=37.83, montant_pat=-56.75),
        Ligne(None, "SALAIRE BRUT", gain=3023.40),
    ], 169.0, 3023.40)
    b.droite["cumul_hs"] = 30.5
    [m] = elements_du_mois({"ESSAI": b}, {"ESSAI": fev}, "colorplast", 1)
    assert m.heures_base == 151.67
    assert (m.heures_sup_payees, m.heures_sup_retirees_absence, m.heures_sup_retirees_conges) == (20.5, 0.0, 0.0)
    assert m.heures_sup == 20.5
    assert m.heures_sup_quadra == 20.5


def test_une_ligne_d_heures_sup_en_retenue_est_une_vraie_deduction():
    """Corrigé après revue : une ligne d'heures sup en retenue (`montant_sal`, sans
    `gain`) est une vraie déduction — des heures sup RETIRÉES pour absence — et non
    un artefact de colonnes comme cru à tort à la première écriture de ce module.
    Vu réellement (Colorplast mars, salarié A) : 17,33 h payées, puis 8,10 h retirées
    pour une absence maladie."""
    b = _b([
        Ligne(None, "H. supp majorées à 25 %", base=17.33, taux=16.1865, gain=280.51),
        Ligne(None, "Absence maladie 160326-280326", base=70.0, montant_sal=906.44),
        Ligne(None, "H. supp majorées à 25 %", base=8.10, taux=16.1865, montant_sal=131.11),
        Ligne(None, "SALAIRE BRUT", gain=1500.0),
    ], 169.0, 1500.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 3)
    assert (m.heures_sup_payees, m.heures_sup_retirees_absence, m.heures_sup_retirees_conges) == (17.33, 8.10, 0.0)
    assert m.heures_sup == 9.23


def test_une_retenue_d_heures_sup_apres_un_conge_paye_reste_payee():
    """R-H2 : les congés payés sont payés, pas de baisse. Vu réellement (Colorplast
    janvier, salarié A) : une ligne d'heures sup en retenue (0,80 h) qui suit
    immédiatement une ligne « H.Absence Congés Payés » reste couverte par
    l'indemnité de congé — elle ne réduit pas heures_sup, elle est comptée à part."""
    b = _b([
        Ligne(None, "H.Absence Congés Payés", base=7.0, montant_sal=98.0),
        Ligne(None, "H. supp majorées à 25 %", base=0.80, taux=17.50, montant_sal=14.00),
        Ligne(None, "SALAIRE DE BASE", base=151.67, gain=2123.38),
        Ligne(None, "H. supp majorées à 25 %", base=17.33, taux=17.50, gain=303.28),
        Ligne(None, "SALAIRE BRUT", gain=2500.0),
    ], 169.0, 2500.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 1)
    assert (m.heures_sup_payees, m.heures_sup_retirees_absence, m.heures_sup_retirees_conges) == (17.33, 0.0, 0.80)
    assert m.heures_sup == 17.33


def test_heures_sup_quadra_est_none_sans_mois_precedent_ou_sans_cumul_hs():
    """None dès que l'un des deux bulletins manque le cumul, plutôt qu'une avance
    fausse (0 supposé au départ) — corrigé après revue (voir aussi heures_mois)."""
    b = _b([Ligne(None, "SALAIRE BRUT", gain=1000.0)], 100.0, 1000.0)
    b.droite["cumul_hs"] = 12.0
    [sans_prec] = elements_du_mois({"ESSAI": b}, None, "colorplast", 2)
    assert sans_prec.heures_sup_quadra is None

    prec_sans_cumul_hs = _b([Ligne(None, "SALAIRE BRUT", gain=900.0)], 90.0, 900.0)  # pas de cumul_hs
    [avec_prec_incomplet] = elements_du_mois({"ESSAI": b}, {"ESSAI": prec_sans_cumul_hs}, "colorplast", 2)
    assert avec_prec_incomplet.heures_sup_quadra is None


def test_heures_mois_utilise_heures_periode_meme_sans_mois_precedent():
    """Corrigé après revue : la différence de cumul est fausse quand le bulletin
    précédent manque (nouvel embauché en cours d'année) — elle repart alors de
    zéro et compte tout l'historique comme le mois en cours. Vu réellement
    (Mont-Blanc, salarié A, avril) : heures_mois valait 250 au lieu de 87,5.
    « Heures période », imprimée par Quadra pour le mois, n'a pas ce défaut."""
    b = _b([Ligne(None, "SALAIRE BRUT", gain=1000.0)], 250.0, 1000.0, heures_periode=87.5)
    [m] = elements_du_mois({"ESSAI": b}, None, "mbc", 4)
    assert m.heures_mois == 87.5


def test_heures_mois_replie_sur_le_delta_de_cumul_si_heures_periode_absente():
    fev = _b([Ligne(None, "SALAIRE BRUT", gain=2400.0)], 169.0, 2400.0)
    mars = _b([Ligne(None, "SALAIRE BRUT", gain=1600.0)], 259.0, 1600.0)  # pas de heures_periode
    [m] = elements_du_mois({"ESSAI": mars}, {"ESSAI": fev}, "colorplast", 3)
    assert m.heures_mois == 90.0


def test_heures_comp_ijss_preavis_par_defaut_sans_libelle_reel():
    """Aucun libellé Quadra réel trouvé pour ces trois éléments sur les 21 bulletins-mois
    relus (Colorplast et Comitech janvier à août, Mont-Blanc janvier à juillet 2026) :
    les champs restent à leur valeur par défaut tant qu'un exemple réel ne les confirme
    pas (voir le rapport de tâche, section doutes)."""
    b = _b([Ligne(None, "SALAIRE BRUT", gain=2000.0)], 151.67, 2000.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 1)
    assert (m.heures_comp, m.ijss, m.indemnite_preavis) == (0.0, 0.0, None)


def test_ijss_ne_compte_que_le_gain_jamais_une_retenue():
    """Corrigé après revue : `gain or montant_sal` compterait deux fois une IJSS
    reprise puis reversée (retenue). Hypothèse, sans libellé réel (voir le rapport
    de tâche, section doutes) : seul le gain doit compter."""
    b = _b([
        Ligne(None, "IJSS", gain=200.0),
        Ligne(None, "IJSS reversement", montant_sal=200.0),
        Ligne(None, "SALAIRE BRUT", gain=1000.0),
    ], 151.67, 1000.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 1)
    assert m.ijss == 200.0


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


def test_enfant_malade_est_une_nature_a_part_qui_peut_etre_maintenue():
    """Corrigé après revue : « Abs. Enfant malade » (Art. L1225-61) n'est PAS
    « jamais maintenue » — vu réellement (Mont-Blanc, trois cas) avec un maintien à
    80 %, une ligne « Maintien de salaire » suivie d'une ligne d'information
    « = 80% enfant malade » (sans heures ni montant, donc pas une absence en soi).
    Nature à part (`enfant_malade`), plus fondue dans `non_payee`."""
    b = _b([
        Ligne(None, "H.Absence Congés Payés", base=3.5, montant_sal=44.13),
        Ligne(None, "SALAIRE DE BASE", base=75.78, gain=955.41),
        Ligne(None, "Abs. Enfant malade 080126", base=3.5, montant_sal=44.13),
        Ligne(None, "Maintien de salaire", gain=123.56),
        Ligne(None, "le 08-01 = 80% enfant malade"),
        Ligne(None, "SALAIRE BRUT", gain=1017.45),
    ], 150.0, 1017.45)
    [m] = elements_du_mois({"ESSAI": b}, None, "mbc", 1)
    assert m.maintien == 123.56
    assert [(a.nature, a.libelle, a.heures, a.montant) for a in m.absences] == [
        ("conges_payes", "H.Absence Congés Payés", 3.5, 44.13),
        ("enfant_malade", "Abs. Enfant malade 080126", 3.5, 44.13),
    ]


def test_une_ligne_d_information_sans_heures_ni_montant_n_est_pas_une_absence():
    """Corrigé après revue : une ligne d'information pure (aucune base, aucun
    montant) ne doit jamais entrer dans `absences`, quelle que soit sa nature
    apparente — vu réellement (Mont-Blanc) : « jour enfant malade 02/02 »."""
    b = _b([
        Ligne(None, "jour enfant malade 02/02"),
        Ligne(None, "SALAIRE BRUT", gain=1000.0),
    ], 150.0, 1000.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "mbc", 2)
    assert m.absences == []


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
    Laissée « autre » plutôt que devinée ; voir le rapport de tâche. Vue aussi sans date
    d'entrée ni de sortie dans le mois (reprise après une longue absence) : la ligne
    touche quand même la réduction, `entree`/`sortie` ne suffisent pas à la repérer."""
    b = _b([
        Ligne(None, "Absence pour entrée ou sortie", base=30.5, taux=12.2, montant_sal=372.1),
        Ligne(None, "SALAIRE BRUT", gain=1000.0),
    ], 40.0, 1000.0, entree="20/04/2026")
    [m] = elements_du_mois({"ESSAI": b}, None, "colorplast", 4)
    assert [(a.nature, a.heures, a.montant) for a in m.absences] == [("autre", 30.5, 372.1)]


def test_bulletin_fusionne_leve_une_erreur():
    """Garde contre la troncature de matricule vue réellement chez Mont-Blanc
    (`MATRICULE` dans colorplast_lignes_quadra.py tronque des matricules suffixés,
    ex. « MIR2 »/« MIR3 », fusionnant plusieurs salariés) : plus d'une ligne
    SALAIRE BRUT trahit un bulletin qui mélange plusieurs personnes."""
    b = _b([
        Ligne(None, "SALAIRE BRUT", gain=1000.0),
        Ligne(None, "SALAIRE BRUT", gain=1500.0),
    ], 150.0, 2500.0)
    with pytest.raises(ValueError, match="fusionnés"):
        elements_du_mois({"ESSAI": b}, None, "mbc", 1)


def test_lire_societe_garde_deux_matricules_pour_un_meme_nir_le_meme_mois(monkeypatch):
    """Corrigé après revue : indexer par le seul NIR écraserait en silence un salarié
    qui change de matricule sans changer de NIR dans le même mois. Vu réellement
    (Comitech, août) : un CDD sorti le 30 et un contrat d'apprentissage entré le 31,
    même NIR, deux matricules, deux bulletins — les deux doivent survivre."""
    meme_nir = "1888888888888"
    fin_cdd = _b([Ligne(None, "SALAIRE BRUT", gain=1000.0)], 100.0, 1000.0, nir=meme_nir)
    debut_apprenti = _b([Ligne(None, "SALAIRE BRUT", gain=50.0)], 5.0, 50.0, nir=meme_nir)
    bulletins_du_mois = {"CDD": fin_cdd, "APPRENTI": debut_apprenti}

    monkeypatch.setitem(quadra_mois.SOCIETES, "essai", {"dossier": "essai", "mois": (8,)})
    monkeypatch.setattr(quadra_mois, "lire_bulletins", lambda annee, mois, dossier: bulletins_du_mois)

    index = lire_societe("essai")
    assert set(index) == {(f"{meme_nir}/APPRENTI", 8), (f"{meme_nir}/CDD", 8)}
