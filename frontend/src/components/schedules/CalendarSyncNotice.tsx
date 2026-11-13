import { Button } from '@/components/ui/button';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';

export function CalendarSyncNotice({ loadError, saveError, isDirty, onReload }: {
  loadError?: boolean;
  saveError?: string | null;
  isDirty: boolean;
  onReload: () => void;
}) {
  if (!loadError && !saveError) return null;
  return <div role="alert" className="mb-3 space-y-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
    <p>{saveError ?? 'Le calendrier n’a pas pu être chargé pour la saisie. Réessayez dans un instant.'}</p>
    {isDirty ? <AlertDialog>
      <AlertDialogTrigger asChild><Button variant="outline" size="sm">Recharger le calendrier</Button></AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Recharger le calendrier ?</AlertDialogTitle>
          <AlertDialogDescription>Les saisies encore affichées seront remplacées par les données enregistrées. Conservez les modifications à reprendre avant de recharger.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Conserver mes saisies</AlertDialogCancel>
          <AlertDialogAction onClick={onReload}>Recharger et remplacer mes saisies</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog> : <Button variant="outline" size="sm" onClick={onReload}>Réessayer le chargement</Button>}
  </div>;
}
