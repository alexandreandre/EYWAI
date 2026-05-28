import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, LayoutGrid, List, BarChart3, UserPlus } from "lucide-react";
import type { RecruitmentPageModel } from "@/features/recruitment/hooks/useRecruitmentPageModel";

type Props = Pick<
  RecruitmentPageModel,
  | "isRh"
  | "canShowPipeline"
  | "mainSection"
  | "setMainSection"
  | "viewMode"
  | "setViewMode"
  | "searchInput"
  | "setSearchInput"
  | "jobs"
  | "jobFilterId"
  | "setJobFilterId"
  | "stages"
  | "stageFilterId"
  | "setStageFilterId"
  | "activeJobs"
  | "setShowCreateCandidate"
>;

export function RecruitmentPageToolbar({
  isRh,
  canShowPipeline,
  mainSection,
  setMainSection,
  viewMode,
  setViewMode,
  searchInput,
  setSearchInput,
  jobs,
  jobFilterId,
  setJobFilterId,
  stages,
  stageFilterId,
  setStageFilterId,
  activeJobs,
  setShowCreateCandidate,
}: Props) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between">
        <div className="flex flex-col sm:flex-row flex-wrap gap-2 items-stretch sm:items-center min-w-0">
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Rechercher un candidat..."
              className="pl-9 h-9"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>

          {mainSection === "pipeline" && jobs.length > 0 ? (
            <Select value={jobFilterId} onValueChange={setJobFilterId}>
              <SelectTrigger className="w-[200px] h-9">
                <SelectValue placeholder="Filtrer par poste" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Tous les postes</SelectItem>
                {jobs.map((j) => (
                  <SelectItem key={j.id} value={j.id} textValue={j.title}>
                    {j.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}

          {mainSection === "pipeline" && stages.length > 0 ? (
            <Select value={stageFilterId} onValueChange={setStageFilterId}>
              <SelectTrigger className="w-[180px] h-9">
                <SelectValue placeholder="Étape" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Toutes les étapes</SelectItem>
                {stages.map((s) => (
                  <SelectItem key={s.id} value={s.id} textValue={s.name}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2 items-center shrink-0">
          {isRh && (
            <div className="flex border rounded-lg h-9 shrink-0">
              <Button
                type="button"
                variant={mainSection === "pipeline" ? "default" : "ghost"}
                size="sm"
                className="rounded-r-none h-9 px-3"
                onClick={() => setMainSection("pipeline")}
              >
                Pipeline
              </Button>
              <Button
                type="button"
                variant={mainSection === "analytics" ? "default" : "ghost"}
                size="sm"
                className="rounded-l-none h-9 px-3 gap-1"
                onClick={() => setMainSection("analytics")}
              >
                <BarChart3 className="h-4 w-4" />
                Analytics
              </Button>
            </div>
          )}

          {mainSection === "pipeline" && (
            <div className="flex border rounded-lg h-9 shrink-0">
              <Button
                variant={viewMode === "kanban" ? "default" : "ghost"}
                size="sm"
                className="rounded-r-none h-9"
                onClick={() => setViewMode("kanban")}
                aria-label="Vue Kanban"
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === "list" ? "default" : "ghost"}
                size="sm"
                className="rounded-l-none h-9"
                onClick={() => setViewMode("list")}
                aria-label="Vue liste"
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
          )}

          {isRh && canShowPipeline && mainSection === "pipeline" && activeJobs.length > 0 && (
            <Button onClick={() => setShowCreateCandidate(true)} size="sm" className="h-9">
              <UserPlus className="h-4 w-4 mr-1" /> Nouveau candidat
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
