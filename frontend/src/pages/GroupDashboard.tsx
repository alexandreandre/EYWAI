/**
 * GroupDashboard : Vue consolidée ultra-moderne pour les groupes d'entreprises
 *
 * Affiche les statistiques consolidées avec graphiques, filtres et export.
 */

import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '@/api/apiClient';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import {
  Users, Building2, TrendingUp, DollarSign, Loader2, ArrowLeft,
  Download, BarChart3, PieChart as PieChartIcon, Filter,
  ArrowUpDown, UserCheck, Percent, Calculator,
  Calendar, CheckCircle2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Area, AreaChart
} from 'recharts';

interface CompanyStats {
  company_id: string;
  company_name: string;
  siret?: string;
  total_employee_count: number;
  employee_count: number; // hors RH
  rh_count: number;
  payslip_count: number;
  gross_salary: number;
  net_salary: number;
  employer_charges: number;
}

interface ConsolidatedStats {
  metadata: {
    reference_year: number;
    reference_month: number;
    generated_at: string;
    company_count: number;
  };
  totals: {
    total_employees: number;
    total_employees_excluding_rh: number;
    total_rh: number;
    total_payslip_count: number;
    total_gross_salary: number;
    total_net_salary: number;
    total_employer_charges: number;
    average_gross_per_company: number;
    average_employees_per_company: number;
  };
  by_company: CompanyStats[];
}

interface EvolutionDataPoint {
  company_id: string;
  company_name: string;
  year: number;
  month: number;
  total_gross: number;
  total_net: number;
  total_employer_charges: number;
  employee_count: number;
}

type SortKey = keyof CompanyStats;
type SortOrder = 'asc' | 'desc';
type PeriodMode = 'month' | 'year' | 'range';

const COLORS = ['#3b82f6', '#10b981', '#6b7280', '#60a5fa', '#34d399', '#9ca3af', '#2563eb', '#059669'];

