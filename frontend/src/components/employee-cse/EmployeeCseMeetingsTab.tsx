import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { MeetingListItem, MeetingStatus } from '@/api/cse';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  MEETING_STATUS_BADGE_CLASSES,
  MEETING_STATUS_LABELS,
  MEETING_TYPE_LABELS,
  RECORDING_STATUS_LABELS,
} from '@/lib/cseLabels';
import {
  formatCseDate,
  formatCseTime,
  pickNextMeeting,
  sortMeetingsByUrgency,
} from '@/lib/employeeCseUtils';
import { cn } from '@/lib/utils';
import { Calendar, FileText, Loader2, MapPin, Users } from 'lucide-react';

const STATUS_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: 'all', label: 'Toutes' },
  { value: 'a_venir', label: MEETING_STATUS_LABELS.a_venir },
  { value: 'en_cours', label: MEETING_STATUS_LABELS.en_cours },
  { value: 'terminee', label: MEETING_STATUS_LABELS.terminee },
];

interface EmployeeCseMeetingsTabProps {
  meetings: MeetingListItem[];
  isLoading: boolean;
  isError?: boolean;
}

export function EmployeeCseMeetingsTab({
  meetings,
  isLoading,
  isError,
}: EmployeeCseMeetingsTabProps) {
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const sortedMeetings = useMemo(() => sortMeetingsByUrgency(meetings), [meetings]);

  const filteredMeetings = useMemo(() => {
    if (statusFilter === 'all') return sortedMeetings;
    return sortedMeetings.filter((m) => m.status === statusFilter);
  }, [sortedMeetings, statusFilter]);

  const nextMeeting = useMemo(() => pickNextMeeting(meetings), [meetings]);

  if (isError) {
    return (
      <Card className="border-destructive/50">
        <CardContent className="pt-6 text-sm text-destructive">
          Impossible de charger vos réunions. Réessayez plus tard.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {nextMeeting && statusFilter === 'all' && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Prochaine réunion</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="font-semibold">{nextMeeting.title}</p>
              <p className="text-sm text-muted-foreground">
                <Calendar className="mr-1 inline h-4 w-4" />
                {formatCseDate(nextMeeting.meeting_date)}
                {nextMeeting.meeting_time
                  ? ` à ${formatCseTime(nextMeeting.meeting_time)}`
                  : ''}
                {nextMeeting.location ? (
                  <>
                    {' '}
                    · <MapPin className="mr-0.5 inline h-3.5 w-3.5" />
                    {nextMeeting.location}
                  </>
                ) : null}
              </p>
            </div>
            <Button size="sm" asChild>
              <Link to={`/cse/meetings/${nextMeeting.id}`}>Voir le détail</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Statut" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_FILTER_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mes réunions CSE</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : filteredMeetings.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">
              Aucune réunion à afficher pour ce filtre.
            </p>
          ) : (
            <div className="space-y-3">
              {filteredMeetings.map((meeting) => (
                <MeetingRow key={meeting.id} meeting={meeting} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function MeetingRow({ meeting }: { meeting: MeetingListItem }) {
  const statusClass =
    MEETING_STATUS_BADGE_CLASSES[meeting.status as MeetingStatus] ?? '';

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-l-4 border-l-blue-500 p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 flex-1 space-y-2">
        <h3 className="font-semibold">{meeting.title}</h3>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Calendar className="h-4 w-4 shrink-0" />
            {formatCseDate(meeting.meeting_date)}
            {meeting.meeting_time ? ` à ${formatCseTime(meeting.meeting_time)}` : ''}
          </span>
          {meeting.location ? (
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5 shrink-0" />
              {meeting.location}
            </span>
          ) : null}
          {meeting.participant_count != null && meeting.participant_count > 0 ? (
            <span className="inline-flex items-center gap-1">
              <Users className="h-3.5 w-3.5 shrink-0" />
              {meeting.participant_count} participant
              {meeting.participant_count > 1 ? 's' : ''}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{MEETING_TYPE_LABELS[meeting.meeting_type]}</Badge>
          <Badge variant="outline" className={cn(statusClass)}>
            {MEETING_STATUS_LABELS[meeting.status]}
          </Badge>
          {meeting.has_minutes ? (
            <Badge variant="secondary" className="gap-1">
              <FileText className="h-3 w-3" />
              PV disponible
            </Badge>
          ) : null}
          {meeting.recording_status &&
          meeting.recording_status !== 'not_started' ? (
            <Badge variant="outline" className="text-xs">
              {RECORDING_STATUS_LABELS[meeting.recording_status] ??
                meeting.recording_status}
            </Badge>
          ) : null}
        </div>
      </div>
      <Button variant="outline" size="sm" className="shrink-0" asChild>
        <Link to={`/cse/meetings/${meeting.id}`}>Voir le détail</Link>
      </Button>
    </div>
  );
}
