#!/usr/bin/env python3
import traceback

from app.core.database import supabase

# Test de l'upsert sur employee_schedules
print("Test de l'upsert sur employee_schedules...")

try:
    result = supabase.table('employee_schedules').upsert({
        'employee_id': '0488b292-3a32-49d6-bc8d-63894fb8b073',
        'year': 2025,
        'month': 11,
        'planned_calendar': {'calendrier_prevu': []},
        'actual_hours': {},
        'payroll_events': {},
        'cumuls': {}
    }, on_conflict='employee_id,year,month').execute()
    print('✅ Upsert réussi')
    print(result)
except Exception as e:
    print('❌ Erreur lors de l\'upsert:')
    print(f'Type: {type(e).__name__}')
    print(f'Message: {str(e)}')
    traceback.print_exc()
