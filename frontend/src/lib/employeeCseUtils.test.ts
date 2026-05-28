import { describe, expect, it } from 'vitest';
import type { MeetingListItem } from '@/api/cse';
import {
  isEmployeeCseTab,
  pickNextMeeting,
  sortMeetingsByUrgency,
} from './employeeCseUtils';

const baseMeeting = (overrides: Partial<MeetingListItem>): MeetingListItem => ({
  id: '1',
  title: 'Réunion',
  meeting_date: '2026-05-15',
  meeting_time: null,
  meeting_type: 'ordinaire',
  status: 'a_venir',
  participant_count: 3,
  created_at: '2026-01-01',
  ...overrides,
});

describe('employeeCseUtils', () => {
  it('isEmployeeCseTab accepts valid tabs', () => {
    expect(isEmployeeCseTab('meetings')).toBe(true);
    expect(isEmployeeCseTab('documents')).toBe(true);
    expect(isEmployeeCseTab('tasks')).toBe(false);
    expect(isEmployeeCseTab(null)).toBe(false);
  });

  it('sortMeetingsByUrgency puts upcoming before finished', () => {
    const meetings = [
      baseMeeting({ id: 'a', status: 'terminee', meeting_date: '2026-04-01' }),
      baseMeeting({ id: 'b', status: 'a_venir', meeting_date: '2026-06-01' }),
      baseMeeting({ id: 'c', status: 'a_venir', meeting_date: '2026-05-01' }),
    ];
    const sorted = sortMeetingsByUrgency(meetings);
    expect(sorted.map((m) => m.id)).toEqual(['c', 'b', 'a']);
  });

  it('pickNextMeeting returns earliest upcoming', () => {
    const meetings = [
      baseMeeting({ id: 'a', status: 'a_venir', meeting_date: '2026-06-01' }),
      baseMeeting({ id: 'b', status: 'a_venir', meeting_date: '2026-05-01' }),
      baseMeeting({ id: 'c', status: 'terminee', meeting_date: '2026-04-01' }),
    ];
    expect(pickNextMeeting(meetings)?.id).toBe('b');
  });
});
