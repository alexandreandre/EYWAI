import { Navigate, useLocation } from 'react-router-dom';

/** Redirection vers le hub Calendrier et planning (vue semaine). */
export default function EmployeePlanning() {
  const { search } = useLocation();
  const hasView = search.includes('view=');
  const target = hasView ? `/calendar${search}` : '/calendar?view=week';
  return <Navigate to={target} replace />;
}
