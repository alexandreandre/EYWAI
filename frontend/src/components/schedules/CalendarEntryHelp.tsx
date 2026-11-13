/** Aide commune à la fiche salarié et au tiroir de la page Calendrier. */
export function CalendarEntryHelp() {
  return (
    <details className="mx-2 mb-3 rounded-md border bg-muted/20 px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium">Quel type choisir pour un jour à 0 h ?</summary>
      <div className="mt-2 space-y-2 text-xs text-muted-foreground">
        <p>
          <strong>Récupération déjà validée et suivie hors Martine :</strong> choisissez
          {' '}« Repos / récupération externe », mettez le prévu à 0 h et gardez le réel à 0 h.
          Martine ne crée ni retenue d’absence, ni congé payé, ni débit de compteur pour ce repos.
          Déduisez les heures du compteur externe et déclarez les heures restant à payer
          dans l’onglet « Corriger » du bulletin (« Ajouter une ligne » → « Des heures »).
          Notez la durée de récupération autorisée dans ce suivi avant de mettre le prévu à zéro.
        </p>
        <p>
          <strong>Compensation faite à l’extérieur :</strong> vérifiez que l’option
          {' '}« Compensation des heures entre semaines » est désactivée dans Mon Entreprise → Paie
          pour éviter de compenser deux fois.
          Vérifiez aussi le routage vers le compte d’heures, le choix individuel du mois
          et les mouvements CET déjà validés.
        </p>
        <p>
          <strong>Temps partiel :</strong> les heures au-delà du contrat sont des heures
          complémentaires. N’utilisez pas la déclaration d’heures supplémentaires à 25 % / 50 %
          pour les remplacer. Leur déclaration se fait dans l’onglet « Corriger » du bulletin :
          {' '}« Ajouter une ligne » → « Des heures » → « Ce mois-ci », aux paliers affichés.
        </p>
        <p>
          <strong>Autre absence :</strong> choisissez son motif réel (congés payés, RTT,
          arrêt ou absence non rémunérée). Un zéro importé ne donne pas le motif :
          faites-le confirmer avant de choisir. Une récupération demandée sur un compteur
          Martine passe par le module Absences.
        </p>
        <p>
          <strong>Travail prévu avec réel à 0 h :</strong> le calendrier reste à vérifier.
          Ne recopiez pas le prévu dans le réel pour masquer cette alerte.
        </p>
      </div>
    </details>
  );
}
