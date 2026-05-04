import apiClient from '@/api/apiClient';

export type Notification = {
  id: string;
  employee_id: string | null;
  company_id: string;
  type: string;
  message: string;
  is_read: boolean;
  created_at: string;
};

export type UnreadCount = {
  count: number;
};

export async function getNotifications(companyId: string): Promise<Notification[]> {
  const res = await apiClient.get<Notification[]>('/api/notifications', {
    headers: { 'X-Active-Company': companyId },
  });
  return res.data ?? [];
}

export async function getUnreadCount(companyId: string): Promise<UnreadCount> {
  const res = await apiClient.get<UnreadCount>('/api/notifications/unread-count', {
    headers: { 'X-Active-Company': companyId },
  });
  return res.data;
}

export async function markAsRead(notificationId: string, companyId: string): Promise<void> {
  await apiClient.put(
    `/api/notifications/${notificationId}/read`,
    {},
    { headers: { 'X-Active-Company': companyId } },
  );
}

export async function markAllAsRead(companyId: string): Promise<void> {
  await apiClient.put('/api/notifications/read-all', {}, { headers: { 'X-Active-Company': companyId } });
}
