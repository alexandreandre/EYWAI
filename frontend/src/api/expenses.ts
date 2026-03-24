// Fichier : src/api/expenses.ts

import apiClient from './apiClient';
import { type SimpleEmployee } from './absences'; // On réutilise cette interface

// --- INTERFACES ---

export type ExpenseStatus = "pending" | "validated" | "rejected";
export type ExpenseType = "Restaurant" | "Transport" | "Hôtel" | "Fournitures" | "Autre";

export interface Expense {
  id: string;
  created_at: string;
  employee_id: string;
  date: string; // "YYYY-MM-DD"
  amount: number;
  type: ExpenseType;
  description: string | null;
  receipt_url: string | null;
  status: ExpenseStatus;
  filename: string | null;
}

export interface ExpenseWithEmployee extends Expense {
  employee: SimpleEmployee;
}

export interface ExpenseCreatePayload {
  employee_id: string;
  date: string;
  amount: number;
  type: ExpenseType;
  description?: string | null;
  receipt_url?: string | null;
  filename?: string | null;
}

// --- FONCTIONS API ---

/**
 * Récupère une URL signée du backend pour uploader un fichier.
 */
export const getUploadUrl = async (filename: string) => { // <-- Accepter filename ici
  // Envoyer le nom du fichier dans le corps de la requête POST
  const response = await apiClient.post<{ path: string; signedURL: string }>(
    '/api/expenses/get-upload-url',
    { filename } // <-- Envoyer filename au backend
  );
  return response.data;
};

/**
 * Uploade le fichier directement vers le stockage Supabase via l'URL signée.
 */
export const uploadFile = async (signedUrl: string, file: File) => {
  console.log(`[DEBUG] Début de l'upload vers: ${signedUrl.split('?')[0]}...`);
  const secureUrl = signedUrl.replace(/^http:\/\//i, 'https://');
  try {
    const response = await fetch(signedUrl, {
      // 👇 VÉRIFIE BIEN CETTE LIGNE 👇
      method: 'PUT',
      // 👆 VÉRIFIE BIEN CETTE LIGNE 👆
      headers: {
        'Content-Type': file.type,
      },
      body: file,
    });

    if (!response.ok) {
      const errorBody = await response.text();
      console.error(`[ERREUR UPLOAD] Statut: ${response.status}, Réponse: ${errorBody}`);
      throw new Error(`Échec de l'upload vers Supabase Storage. Statut: ${response.status}`);
    }

    console.log(`[DEBUG] Upload terminé avec succès. Statut: ${response.status}`);

  } catch (error) {
    console.error("[ERREUR UPLOAD] Exception lors du fetch:", error);
    throw error;
  }
};

/**
 * Crée la note de frais en BDD (après upload).
 */
export const createExpense = (payload: ExpenseCreatePayload) => {
  return apiClient.post<Expense>('/api/expenses/', payload);
};

/**
 * (Employé) Récupère mes notes de frais.
 */
export const getMyExpenses = () => {
  return apiClient.get<Expense[]>('/api/expenses/me');
};

/**
 * (RH) Récupère toutes les notes de frais.
 */
export const getAllExpenses = (status?: ExpenseStatus) => {
  const params = status ? { status } : {};
  return apiClient.get<ExpenseWithEmployee[]>('/api/expenses', { params });
};

/**
 * (RH) Met à jour le statut d'une note de frais.
 */
export const updateExpenseStatus = (id: string, status: 'validated' | 'rejected') => {
  return apiClient.patch<Expense>(`/api/expenses/${id}/status`, { status });
};