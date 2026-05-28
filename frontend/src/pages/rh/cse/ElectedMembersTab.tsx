// frontend/src/pages/cse/ElectedMembersTab.tsx

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getElectedMembers, type ElectedMemberListItem } from "@/api/cse";
import { ROLE_LABELS, ROLE_BADGE_CLASSES } from "@/lib/cseLabels";
import { useCsePage } from "@/contexts/CsePageContext";
import { Plus, Users, Calendar, AlertTriangle, Loader2, Edit, ExternalLink } from "lucide-react";
import { ElectedMemberModal } from "@/components/cse/ElectedMemberModal";
import { cn } from "@/lib/utils";

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
    return Math.ceil((end.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}

export default function ElectedMembersTab() {
  const { highlightElectedMemberId } = useCsePage();
  const [searchTerm, setSearchTerm] = useState("");
  const [activeOnly, setActiveOnly] = useState(true);
  const [expiringOnly, setExpiringOnly] = useState(false);
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<ElectedMemberListItem | null>(null);

  const { data: members = [], isLoading } = useQuery({
    queryKey: ["cse", "elected-members", activeOnly],
    queryFn: () => getElectedMembers(activeOnly),
  });

  const filteredMembers = useMemo(() => {
    return members.filter((member) => {
      const daysRemaining = member.days_remaining ?? getDaysRemaining(member.end_date);
      if (expiringOnly && (daysRemaining === null || daysRemaining > 90)) {
        return false;
      }
      if (!searchTerm) return true;
      const search = searchTerm.toLowerCase();
      return (
        member.first_name.toLowerCase().includes(search) ||
        member.last_name.toLowerCase().includes(search) ||
        (member.job_title?.toLowerCase().includes(search) ?? false) ||
        (member.college?.toLowerCase().includes(search) ?? false)
      );
    });
  }, [members, searchTerm, expiringOnly]);

  useEffect(() => {
    if (!highlightElectedMemberId) return;
    const el = document.getElementById(`elected-row-${highlightElectedMemberId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightElectedMemberId, filteredMembers]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:flex-1">
          <Input
            placeholder="Rechercher un élu…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
          />
          <div className="flex items-center gap-2">
            <Switch id="active-only" checked={activeOnly} onCheckedChange={setActiveOnly} />
            <Label htmlFor="active-only" className="text-sm font-normal cursor-pointer">
              Actifs seulement
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch id="expiring" checked={expiringOnly} onCheckedChange={setExpiringOnly} />
            <Label htmlFor="expiring" className="text-sm font-normal cursor-pointer">
              Expire sous 90 j
            </Label>
          </div>
        </div>
        <Button
          onClick={() => {
            setSelectedMember(null);
            setMemberModalOpen(true);
          }}
          className="shrink-0"
        >
          <Plus className="h-4 w-4 mr-2" />
          Ajouter un élu
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Élus CSE
            <span className="text-sm font-normal text-muted-foreground">
              ({filteredMembers.length})
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : filteredMembers.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">Aucun élu trouvé</div>
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
                  const daysRemaining =
                    member.days_remaining ?? getDaysRemaining(member.end_date);
                  const isExpiringSoon =
                    daysRemaining !== null && daysRemaining <= 90 && daysRemaining >= 0;
                  const isHighlighted = highlightElectedMemberId === member.id;

                  return (
                    <TableRow
                      key={member.id}
                      id={`elected-row-${member.id}`}
                      className={cn(
                        isHighlighted && "bg-orange-50 ring-1 ring-orange-200",
                      )}
                    >
                      <TableCell className="font-medium">
                        <Link
                          to={`/employees/${member.employee_id}`}
                          className="inline-flex items-center gap-1 hover:underline"
                        >
                          {member.first_name} {member.last_name}
                          <ExternalLink className="h-3 w-3 text-muted-foreground" />
                        </Link>
                      </TableCell>
                      <TableCell>{member.job_title || "—"}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={cn("border", ROLE_BADGE_CLASSES[member.role])}
                        >
                          {ROLE_LABELS[member.role]}
                        </Badge>
                      </TableCell>
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
                            <span
                              className={cn(
                                isExpiringSoon && "text-orange-600 font-medium",
                                daysRemaining < 0 && "text-red-600 font-medium",
                              )}
                            >
                              {daysRemaining < 0
                                ? `Expiré (${Math.abs(daysRemaining)} j.)`
                                : `${daysRemaining} jour${daysRemaining > 1 ? "s" : ""}`}
                            </span>
                          </div>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell>
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
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {memberModalOpen && (
        <ElectedMemberModal
          open={memberModalOpen}
          onOpenChange={setMemberModalOpen}
          member={selectedMember ?? undefined}
        />
      )}
    </div>
  );
}
