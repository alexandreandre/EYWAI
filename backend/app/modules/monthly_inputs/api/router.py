"""
Router API du module monthly_inputs.

Appelle uniquement la couche application (commands, queries).
Aucune logique métier, aucun accès DB. Comportement HTTP identique à l'ancien routeur.
"""
from __future__ import annotations

import sys
import traceback
from typing import List

from fastapi import APIRouter, HTTPException

from app.modules.monthly_inputs.application import commands, queries
from app.modules.monthly_inputs.schemas.requests import MonthlyInput, MonthlyInputCreate
from app.modules.monthly_inputs.schemas.responses import (
    create_batch_response,
    create_single_response,
    delete_response,
)

router = APIRouter(tags=["Monthly Inputs"])


@router.get("/api/monthly-inputs")
def list_monthly_inputs(year: int, month: int):
    """Retourne toutes les saisies ponctuelles du mois, tous salariés confondus."""
    result = queries.list_monthly_inputs_by_period(year, month)
    return result.items


@router.post("/api/monthly-inputs", status_code=201)
def create_monthly_inputs(payload: List[MonthlyInput]):
    """Crée une ou plusieurs saisies mensuelles."""
    try:
        result = commands.create_monthly_inputs_batch(payload)
        return create_batch_response(result.inserted_count)
    except Exception as e:
        print(f"❌ ERREUR dans create_monthly_inputs : {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/monthly-inputs/{input_id}")
def delete_monthly_input(input_id: str):
    """Supprime une saisie ponctuelle."""
    commands.delete_monthly_input(input_id)
    return delete_response()


@router.get("/api/employees/{employee_id}/monthly-inputs")
def get_employee_monthly_inputs(employee_id: str, year: int, month: int):
    """Retourne les saisies ponctuelles (prime, acompte, etc.) pour un employé donné."""
    result = queries.list_monthly_inputs_by_employee_period(employee_id, year, month)
    return result.items


@router.post("/api/employees/{employee_id}/monthly-inputs", status_code=201)
def create_employee_monthly_inputs(employee_id: str, prime_data: MonthlyInputCreate):
    """Crée une saisie ponctuelle pour un employé."""
    try:
        result = commands.create_employee_monthly_input(employee_id, prime_data)
        return create_single_response(result.inserted_data)
    except Exception as e:
        print(f"❌ Erreur create_employee_monthly_inputs : {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/employees/{employee_id}/monthly-inputs/{input_id}")
def delete_employee_monthly_input(employee_id: str, input_id: str):
    """Supprime une saisie ponctuelle pour un employé donné."""
    try:
        commands.delete_employee_monthly_input(employee_id, input_id)
        return delete_response()
    except Exception as e:
        print(f"❌ Erreur delete_employee_monthly_input : {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/primes-catalogue")
def get_primes_catalogue():
    """Retourne le catalogue de primes (payroll_config, config_key='primes')."""
    try:
        return queries.get_primes_catalogue()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
