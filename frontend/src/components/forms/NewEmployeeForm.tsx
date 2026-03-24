import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import apiClient from '@/api/apiClient'; // Ajustez le chemin si nécessaire

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Loader2 } from "lucide-react";

// Le schéma de validation reste ici, avec le formulaire
const formSchema = z.object({
  first_name: z.string().min(2, { message: "Le prénom doit contenir au moins 2 caractères." }),
  last_name: z.string().min(2, { message: "Le nom doit contenir au moins 2 caractères." }),
  job_title: z.string().min(2, { message: "Le poste est requis." }),
  contract_type: z.string().min(2, { message: "Le type de contrat est requis." }),
});

// On définit les "props" que ce composant accepte
// Ici, il a besoin d'une fonction à appeler quand le formulaire est soumis avec succès
interface NewEmployeeFormProps {
  onSuccess: () => void;
}

export function NewEmployeeForm({ onSuccess }: NewEmployeeFormProps) {
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { first_name: "", last_name: "", job_title: "", contract_type: "CDI" },
  });

  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    try {
      await apiClient.post('/api/employees', values);
      onSuccess(); // Appelle la fonction onSuccess pour notifier le parent
    } catch (error) {
      console.error("Erreur lors de la création du collaborateur", error);
      alert("Une erreur est survenue.");
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 pt-4">
        <FormField control={form.control} name="first_name" render={({ field }) => (
          <FormItem><FormLabel>Prénom</FormLabel><FormControl><Input placeholder="Jean" {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="last_name" render={({ field }) => (
          <FormItem><FormLabel>Nom</FormLabel><FormControl><Input placeholder="Dupont" {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="job_title" render={({ field }) => (
          <FormItem><FormLabel>Poste</FormLabel><FormControl><Input placeholder="Peintre industriel" {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="contract_type" render={({ field }) => (
          <FormItem><FormLabel>Type de contrat</FormLabel><FormControl><Input placeholder="CDI" {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        
        <div className="flex justify-end pt-4">
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Créer le Collaborateur
          </Button>
        </div>
      </form>
    </Form>
  );
}