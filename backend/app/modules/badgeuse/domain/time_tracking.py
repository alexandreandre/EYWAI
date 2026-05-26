from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from enum import StrEnum
from typing import List, Tuple, Dict, Iterable


class TimeEntryType(StrEnum):
    ENTREE = "ENTREE"
    SORTIE = "SORTIE"


class TimeEntrySource(StrEnum):
    EMPLOYE = "EMPLOYE"
    RH = "RH"
    QR_SCAN = "QR_SCAN"


@dataclass(frozen=True)
class TimeEntry:
    employee_id: str
    company_id: str
    timestamp: datetime
    event_type: TimeEntryType
    source: TimeEntrySource
    id: str | None = None


@dataclass(frozen=True)
class TimeSequence:
    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        return max(self.end - self.start, timedelta(0))


@dataclass(frozen=True)
class DayAnomaly:
    date: date
    message: str


@dataclass(frozen=True)
class DaySummary:
    date: date
    total_duration: timedelta
    sequences: List[TimeSequence]
    anomalies: List[DayAnomaly]

    @property
    def status(self) -> str:
        if not self.sequences and not self.anomalies:
            return "Absent"
        if self.anomalies:
            return "Anomalie"
        return "Complet"


def _sort_entries(entries: Iterable[TimeEntry]) -> List[TimeEntry]:
    return sorted(entries, key=lambda e: e.timestamp)


def build_sequences_and_anomalies(
    entries: Iterable[TimeEntry],
) -> Tuple[List[TimeSequence], List[DayAnomaly]]:
    """
    Construit les séquences ENTREE→SORTIE et détecte les anomalies pour un jour donné.
    Règles :
    - ENTREE sans SORTIE correspondante → anomalie
    - SORTIE sans ENTREE préalable → anomalie
    - Deux ENTREE consécutives ou deux SORTIE consécutives → anomalie
    - SORTIE avec horodatage antérieur à l'ENTREE correspondante → anomalie
    """
    sorted_entries = _sort_entries(entries)
    sequences: List[TimeSequence] = []
    anomalies: List[DayAnomaly] = []

    open_entry: TimeEntry | None = None
    current_date: date | None = None

    for entry in sorted_entries:
        current_date = entry.timestamp.date()
        if entry.event_type == TimeEntryType.ENTREE:
            if open_entry is not None:
                anomalies.append(
                    DayAnomaly(
                        date=current_date,
                        message="Deux entrées consécutives sans sortie intermédiaire",
                    )
                )
                # On considère la paire d'entrées comme une anomalie isolée
                # et on ne laisse pas d'entrée "ouverte" supplémentaire
                open_entry = None
            else:
                open_entry = entry
        else:  # SORTIE
            if open_entry is None:
                anomalies.append(
                    DayAnomaly(
                        date=entry.timestamp.date(),
                        message="Sortie sans entrée préalable",
                    )
                )
                continue
            if entry.timestamp <= open_entry.timestamp:
                anomalies.append(
                    DayAnomaly(
                        date=entry.timestamp.date(),
                        message="Sortie antérieure ou égale à l'entrée correspondante",
                    )
                )
            else:
                sequences.append(
                    TimeSequence(start=open_entry.timestamp, end=entry.timestamp)
                )
            open_entry = None

    if open_entry is not None:
        anomalies.append(
            DayAnomaly(
                date=open_entry.timestamp.date(),
                message="Entrée sans sortie correspondante",
            )
        )

    return sequences, anomalies


def compute_day_summary(entries: Iterable[TimeEntry]) -> DaySummary:
    """Calcule le résumé d'une journée pour un employé."""
    entries_list = list(entries)
    if not entries_list:
        today = date.today()
        return DaySummary(
            date=today,
            total_duration=timedelta(0),
            sequences=[],
            anomalies=[],
        )

    day = entries_list[0].timestamp.date()
    sequences, anomalies = build_sequences_and_anomalies(entries_list)
    total_duration = sum((seq.duration for seq in sequences), timedelta(0))
    return DaySummary(
        date=day,
        total_duration=total_duration,
        sequences=sequences,
        anomalies=anomalies,
    )


def group_entries_by_day(entries: Iterable[TimeEntry]) -> Dict[date, List[TimeEntry]]:
    by_day: Dict[date, List[TimeEntry]] = {}
    for entry in entries:
        d = entry.timestamp.date()
        by_day.setdefault(d, []).append(entry)
    for d in by_day:
        by_day[d] = _sort_entries(by_day[d])
    return by_day


def compute_period_summaries(entries: Iterable[TimeEntry]) -> Dict[date, DaySummary]:
    grouped = group_entries_by_day(entries)
    return {d: compute_day_summary(day_entries) for d, day_entries in grouped.items()}
