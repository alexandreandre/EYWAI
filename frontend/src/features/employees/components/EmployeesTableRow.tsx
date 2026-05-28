import { ChevronRight, UserMinus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { TableCell, TableRow } from "@/components/ui/table";

export interface EmployeeListItem {
  id: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
  contract_type: string | null;
  hire_date: string | null;
  employment_status?: string | null;
  current_exit_id?: string | null;
}

export function getContractBadge(type: string) {
  const variants = { CDI: "bg-blue-100 text-blue-800", CDD: "bg-purple-100 text-purple-800" };
  return <Badge variant="default" className={variants[type as keyof typeof variants] || "bg-gray-100 text-gray-800"}>{type}</Badge>;
}

export function EmployeesTableRow({ employee }: { employee: EmployeeListItem }) {
  const navigate = useNavigate();

  return (
    <TableRow
      key={employee.id}
      onClick={() => navigate(`/employees/${employee.id}`)}
      className="cursor-pointer hover:bg-muted/50"
    >
      <TableCell>
        <div className="flex items-center gap-3">
          <Avatar className="h-8 w-8">
            <AvatarFallback>
              {employee.first_name.charAt(0)}
              {employee.last_name.charAt(0)}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <p className="font-medium">
                {employee.first_name} {employee.last_name}
              </p>
              {employee.employment_status === "en_sortie" && (
                <Badge variant="outline" className="text-xs flex items-center gap-1">
                  <UserMinus className="h-3 w-3" />
                  En départ
                </Badge>
              )}
              {employee.employment_status === "parti" && (
                <Badge variant="secondary" className="text-xs">
                  Parti
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Entrée:{" "}
              {employee.hire_date
                ? new Date(employee.hire_date).toLocaleDateString("fr-FR")
                : "N/A"}
            </p>
          </div>
        </div>
      </TableCell>
      <TableCell>{employee.job_title || "N/A"}</TableCell>
      <TableCell>
        {employee.contract_type ? getContractBadge(employee.contract_type!) : "N/A"}
      </TableCell>
      <TableCell className="text-right">
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
      </TableCell>
    </TableRow>
  );
}
