"""Fixtures texte Cegid pour tests backtest."""

BUGNY_PAGE1 = """
   COLORPLAST                                                                          BULLETIN DE SALAIRE
   01300 MAGNIEU                                                                         Paiement le : 31/05/26
                 CP N-1          CP N
                                                                                  MR BUGNY Michel
  Solde :         15.00 /       24.96 /
   Matricule : BUGNY                 NoSécu.: 177037305401687
   Emploi :      Logisticien Polyvalent                      Coeff: 720
                  Rubriques                         Base        Taux salarial         Montant salarial
        SALAIRE DE BASE                                151.67           14.2800                     2165.85
        Heures supplémentaires 25                       15.00           17.8500                      267.75
   BPA Prime exceptionnelle                            150.00                                        150.00
   BANC Prime ancienneté                              1980.15            3.0000                       59.40
        SALAIRE BRUT                                                                                2952.34
        Participation 2025                            3936.59                                       3936.59
        NET IMPOSABLE                                                                               5600.16
  MONTANT NET SOCIAL
  NET A PAYER AVANT IMPOT SUR LE REVENU
"""

BUGNY_PAGE2 = """
   Matricule : BUGNY                   NoSécu.: 177037305401687
   SINT Acompte sur participation 2025                   -1000.00                                         -1000.00
   SNDF Rbst note de frais                                 569.59                                           569.59
  MONTANT NET SOCIAL                                                                                                                   5479.53
  NET A PAYER AVANT IMPOT SUR LE REVENU                                                                                                5479.53
Montant net imposable                                                                                      5600.16
Impôt sur le revenu prélevé à la source                 5600.16                  3.40                       190.41
                                                                                                                         Net à payer au salarié (En Euros)
                                                                                                                                                 5289.12
            Versé employeur
                                                                                                                                                    7207.57
"""
