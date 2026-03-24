// frontend/src/pages/cse/ElectedMembersTab.tsx
// Onglet Élus & Mandats

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import {
  getElectedMembers,
  type ElectedMemberListItem,
} from "@/api/cse";
import { Plus, Users, Calendar, AlertTriangle, Loader2, Edit } from "lucide-react";
import { ElectedMemberModal } from "@/components/cse/ElectedMemberModal";

function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

function getDaysRemaining(endDate: string): number | null {
  try {
    const end = new Date(endDate);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    end.setHours(0, 0, 0, 0);
    const diff = Math.ceil((end.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    return diff;
  } catch {
    return null;
  }
}

export default function ElectedMembersTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<ElectedMemberListItem | null>(null);

  const { data: members = [], isLoading } = useQuery({
    queryKey: ["cse", "elected-members"],
    queryFn: () => getElectedMembers(true),
  });


  const filteredMembers = members.filter((member) => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        member.first_name.toLowerCase().includes(search) ||
        member.last_name.toLowerCase().includes(search) ||
        member.job_title?.toLowerCase().includes(search) ||
        ""
      );
    }
    return true;
  });

  const getRoleBadge = (role: string) => {
    const colors: Record<string, string> = {
      titulaire: "bg-blue-100 text-blue-800",
      suppleant: "bg-green-100 text-green-800",
      secretaire: "bg-purple-100 text-purple-800",
      tresorier: "bg-orange-100 text-orange-800",
      autre: "bg-gray-100 text-gray-800",
    };
    return (
      <Badge className={colors[role] || colors.autre}>
        {role.charAt(0).toUpperCase() + role.slice(1)}
      </Badge>
    );
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 flex-1">
          <Input
            placeholder="Rechercher un élu..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
          />
        </div>
        <Button onClick={() => {
          setSelectedMember(null);
          setMemberModalOpen(true);
        }}>
          <Plus className="h-4 w-4 mr-2" />
          Ajouter un élu
        </Button>
      </div>

      {/* Liste des élus */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Élus CSE
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : filteredMembers.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Aucun élu trouvé
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nom</TableHead>
                  <TableHead>Poste</TableHead>
                  <TableHead>Rôle CSE</TableHead>
                  <TableHead>Collège</TableHead>
                  <TableHead>Début</TableHead>
                  <TableHead>Fin</TableHead>
                  <TableHead>Jours restants</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredMembers.map((member) => {
                  const daysRemaining = member.days_remaining ?? getDaysRemaining(member.end_date);
                  const isExpiringSoon = daysRemaining !== null && daysRemaining <= 90;
                  
                  return (
                    <TableRow key={member.id}>
                      <TableCell className="font-medium">
                        {member.first_name} {member.last_name}
                      </TableCell>
                      <TableCell>{member.job_title || "—"}</TableCell>
                      <TableCell>{getRoleBadge(member.role)}</TableCell>
                      <TableCell>{member.college || "—"}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                          <span>{formatDate(member.start_date)}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                          <span>{formatDate(member.end_date)}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {daysRemaining !== null ? (
                          <div className="flex items-center gap-2">
                            {isExpiringSoon && (
                              <AlertTriangle className="h-4 w-4 text-orange-500" />
                            )}
                            <span className={isExpiringSoon ? "text-orange-600 font-medium" : ""}>
                              {daysRemaining} jour{daysRemaining > 1 ? "s" : ""}
                            </span>
                          </div>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedMember(member);
                              setMemberModalOpen(true);
                            }}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Modal création/édition élu */}
      {memberModalOpen && (
        <ElectedMemberModal
          open={memberModalOpen}
          onOpenChange={setMemberModalOpen}
          member={selectedMember || undefined}
        />
      )}
    </div>
  );
}
