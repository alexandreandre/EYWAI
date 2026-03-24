// frontend/src/pages/super-admin/SuperAdminLayout.tsx
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useState } from 'react';

export default function SuperAdminLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const navigation = [
    { name: 'Dashboard', href: '/super-admin', icon: '📊' },
    { name: 'Entreprises', href: '/super-admin/companies', icon: '🏢' },
    { name: 'Groupes', href: '/super-admin/groups', icon: '🏛️' },
    { name: 'Utilisateurs', href: '/super-admin/users', icon: '👥' },
    { name: 'Conventions Collectives', href: '/super-admin/collective-agreements', icon: '📋' },
    { name: 'Réduction Fillon', href: '/super-admin/reduction-fillon', icon: '💰' },
    { name: 'Scraping', href: '/super-admin/scraping', icon: '🌐' },
    { name: 'Monitoring', href: '/super-admin/monitoring', icon: '🔍' },
    { name: 'Tests', href: '/super-admin/tests', icon: '🧪' },
    // { name: 'Super Admins', href: '/super-admin/admins', icon: '👑' },
  ];

  const isActive = (path: string) => {
    if (path === '/super-admin') {
      return location.pathname === path;
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-gradient-to-b from-indigo-900 to-purple-900 text-white transform transition-transform duration-200 ease-in-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between h-16 px-6 bg-black bg-opacity-20">
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold">Super Admin</h1>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden text-white hover:text-gray-200"
          >
            ✕
          </button>
        </div>

        {/* Navigation */}
        <nav className="mt-6 px-3">
          {navigation.map((item) => (
            <Link
              key={item.name}
              to={item.href}
              className={`flex items-center space-x-3 px-4 py-3 mb-2 rounded-lg transition-all ${
                isActive(item.href)
                  ? 'bg-white bg-opacity-20 text-white font-semibold shadow-lg'
                  : 'text-gray-200 hover:bg-white hover:bg-opacity-10'
              }`}
            >
              <span className="text-2xl">{item.icon}</span>
              <span>{item.name}</span>
            </Link>
          ))}
        </nav>

        {/* Footer */}
        <div className="absolute bottom-0 w-full p-4 border-t border-white border-opacity-20">
          <button
            onClick={() => navigate('/')}
            className="flex items-center space-x-2 w-full px-4 py-2 text-sm text-gray-200 hover:text-white hover:bg-white hover:bg-opacity-10 rounded-lg transition-all"
          >
            <span>←</span>
            <span>Retour à l'appli</span>
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className={`transition-all duration-200 ${sidebarOpen ? 'lg:ml-64' : 'ml-0'}`}>
        {/* Top bar */}
        <div className="sticky top-0 z-40 h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div className="flex items-center space-x-4">
            <div className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm font-semibold">
              Super Admin Mode
            </div>
          </div>
        </div>

        {/* Page content */}
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
