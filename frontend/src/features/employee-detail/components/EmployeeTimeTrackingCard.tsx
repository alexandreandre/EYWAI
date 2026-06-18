import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Hash } from 'lucide-react';

import { updateEmployee } from '@/api/employees';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { Employee } from '@/features/employee-detail/types';
import { useToast } from '@/hooks/use-toast';

interface EmployeeTimeTrackingCardProps {
  employeeId: string;
  employee: Employee;
  canEdit?: boolean;
  onEmployeeUpdated: (employee: Employee) => void;
}

export function EmployeeTimeTrackingCard({
  employeeId,
  employee,
  canEdit = true,
  onEmployeeUpdated,
}: EmployeeTimeTrackingCardProps) {
  const { toast } = useToast();
  const [matricule, setMatricule] = useState(employee.time_tracking_id ?? '');

  useEffect(() => {
    setMatricule(employee.time_tracking_id ?? '');
  }, [employee.time_tracking_id]);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateEmployee(employeeId, {
        time_tracking_id: matricule.trim() || null,
      }),
    onSuccess: (updated) => {
      onEmployeeUpdated(updated);
      toast({ title: 'Matricule GTA enregistré' });
    },
    onError: () => {
      toast({
        title: 'Erreur',
        description: "Impossible d'enregistrer le matricule.",
        variant: 'destructive',
      });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <Hash className="mr-2 h-5 w-5 text-primary" />
          Matricule GTA / badgeuse
        </CardTitle>
        <CardDescription>
          Utilisé pour l&apos;import automatique des relevés Cegid hebdomadaires.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="time-tracking-id">Matricule</Label>
          <Input
            id="time-tracking-id"
            value={matricule}
            onChange={(e) => setMatricule(e.target.value)}
            disabled={!canEdit || saveMutation.isPending}
            placeholder="ex. 196"
            className="max-w-xs"
          />
        </div>
        {canEdit && (
          <Button
            type="button"
            size="sm"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          >
            Enregistrer
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
