-- Notifications salarié (ex. avenant signé)

CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
  company_id UUID NOT NULL,
  type TEXT NOT NULL,
  message TEXT NOT NULL,
  is_read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_employee
  ON notifications(employee_id);
CREATE INDEX IF NOT EXISTS idx_notifications_company
  ON notifications(company_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read
  ON notifications(is_read);
