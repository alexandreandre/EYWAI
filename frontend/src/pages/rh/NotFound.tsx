import { log } from '@/lib/logger';
import { Button } from '@/components/ui/button';
import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';

const NotFound = () => {
  const location = useLocation();
  const isPlatformAdminArea = location.pathname.startsWith('/super-admin');
  const homeTo = isPlatformAdminArea ? '/super-admin' : '/';

  useEffect(() => {
    log.error('404 — route inexistante :', location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="text-center">
        <h1 className="mb-4 text-4xl font-bold">404</h1>
        <p className="mb-4 text-xl text-muted-foreground">Page introuvable</p>
        <p className="mb-6 text-sm text-muted-foreground">
          L&apos;adresse demandée n&apos;existe pas ou a été déplacée.
        </p>
        <Button variant="outline" asChild>
          <Link to={homeTo}>Retour à l&apos;accueil</Link>
        </Button>
      </div>
    </div>
  );
};

export default NotFound;