export function GroupDashboard() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const [stats, setStats] = useState<ConsolidatedStats | null>(null);
  const [evolutionData, setEvolutionData] = useState<EvolutionDataPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtres et tri
  const [searchTerm, setSearchTerm] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('company_name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  // Sélection de période
  const [periodMode, setPeriodMode] = useState<PeriodMode>('month');
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [startYear, setStartYear] = useState<number>(new Date().getFullYear() - 1);
  const [endYear, setEndYear] = useState<number>(new Date().getFullYear());

  // Sélection d'entreprises
  const [availableCompanies, setAvailableCompanies] = useState<CompanyStats[]>([]);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!groupId) {
      setError('ID de groupe manquant');
      setIsLoading(false);
      return;
    }

    loadStats();
  }, [groupId, periodMode, selectedMonth, selectedYear, startYear, endYear]);

  const loadStats = async () => {
    try {
      setIsLoading(true);
      setError(null);

      if (periodMode === 'month') {
        // Charger stats mensuelles
        const response = await apiClient.get(
          `/api/company-groups/${groupId}/consolidated-stats?year=${selectedYear}&month=${selectedMonth}`
        );
        setStats(response.data);

        // Charger évolution (12 derniers mois)
        const evolutionResponse = await apiClient.get(
          `/api/company-groups/${groupId}/payroll-evolution?start_year=${selectedYear - 1}&start_month=${selectedMonth}&end_year=${selectedYear}&end_month=${selectedMonth}`
        );
        setEvolutionData(evolutionResponse.data || []);

        // Initialiser les entreprises disponibles
        if (response.data?.by_company && selectedCompanyIds.size === 0) {
          const allIds = new Set(response.data.by_company.map((c: CompanyStats) => c.company_id));
          setSelectedCompanyIds(allIds);
          setAvailableCompanies(response.data.by_company);
        }
      } else if (periodMode === 'year') {
        // Agréger les données sur l'année entière
        const promises = [];
        for (let month = 1; month <= 12; month++) {
          promises.push(
            apiClient.get(`/api/company-groups/${groupId}/consolidated-stats?year=${selectedYear}&month=${month}`)
          );
        }
        const responses = await Promise.all(promises);

        // Agréger les résultats
        const aggregated = aggregateYearlyData(responses.map(r => r.data));
        setStats(aggregated);

        // Charger évolution annuelle
        const evolutionResponse = await apiClient.get(
          `/api/company-groups/${groupId}/payroll-evolution?start_year=${selectedYear}&start_month=1&end_year=${selectedYear}&end_month=12`
        );
        setEvolutionData(evolutionResponse.data || []);
      } else {
        // Range mode : agréger sur plusieurs années
        const promises = [];
        for (let year = startYear; year <= endYear; year++) {
          for (let month = 1; month <= 12; month++) {
            promises.push(
              apiClient.get(`/api/company-groups/${groupId}/consolidated-stats?year=${year}&month=${month}`)
            );
          }
        }
        const responses = await Promise.all(promises);
        const aggregated = aggregateYearlyData(responses.map(r => r.data));
        setStats(aggregated);

        // Charger évolution
        const evolutionResponse = await apiClient.get(
          `/api/company-groups/${groupId}/payroll-evolution?start_year=${startYear}&start_month=1&end_year=${endYear}&end_month=12`
        );
        setEvolutionData(evolutionResponse.data || []);
      }
    } catch (err: any) {
      console.error('Erreur lors du chargement des statistiques:', err);
      setError(err.response?.data?.detail || 'Erreur lors du chargement des statistiques');
    } finally {
      setIsLoading(false);
    }
  };

  const aggregateYearlyData = (monthlyData: ConsolidatedStats[]): ConsolidatedStats => {
    // Filtrer les données invalides
    const validData = monthlyData.filter(d => d && d.by_company);

    if (validData.length === 0) {
      return {
        metadata: {
          reference_year: selectedYear,
          reference_month: 0,
          generated_at: new Date().toISOString(),
          company_count: 0
        },
        totals: {
          total_employees: 0,
          total_employees_excluding_rh: 0,
          total_rh: 0,
          total_payslip_count: 0,
          total_gross_salary: 0,
          total_net_salary: 0,
          total_employer_charges: 0,
          average_gross_per_company: 0,
          average_employees_per_company: 0
        },
        by_company: []
      };
    }

    // Agréger par entreprise
    const companyMap = new Map<string, CompanyStats>();

    validData.forEach(monthData => {
      monthData.by_company.forEach(company => {
        const existing = companyMap.get(company.company_id);
        if (existing) {
          existing.payslip_count += company.payslip_count;
          existing.gross_salary += company.gross_salary;
          existing.net_salary += company.net_salary;
          existing.employer_charges += company.employer_charges;
          // Garder le max des effectifs
          existing.total_employee_count = Math.max(existing.total_employee_count, company.total_employee_count);
          existing.employee_count = Math.max(existing.employee_count, company.employee_count);
          existing.rh_count = Math.max(existing.rh_count, company.rh_count);
        } else {
          companyMap.set(company.company_id, { ...company });
        }
      });
    });

    const by_company = Array.from(companyMap.values());

    // Calculer les totaux
    const totals = {
      total_employees: Math.max(...by_company.map(c => c.total_employee_count), 0),
      total_employees_excluding_rh: Math.max(...by_company.map(c => c.employee_count), 0),
      total_rh: Math.max(...by_company.map(c => c.rh_count), 0),
      total_payslip_count: by_company.reduce((sum, c) => sum + c.payslip_count, 0),
      total_gross_salary: by_company.reduce((sum, c) => sum + c.gross_salary, 0),
      total_net_salary: by_company.reduce((sum, c) => sum + c.net_salary, 0),
      total_employer_charges: by_company.reduce((sum, c) => sum + c.employer_charges, 0),
      average_gross_per_company: by_company.length > 0
        ? by_company.reduce((sum, c) => sum + c.gross_salary, 0) / by_company.length
        : 0,
      average_employees_per_company: by_company.length > 0
        ? by_company.reduce((sum, c) => sum + c.total_employee_count, 0) / by_company.length
        : 0
    };

    return {
      metadata: {
        reference_year: selectedYear,
        reference_month: 0,
        generated_at: new Date().toISOString(),
        company_count: by_company.length
      },
      totals,
      by_company
    };
  };

  // Filtrage et tri
  const filteredAndSortedCompanies = useMemo(() => {
    if (!stats?.by_company) return [];

    const filtered = stats.by_company.filter(company =>
      selectedCompanyIds.has(company.company_id) &&
      (company.company_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
       company.siret?.includes(searchTerm))
    );

    filtered.sort((a, b) => {
      const aValue = a[sortKey];
      const bValue = b[sortKey];

      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortOrder === 'asc'
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }

      const aNum = Number(aValue) || 0;
      const bNum = Number(bValue) || 0;
      return sortOrder === 'asc' ? aNum - bNum : bNum - aNum;
    });

    return filtered;
  }, [stats, searchTerm, sortKey, sortOrder, selectedCompanyIds]);

  // Calculer les totaux filtrés basés sur les entreprises sélectionnées
  const filteredTotals = useMemo(() => {
    if (!filteredAndSortedCompanies.length) {
      return {
        total_employees: 0,
        total_employees_excluding_rh: 0,
        total_rh: 0,
        total_payslip_count: 0,
        total_gross_salary: 0,
        total_net_salary: 0,
        total_employer_charges: 0,
        average_gross_per_company: 0,
        average_employees_per_company: 0,
        company_count: 0
      };
    }

    const totals = filteredAndSortedCompanies.reduce((acc, company) => {
      acc.total_employees += company.total_employee_count;
      acc.total_employees_excluding_rh += company.employee_count;
      acc.total_rh += company.rh_count;
      acc.total_payslip_count += company.payslip_count;
      acc.total_gross_salary += company.gross_salary;
      acc.total_net_salary += company.net_salary;
      acc.total_employer_charges += company.employer_charges;
      return acc;
    }, {
      total_employees: 0,
      total_employees_excluding_rh: 0,
      total_rh: 0,
      total_payslip_count: 0,
      total_gross_salary: 0,
      total_net_salary: 0,
      total_employer_charges: 0,
      average_gross_per_company: 0,
      average_employees_per_company: 0,
      company_count: filteredAndSortedCompanies.length
    });

    totals.average_gross_per_company = totals.company_count > 0
      ? totals.total_gross_salary / totals.company_count
      : 0;
    totals.average_employees_per_company = totals.company_count > 0
      ? totals.total_employees / totals.company_count
      : 0;

    return totals;
  }, [filteredAndSortedCompanies]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatCompactNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M€`;
    if (num >= 1000) return `${(num / 1000).toFixed(0)}k€`;
    return formatCurrency(num);
  };

  const formatMonth = (month: number) => {
    const months = [
      'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
      'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
    ];
    return months[month - 1] || month;
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('asc');
    }
  };

  const exportToCSV = () => {
    if (!stats) return;

    const headers = [
      'Entreprise', 'SIRET', 'Employés (hors-RH)', 'RH', 'Total Employés',
      'Bulletins', 'Masse Sal. Brute', 'Masse Sal. Nette', 'Charges Patronales'
    ];

    const rows = filteredAndSortedCompanies.map(company => [
      company.company_name,
      company.siret || '',
      company.employee_count,
      company.rh_count,
      company.total_employee_count,
      company.payslip_count,
      company.gross_salary,
      company.net_salary,
      company.employer_charges
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    const filename = periodMode === 'month'
      ? `groupe_stats_${selectedYear}_${selectedMonth}.csv`
      : periodMode === 'year'
      ? `groupe_stats_${selectedYear}.csv`
      : `groupe_stats_${startYear}-${endYear}.csv`;
    link.download = filename;
    link.click();
  };

  const toggleCompanySelection = (companyId: string) => {
    const newSet = new Set(selectedCompanyIds);
    if (newSet.has(companyId)) {
      newSet.delete(companyId);
    } else {
      newSet.add(companyId);
    }
    setSelectedCompanyIds(newSet);
  };

  const toggleAllCompanies = () => {
    if (selectedCompanyIds.size === availableCompanies.length) {
      setSelectedCompanyIds(new Set());
    } else {
      setSelectedCompanyIds(new Set(availableCompanies.map(c => c.company_id)));
    }
  };

  // Données pour les graphiques
  const chartData = useMemo(() => {
    if (!stats?.by_company) return [];
    return filteredAndSortedCompanies.map(company => ({
      name: company.company_name.length > 15
        ? company.company_name.substring(0, 15) + '...'
        : company.company_name,
      fullName: company.company_name,
      employees: company.employee_count,
      rh: company.rh_count,
      grossSalary: company.gross_salary,
      charges: company.employer_charges,
    }));
  }, [stats, filteredAndSortedCompanies]);

  const pieChartData = useMemo(() => {
    if (!stats?.by_company) return [];
    return filteredAndSortedCompanies.map(company => ({
      name: company.company_name,
      value: company.total_employee_count,
    }));
  }, [stats, filteredAndSortedCompanies]);

  const evolutionChartData = useMemo(() => {
    if (!evolutionData || evolutionData.length === 0) {
      return [];
    }

    // Filtrer par entreprises sélectionnées
    const filteredEvolution = evolutionData.filter(point =>
      selectedCompanyIds.size === 0 || selectedCompanyIds.has(point.company_id)
    );

    // Grouper par mois
    const byMonth = new Map<string, { month: string, gross: number, charges: number }>();

    filteredEvolution.forEach(point => {
      const key = `${point.year}-${String(point.month).padStart(2, '0')}`;
      const monthLabel = `${formatMonth(point.month).substring(0, 3)} ${point.year}`;

      const existing = byMonth.get(key);
      if (existing) {
        existing.gross += point.total_gross;
        existing.charges += point.total_employer_charges;
      } else {
        byMonth.set(key, {
          month: monthLabel,
          gross: point.total_gross,
          charges: point.total_employer_charges
        });
      }
    });

    // Prendre les 12 derniers mois et filtrer ceux qui ont au moins une valeur non-nulle
    const allMonths = Array.from(byMonth.values()).slice(-12);

    // Ne garder que les mois avec des données
    const monthsWithData = allMonths.filter(m => m.gross > 0 || m.charges > 0);

    // Si aucun mois n'a de données, retourner tableau vide
    // Sinon, retourner tous les mois pour garder la continuité temporelle
    return monthsWithData.length > 0 ? allMonths : [];
  }, [evolutionData, selectedCompanyIds]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(-1)}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Retour
        </Button>
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="container mx-auto p-6">
        <Alert>
          <AlertDescription>Aucune statistique disponible</AlertDescription>
        </Alert>
      </div>
    );
  }

  const chargeRate = filteredTotals.total_gross_salary > 0
    ? (filteredTotals.total_employer_charges / filteredTotals.total_gross_salary) * 100
    : 0;

  const avgGrossPerEmployee = filteredTotals.total_employees > 0
    ? filteredTotals.total_gross_salary / filteredTotals.total_employees
    : 0;

  const getPeriodLabel = () => {
    if (periodMode === 'month') {
      return `${formatMonth(selectedMonth)} ${selectedYear}`;
    } else if (periodMode === 'year') {
      return `Année ${selectedYear}`;
    } else {
      return `${startYear} - ${endYear}`;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header sobre */}
      <div className="flex items-center justify-between">
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
            className="mb-2"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour
          </Button>
          <h1 className="text-3xl font-bold">Vue Consolidée du Groupe</h1>
          <div className="flex items-center gap-3 text-muted-foreground mt-1">
            <span className="flex items-center gap-1">
              <Building2 className="h-4 w-4" />
              {stats.metadata.company_count} entreprise{stats.metadata.company_count > 1 ? 's' : ''}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              {getPeriodLabel()}
            </span>
          </div>
        </div>

        <Button onClick={exportToCSV} variant="outline">
          <Download className="h-4 w-4 mr-2" />
          Export CSV
        </Button>
      </div>

      {/* Filtres et sélection de période */}
      <Card className="shadow-lg border-0">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filtres et Période
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Sélection de période */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label>Type de période</Label>
              <Select value={periodMode} onValueChange={(v) => setPeriodMode(v as PeriodMode)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="month">Mensuelle</SelectItem>
                  <SelectItem value="year">Annuelle</SelectItem>
                  <SelectItem value="range">Pluriannuelle</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {periodMode === 'month' && (
              <>
                <div className="space-y-2">
                  <Label>Mois</Label>
                  <Select
                    value={selectedMonth.toString()}
                    onValueChange={(v) => setSelectedMonth(Number(v))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 12 }, (_, i) => i + 1).map(month => (
                        <SelectItem key={month} value={month.toString()}>
                          {formatMonth(month)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Année</Label>
                  <Select
                    value={selectedYear.toString()}
                    onValueChange={(v) => setSelectedYear(Number(v))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map(year => (
                        <SelectItem key={year} value={year.toString()}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            {periodMode === 'year' && (
              <div className="space-y-2">
                <Label>Année</Label>
                <Select
                  value={selectedYear.toString()}
                  onValueChange={(v) => setSelectedYear(Number(v))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map(year => (
                      <SelectItem key={year} value={year.toString()}>
                        {year}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {periodMode === 'range' && (
              <>
                <div className="space-y-2">
                  <Label>Année de début</Label>
                  <Select
                    value={startYear.toString()}
                    onValueChange={(v) => setStartYear(Number(v))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 10 }, (_, i) => new Date().getFullYear() - i).map(year => (
                        <SelectItem key={year} value={year.toString()}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Année de fin</Label>
                  <Select
                    value={endYear.toString()}
                    onValueChange={(v) => setEndYear(Number(v))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 10 }, (_, i) => new Date().getFullYear() - i).map(year => (
                        <SelectItem key={year} value={year.toString()}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </div>

          {/* Sélection d'entreprises */}
          <div className="space-y-2">
            <Label>Entreprises affichées ({selectedCompanyIds.size}/{availableCompanies.length})</Label>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={toggleAllCompanies}
                className="h-8"
              >
                <CheckCircle2 className="h-3 w-3 mr-1" />
                {selectedCompanyIds.size === availableCompanies.length ? 'Tout désélectionner' : 'Tout sélectionner'}
              </Button>
              {availableCompanies.map(company => (
                <Badge
                  key={company.company_id}
                  variant={selectedCompanyIds.has(company.company_id) ? "default" : "outline"}
                  className="cursor-pointer hover:bg-primary/80 transition-colors"
                  onClick={() => toggleCompanySelection(company.company_id)}
                >
                  {company.company_name}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* KPIs Globaux */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-blue-50 border-blue-100">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-blue-900">Entreprises</CardTitle>
            <Building2 className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-900">{filteredTotals.company_count}</div>
            <p className="text-xs text-blue-700 mt-1">
              {filteredTotals.average_employees_per_company.toFixed(0)} employés moy.
            </p>
          </CardContent>
        </Card>

        <Card className="bg-green-50 border-green-100">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-green-900">Total Employés</CardTitle>
            <Users className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-900">{filteredTotals.total_employees}</div>
            <div className="flex gap-2 mt-1">
              <Badge variant="secondary" className="text-xs bg-green-100 text-green-800">
                {filteredTotals.total_employees_excluding_rh} hors-RH
              </Badge>
              <Badge variant="outline" className="text-xs border-green-300 text-green-700">
                <UserCheck className="h-3 w-3 mr-1" />
                {filteredTotals.total_rh} RH
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-purple-50 border-purple-100">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-purple-900">Masse Salariale Brute</CardTitle>
            <DollarSign className="h-4 w-4 text-purple-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-900">
              {formatCompactNumber(filteredTotals.total_gross_salary)}
            </div>
            <p className="text-xs text-purple-700 mt-1">
              {formatCompactNumber(avgGrossPerEmployee)} moy. /employé
            </p>
          </CardContent>
        </Card>

        <Card className="bg-orange-50 border-orange-100">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-orange-900">Charges Patronales</CardTitle>
            <TrendingUp className="h-4 w-4 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-900">
              {formatCompactNumber(filteredTotals.total_employer_charges)}
            </div>
            <p className="text-xs text-orange-700 mt-1 flex items-center">
              <Percent className="h-3 w-3 mr-1" />
              {chargeRate.toFixed(1)}% du brut
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Onglets pour différentes vues */}
      <Tabs defaultValue="table" className="space-y-4">
        <TabsList className="grid w-full grid-cols-5 lg:w-[650px]">
          <TabsTrigger value="table">
            <ArrowUpDown className="h-4 w-4 mr-2" />
            Tableau
          </TabsTrigger>
          <TabsTrigger value="kpis">
            <Calculator className="h-4 w-4 mr-2" />
            KPIs
          </TabsTrigger>
          <TabsTrigger value="charts">
            <BarChart3 className="h-4 w-4 mr-2" />
            Graphiques
          </TabsTrigger>
          <TabsTrigger value="comparison">
            <PieChartIcon className="h-4 w-4 mr-2" />
            Répartition
          </TabsTrigger>
          <TabsTrigger value="evolution">
            <TrendingUp className="h-4 w-4 mr-2" />
            Évolutions
          </TabsTrigger>
        </TabsList>

        {/* Tableau détaillé */}
        <TabsContent value="table" className="space-y-4">
          <Card className="shadow-lg border-0">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Détails par Entreprise</CardTitle>
                  <CardDescription>
                    Vue détaillée des statistiques de chaque entreprise du groupe
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Rechercher..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-64"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="text-left p-3">
                        <button
                          onClick={() => handleSort('company_name')}
                          className="font-medium hover:underline flex items-center"
                        >
                          Entreprise
                          <ArrowUpDown className="h-3 w-3 ml-1" />
                        </button>
                      </th>
                      <th className="text-right p-3">
                        <button
                          onClick={() => handleSort('employee_count')}
                          className="font-medium hover:underline flex items-center justify-end"
                        >
                          Employés (hors-RH)
                          <ArrowUpDown className="h-3 w-3 ml-1" />
                        </button>
                      </th>
                      <th className="text-right p-3">
                        <button
                          onClick={() => handleSort('rh_count')}
                          className="font-medium hover:underline flex items-center justify-end"
                        >
                          RH
                          <ArrowUpDown className="h-3 w-3 ml-1" />
                        </button>
                      </th>
                      <th className="text-right p-3">
                        <button
                          onClick={() => handleSort('payslip_count')}
                          className="font-medium hover:underline flex items-center justify-end"
                        >
                          Bulletins
                          <ArrowUpDown className="h-3 w-3 ml-1" />
                        </button>
                      </th>
                      <th className="text-right p-3">
                        <button
                          onClick={() => handleSort('gross_salary')}
                          className="font-medium hover:underline flex items-center justify-end"
                        >
                          Masse Sal. Brute
                          <ArrowUpDown className="h-3 w-3 ml-1" />
                        </button>
                      </th>
                      <th className="text-right p-3">
                        <button
                          onClick={() => handleSort('net_salary')}
                          className="font-medium hover:underline flex items-center justify-end"
                        >
                          Masse Sal. Nette
                          <ArrowUpDown className="h-3 w-3 ml-1" />
                        </button>
                      </th>
                      <th className="text-right p-3">
                        <button
                          onClick={() => handleSort('employer_charges')}
                          className="font-medium hover:underline flex items-center justify-end"
                        >
                          Charges
                          <ArrowUpDown className="h-3 w-3 ml-1" />
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAndSortedCompanies.map((company) => {
                      const companyChargeRate = company.gross_salary > 0
                        ? (company.employer_charges / company.gross_salary) * 100
                        : 0;

                      return (
                        <tr
                          key={company.company_id}
                          className="border-b hover:bg-blue-50/50 transition-colors cursor-pointer"
                          onClick={() => {
                            console.log('Naviguer vers entreprise:', company.company_id);
                          }}
                        >
                          <td className="p-3">
                            <div>
                              <div className="font-medium">{company.company_name}</div>
                              {company.siret && (
                                <div className="text-xs text-muted-foreground font-mono">
                                  {company.siret}
                                </div>
                              )}
                            </div>
                          </td>
                          <td className="text-right p-3">
                            <Badge variant="secondary">
                              {company.employee_count}
                            </Badge>
                          </td>
                          <td className="text-right p-3">
                            <Badge variant="outline">
                              {company.rh_count}
                            </Badge>
                          </td>
                          <td className="text-right p-3">
                            <span className="font-medium">{company.payslip_count}</span>
                          </td>
                          <td className="text-right p-3">
                            <div className="font-medium">
                              {formatCurrency(company.gross_salary)}
                            </div>
                          </td>
                          <td className="text-right p-3">
                            <span className={`font-medium ${company.net_salary > 0 ? 'text-green-600' : ''}`}>
                              {formatCurrency(company.net_salary)}
                            </span>
                          </td>
                          <td className="text-right p-3">
                            <div>
                              <div className={`font-medium ${companyChargeRate > 45 ? 'text-red-600' : ''}`}>
                                {formatCurrency(company.employer_charges)}
                              </div>
                              <div className={`text-xs ${companyChargeRate > 45 ? 'text-red-600' : 'text-muted-foreground'}`}>
                                {companyChargeRate.toFixed(1)}%
                              </div>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 font-bold bg-muted/50">
                      <td className="p-3">Total</td>
                      <td className="text-right p-3">{filteredTotals.total_employees_excluding_rh}</td>
                      <td className="text-right p-3">{filteredTotals.total_rh}</td>
                      <td className="text-right p-3">{filteredTotals.total_payslip_count}</td>
                      <td className="text-right p-3">{formatCurrency(filteredTotals.total_gross_salary)}</td>
                      <td className="text-right p-3 text-green-600">{formatCurrency(filteredTotals.total_net_salary)}</td>
                      <td className="text-right p-3">{formatCurrency(filteredTotals.total_employer_charges)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Onglet KPIs */}
        <TabsContent value="kpis" className="space-y-4">
          {/* KPIs Comparatifs - Tableau */}
          <Card className="shadow-lg border-0">
            <CardHeader>
              <CardTitle>Indicateurs Clés de Performance par Entreprise</CardTitle>
              <CardDescription>
                Comparaison des ratios et métriques stratégiques
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="text-left p-3 font-medium">Entreprise</th>
                      <th className="text-right p-3 font-medium">Taux de Charges</th>
                      <th className="text-right p-3 font-medium">Taux Rétention Net</th>
                      <th className="text-right p-3 font-medium">Coût/Employé</th>
                      <th className="text-right p-3 font-medium">Masse Sal./Employé</th>
                      <th className="text-right p-3 font-medium">Charges/Employé</th>
                      <th className="text-right p-3 font-medium">Ratio RH</th>
                      <th className="text-right p-3 font-medium">Coût/Bulletin</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAndSortedCompanies.map((company) => {
                      const chargeRate = company.gross_salary > 0
                        ? (company.employer_charges / company.gross_salary) * 100
                        : 0;
                      const netRetentionRate = company.gross_salary > 0
                        ? (company.net_salary / company.gross_salary) * 100
                        : 0;
                      const totalCostPerEmployee = company.total_employee_count > 0
                        ? (company.gross_salary + company.employer_charges) / company.total_employee_count
                        : 0;
                      const grossPerEmployee = company.total_employee_count > 0
                        ? company.gross_salary / company.total_employee_count
                        : 0;
                      const chargesPerEmployee = company.total_employee_count > 0
                        ? company.employer_charges / company.total_employee_count
                        : 0;
                      const rhRatio = company.total_employee_count > 0
                        ? (company.rh_count / company.total_employee_count) * 100
                        : 0;
                      const costPerPayslip = company.payslip_count > 0
                        ? (company.gross_salary + company.employer_charges) / company.payslip_count
                        : 0;

                      return (
                        <tr key={company.company_id} className="border-b hover:bg-blue-50/50 transition-colors">
                          <td className="p-3">
                            <div className="font-medium">{company.company_name}</div>
                            <div className="text-xs text-muted-foreground">
                              {company.total_employee_count} employés · {company.payslip_count} bulletins
                            </div>
                          </td>
                          <td className="text-right p-3">
                            <span className={`font-medium ${
                              chargeRate > 45 ? 'text-red-600' :
                              chargeRate > 40 ? 'text-amber-600' :
                              'text-green-600'
                            }`}>
                              {chargeRate.toFixed(1)}%
                            </span>
                          </td>
                          <td className="text-right p-3">
                            <span className="font-medium text-green-600">
                              {netRetentionRate.toFixed(1)}%
                            </span>
                          </td>
                          <td className="text-right p-3">
                            <span className="font-medium">
                              {formatCurrency(totalCostPerEmployee)}
                            </span>
                          </td>
                          <td className="text-right p-3">
                            <span className="font-medium">
                              {formatCurrency(grossPerEmployee)}
                            </span>
                          </td>
                          <td className="text-right p-3">
                            <span className="font-medium">
                              {formatCurrency(chargesPerEmployee)}
                            </span>
                          </td>
                          <td className="text-right p-3">
                            <span className="font-medium">
                              {rhRatio.toFixed(1)}%
                            </span>
                          </td>
                          <td className="text-right p-3">
                            <span className="font-medium">
                              {formatCurrency(costPerPayslip)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 font-bold bg-muted/50">
                      <td className="p-3">Moyenne Groupe</td>
                      <td className="text-right p-3">{chargeRate.toFixed(1)}%</td>
                      <td className="text-right p-3 text-green-600">
                        {filteredTotals.total_gross_salary > 0
                          ? ((filteredTotals.total_net_salary / filteredTotals.total_gross_salary) * 100).toFixed(1)
                          : 0}%
                      </td>
                      <td className="text-right p-3">
                        {formatCurrency(
                          filteredTotals.total_employees > 0
                            ? (filteredTotals.total_gross_salary + filteredTotals.total_employer_charges) / filteredTotals.total_employees
                            : 0
                        )}
                      </td>
                      <td className="text-right p-3">
                        {formatCurrency(avgGrossPerEmployee)}
                      </td>
                      <td className="text-right p-3">
                        {formatCurrency(
                          filteredTotals.total_employees > 0
                            ? filteredTotals.total_employer_charges / filteredTotals.total_employees
                            : 0
                        )}
                      </td>
                      <td className="text-right p-3">
                        {filteredTotals.total_employees > 0
                          ? ((filteredTotals.total_rh / filteredTotals.total_employees) * 100).toFixed(1)
                          : 0}%
                      </td>
                      <td className="text-right p-3">
                        {formatCurrency(
                          filteredTotals.total_payslip_count > 0
                            ? (filteredTotals.total_gross_salary + filteredTotals.total_employer_charges) / filteredTotals.total_payslip_count
                            : 0
                        )}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Graphiques de comparaison des KPIs */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="shadow-lg border-0">
              <CardHeader>
                <CardTitle>Taux de Charges par Entreprise</CardTitle>
                <CardDescription>Charges patronales en % du salaire brut</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={filteredAndSortedCompanies.map(c => ({
                      name: c.company_name.length > 12 ? c.company_name.substring(0, 12) + '...' : c.company_name,
                      fullName: c.company_name,
                      rate: c.gross_salary > 0 ? (c.employer_charges / c.gross_salary) * 100 : 0
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="name" stroke="#6b7280" fontSize={11} angle={-45} textAnchor="end" height={80} />
                    <YAxis stroke="#6b7280" fontSize={12} />
                    <Tooltip
                      formatter={(value: number) => `${value.toFixed(1)}%`}
                      labelFormatter={(label) => {
                        const item = filteredAndSortedCompanies.find(c =>
                          c.company_name === label || c.company_name.startsWith(label)
                        );
                        return item?.company_name || label;
                      }}
                    />
                    <Bar dataKey="rate" name="Taux de Charges">
                      {filteredAndSortedCompanies.map((company, index) => {
                        const rate = company.gross_salary > 0 ? (company.employer_charges / company.gross_salary) * 100 : 0;
                        return (
                          <Cell
                            key={`cell-${index}`}
                            fill={rate > 45 ? '#ef4444' : rate > 40 ? '#f59e0b' : '#10b981'}
                          />
                        );
                      })}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="shadow-lg border-0">
              <CardHeader>
                <CardTitle>Coût Total par Employé</CardTitle>
                <CardDescription>Coût employeur complet (brut + charges)</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={filteredAndSortedCompanies.map(c => ({
                      name: c.company_name.length > 12 ? c.company_name.substring(0, 12) + '...' : c.company_name,
                      fullName: c.company_name,
                      cost: c.total_employee_count > 0 ? (c.gross_salary + c.employer_charges) / c.total_employee_count : 0
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="name" stroke="#6b7280" fontSize={11} angle={-45} textAnchor="end" height={80} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={(v) => formatCompactNumber(v)} />
                    <Tooltip
                      formatter={(value: number) => formatCurrency(value)}
                      labelFormatter={(label) => {
                        const item = filteredAndSortedCompanies.find(c =>
                          c.company_name === label || c.company_name.startsWith(label)
                        );
                        return item?.company_name || label;
                      }}
                    />
                    <Bar dataKey="cost" fill="#3b82f6" name="Coût/Employé" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="shadow-lg border-0">
              <CardHeader>
                <CardTitle>Ratio RH / Total Employés</CardTitle>
                <CardDescription>Proportion de personnel RH dans l'effectif total</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={filteredAndSortedCompanies.map(c => ({
                      name: c.company_name.length > 12 ? c.company_name.substring(0, 12) + '...' : c.company_name,
                      fullName: c.company_name,
                      ratio: c.total_employee_count > 0 ? (c.rh_count / c.total_employee_count) * 100 : 0
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="name" stroke="#6b7280" fontSize={11} angle={-45} textAnchor="end" height={80} />
                    <YAxis stroke="#6b7280" fontSize={12} />
                    <Tooltip
                      formatter={(value: number) => `${value.toFixed(1)}%`}
                      labelFormatter={(label) => {
                        const item = filteredAndSortedCompanies.find(c =>
                          c.company_name === label || c.company_name.startsWith(label)
                        );
                        return item?.company_name || label;
                      }}
                    />
                    <Bar dataKey="ratio" fill="#6b7280" name="Ratio RH" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="shadow-lg border-0">
              <CardHeader>
                <CardTitle>Masse Salariale par Employé</CardTitle>
                <CardDescription>Salaire brut moyen par employé</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={filteredAndSortedCompanies.map(c => ({
                      name: c.company_name.length > 12 ? c.company_name.substring(0, 12) + '...' : c.company_name,
                      fullName: c.company_name,
                      salary: c.total_employee_count > 0 ? c.gross_salary / c.total_employee_count : 0
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="name" stroke="#6b7280" fontSize={11} angle={-45} textAnchor="end" height={80} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={(v) => formatCompactNumber(v)} />
                    <Tooltip
                      formatter={(value: number) => formatCurrency(value)}
                      labelFormatter={(label) => {
                        const item = filteredAndSortedCompanies.find(c =>
                          c.company_name === label || c.company_name.startsWith(label)
                        );
                        return item?.company_name || label;
                      }}
                    />
                    <Bar dataKey="salary" fill="#8b5cf6" name="Masse Sal./Employé" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          {/* Statistiques de distribution */}
          <Card className="shadow-lg border-0">
            <CardHeader>
              <CardTitle>Analyse Statistique des KPIs</CardTitle>
              <CardDescription>Distribution des indicateurs à travers le groupe</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {(() => {
                  // Calculer les statistiques pour le taux de charges
                  const chargeRates = filteredAndSortedCompanies
                    .filter(c => c.gross_salary > 0)
                    .map(c => (c.employer_charges / c.gross_salary) * 100)
                    .sort((a, b) => a - b);

                  const avgChargeRate = chargeRates.length > 0
                    ? chargeRates.reduce((a, b) => a + b, 0) / chargeRates.length
                    : 0;
                  const minChargeRate = chargeRates.length > 0 ? chargeRates[0] : 0;
                  const maxChargeRate = chargeRates.length > 0 ? chargeRates[chargeRates.length - 1] : 0;
                  const medianChargeRate = chargeRates.length > 0
                    ? chargeRates.length % 2 === 0
                      ? (chargeRates[chargeRates.length / 2 - 1] + chargeRates[chargeRates.length / 2]) / 2
                      : chargeRates[Math.floor(chargeRates.length / 2)]
                    : 0;

                  // Calculer les statistiques pour le coût par employé
                  const costsPerEmployee = filteredAndSortedCompanies
                    .filter(c => c.total_employee_count > 0)
                    .map(c => (c.gross_salary + c.employer_charges) / c.total_employee_count)
                    .sort((a, b) => a - b);

                  const avgCostPerEmployee = costsPerEmployee.length > 0
                    ? costsPerEmployee.reduce((a, b) => a + b, 0) / costsPerEmployee.length
                    : 0;
                  const minCostPerEmployee = costsPerEmployee.length > 0 ? costsPerEmployee[0] : 0;
                  const maxCostPerEmployee = costsPerEmployee.length > 0 ? costsPerEmployee[costsPerEmployee.length - 1] : 0;

                  // Calculer les statistiques pour le ratio RH
                  const rhRatios = filteredAndSortedCompanies
                    .filter(c => c.total_employee_count > 0)
                    .map(c => (c.rh_count / c.total_employee_count) * 100)
                    .sort((a, b) => a - b);

                  const avgRhRatio = rhRatios.length > 0
                    ? rhRatios.reduce((a, b) => a + b, 0) / rhRatios.length
                    : 0;
                  const minRhRatio = rhRatios.length > 0 ? rhRatios[0] : 0;
                  const maxRhRatio = rhRatios.length > 0 ? rhRatios[rhRatios.length - 1] : 0;

                  // Calculer les statistiques pour la masse salariale par employé
                  const salariesPerEmployee = filteredAndSortedCompanies
                    .filter(c => c.total_employee_count > 0)
                    .map(c => c.gross_salary / c.total_employee_count)
                    .sort((a, b) => a - b);

                  const avgSalaryPerEmployee = salariesPerEmployee.length > 0
                    ? salariesPerEmployee.reduce((a, b) => a + b, 0) / salariesPerEmployee.length
                    : 0;
                  const minSalaryPerEmployee = salariesPerEmployee.length > 0 ? salariesPerEmployee[0] : 0;
                  const maxSalaryPerEmployee = salariesPerEmployee.length > 0 ? salariesPerEmployee[salariesPerEmployee.length - 1] : 0;

                  return (
                    <>
                      <div className="space-y-3">
                        <h3 className="font-semibold text-sm">Taux de Charges (%)</h3>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Minimum</span>
                            <span className="font-medium text-green-600">{minChargeRate.toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Médiane</span>
                            <span className="font-medium">{medianChargeRate.toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Moyenne</span>
                            <span className="font-medium">{avgChargeRate.toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Maximum</span>
                            <span className="font-medium text-red-600">{maxChargeRate.toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between pt-1 border-t">
                            <span className="text-muted-foreground">Écart</span>
                            <span className="font-medium">{(maxChargeRate - minChargeRate).toFixed(1)}%</span>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <h3 className="font-semibold text-sm">Coût par Employé</h3>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Minimum</span>
                            <span className="font-medium text-green-600">{formatCurrency(minCostPerEmployee)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Moyenne</span>
                            <span className="font-medium">{formatCurrency(avgCostPerEmployee)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Maximum</span>
                            <span className="font-medium text-red-600">{formatCurrency(maxCostPerEmployee)}</span>
                          </div>
                          <div className="flex justify-between pt-1 border-t">
                            <span className="text-muted-foreground">Écart</span>
                            <span className="font-medium">{formatCurrency(maxCostPerEmployee - minCostPerEmployee)}</span>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <h3 className="font-semibold text-sm">Ratio RH (%)</h3>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Minimum</span>
                            <span className="font-medium">{minRhRatio.toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Moyenne</span>
                            <span className="font-medium">{avgRhRatio.toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Maximum</span>
                            <span className="font-medium">{maxRhRatio.toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between pt-1 border-t">
                            <span className="text-muted-foreground">Écart</span>
                            <span className="font-medium">{(maxRhRatio - minRhRatio).toFixed(1)}%</span>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <h3 className="font-semibold text-sm">Masse Sal. par Employé</h3>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Minimum</span>
                            <span className="font-medium">{formatCurrency(minSalaryPerEmployee)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Moyenne</span>
                            <span className="font-medium">{formatCurrency(avgSalaryPerEmployee)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Maximum</span>
                            <span className="font-medium">{formatCurrency(maxSalaryPerEmployee)}</span>
                          </div>
                          <div className="flex justify-between pt-1 border-t">
                            <span className="text-muted-foreground">Écart</span>
                            <span className="font-medium">{formatCurrency(maxSalaryPerEmployee - minSalaryPerEmployee)}</span>
                          </div>
                        </div>
                      </div>
                    </>
                  );
                })()}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Graphiques de comparaison */}
        <TabsContent value="charts" className="space-y-4">
          <Card className="shadow-lg border-0">
            <CardHeader>
              <CardTitle>Comparaison : Masse Salariale & Charges</CardTitle>
              <CardDescription>Par entreprise</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
                  <YAxis stroke="#6b7280" fontSize={12} tickFormatter={(v) => formatCompactNumber(v)} />
                  <Tooltip
                    formatter={(value: number) => formatCurrency(value)}
                    labelFormatter={(label) => {
                      const item = chartData.find(d => d.name === label);
                      return item?.fullName || label;
                    }}
                  />
                  <Legend />
                  <Bar dataKey="grossSalary" fill="#3b82f6" name="Masse Sal. Brute" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="charges" fill="#ef4444" name="Charges Patronales" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="shadow-lg border-0">
            <CardHeader>
              <CardTitle>Comparaison : Effectifs</CardTitle>
              <CardDescription>Employés vs RH par entreprise</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
                  <YAxis stroke="#6b7280" fontSize={12} />
                  <Tooltip
                    labelFormatter={(label) => {
                      const item = chartData.find(d => d.name === label);
                      return item?.fullName || label;
                    }}
                  />
                  <Legend />
                  <Bar dataKey="employees" fill="#10b981" name="Employés (hors-RH)" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="rh" fill="#6b7280" name="RH" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Répartition en camembert */}
        <TabsContent value="comparison" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="shadow-lg border-0">
              <CardHeader>
                <CardTitle>Répartition des Effectifs</CardTitle>
                <CardDescription>Par entreprise</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={420}>
                  <PieChart>
                    <Pie
                      data={pieChartData}
                      cx="50%"
                      cy="40%"
                      labelLine={true}
                      label={({ percent }) => `${(percent * 100).toFixed(1)}%`}
                      outerRadius={120}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {pieChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name: string, props: any) => [
                        `${value} employé${value > 1 ? 's' : ''}`,
                        props.payload.name
                      ]}
                    />
                    <Legend
                      verticalAlign="bottom"
                      height={70}
                      wrapperStyle={{ fontSize: '13px', paddingTop: '15px' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="shadow-lg border-0">
              <CardHeader>
                <CardTitle>Indicateurs de Performance</CardTitle>
                <CardDescription>Ratios et moyennes du groupe</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Taux de charges moyen</span>
                    <span className={`font-medium ${chargeRate > 45 ? 'text-red-600' : chargeRate > 40 ? 'text-amber-600' : 'text-green-600'}`}>
                      {chargeRate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${chargeRate > 45 ? 'bg-red-500' : chargeRate > 40 ? 'bg-amber-500' : 'bg-green-500'}`}
                      style={{ width: `${Math.min(chargeRate, 100)}%` }}
                    />
                  </div>
                </div>

                <div className="flex justify-between text-sm pt-1">
                  <span className="text-muted-foreground">Masse sal. brute moy. /entreprise</span>
                  <span className="font-medium">
                    {formatCurrency(filteredTotals.average_gross_per_company)}
                  </span>
                </div>

                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Masse sal. brute moy. /employé</span>
                  <span className="font-medium">
                    {formatCurrency(avgGrossPerEmployee)}
                  </span>
                </div>

                <div className="space-y-1.5 pt-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Ratio RH / Total employés</span>
                    <span className="font-medium">
                      {filteredTotals.total_employees > 0
                        ? ((filteredTotals.total_rh / filteredTotals.total_employees) * 100).toFixed(1)
                        : 0}%
                    </span>
                  </div>
                  <div className="h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 transition-all"
                      style={{
                        width: `${filteredTotals.total_employees > 0
                          ? (filteredTotals.total_rh / filteredTotals.total_employees) * 100
                          : 0}%`
                      }}
                    />
                  </div>
                </div>

                <div className="flex justify-between text-sm pt-1">
                  <span className="text-muted-foreground">Coût employeur total</span>
                  <span className="font-medium">
                    {formatCompactNumber(
                      filteredTotals.total_gross_salary + filteredTotals.total_employer_charges
                    )}
                  </span>
                </div>

                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Taux de rétention net</span>
                  <span className="font-medium text-green-600">
                    {filteredTotals.total_gross_salary > 0
                      ? ((filteredTotals.total_net_salary / filteredTotals.total_gross_salary) * 100).toFixed(1)
                      : 0}%
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Onglet Évolutions */}
        <TabsContent value="evolution" className="space-y-4">
          {evolutionChartData.length > 0 ? (
            <Card className="shadow-lg border-0">
              <CardHeader>
                <CardTitle>Évolution Temporelle</CardTitle>
                <CardDescription>Masse salariale et charges sur la période</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                  <AreaChart data={evolutionChartData}>
                    <defs>
                      <linearGradient id="colorGross" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1}/>
                      </linearGradient>
                      <linearGradient id="colorCharges" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0.1}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="month" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={(v) => formatCompactNumber(v)} />
                    <Tooltip formatter={(value: number) => formatCurrency(value)} />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="gross"
                      stroke="#3b82f6"
                      fillOpacity={1}
                      fill="url(#colorGross)"
                      name="Masse Salariale Brute"
                    />
                    <Area
                      type="monotone"
                      dataKey="charges"
                      stroke="#ef4444"
                      fillOpacity={1}
                      fill="url(#colorCharges)"
                      name="Charges Patronales"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-6 text-center text-muted-foreground">
                Aucune donnée d'évolution disponible pour cette période
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
