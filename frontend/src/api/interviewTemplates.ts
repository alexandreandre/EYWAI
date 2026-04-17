// Modèles de trames d'entretien (API alignée sur les schémas Pydantic)

import apiClient from "./apiClient";
import type { InterviewType } from "./annualReviews";

export type TemplateStatus = "active" | "archived";

export type QuestionType =
  | "text"
  | "textarea"
  | "number"
  | "date"
  | "boolean"
  | "single_select"
  | "multi_select";

export interface TemplateQuestion {
  id: string;
  section_id: string;
  label: string;
  question_type: string;
  options?: unknown;
  is_required: boolean;
  is_self_evaluation: boolean;
  position: number;
}

export interface TemplateSection {
  id: string;
  template_id: string;
  title: string;
  position: number;
  questions: TemplateQuestion[];
}

export interface InterviewTemplate {
  id: string;
  company_id: string;
  name: string;
  interview_type: InterviewType;
  status: string;
  created_by: string | null;
  created_at: string;
  updated_at: string | null;
  sections: TemplateSection[];
}

export interface TemplateQuestionCreate {
  label: string;
  question_type: QuestionType;
  options?: unknown;
  is_required?: boolean;
  is_self_evaluation?: boolean;
  position: number;
}

export interface TemplateSectionCreate {
  title: string;
  position: number;
  questions: TemplateQuestionCreate[];
}

export interface InterviewTemplateCreate {
  name: string;
  interview_type: InterviewType;
  sections: TemplateSectionCreate[];
}

export interface InterviewTemplateUpdate {
  name?: string;
  status?: TemplateStatus;
  sections?: TemplateSectionCreate[];
}

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  text: "Texte court",
  textarea: "Texte long",
  number: "Nombre",
  date: "Date",
  boolean: "Oui / Non",
  single_select: "Choix unique",
  multi_select: "Choix multiples",
};

export const getTemplates = () =>
  apiClient.get<InterviewTemplate[]>("/api/interview-templates");

export const getTemplate = (id: string) =>
  apiClient.get<InterviewTemplate>(`/api/interview-templates/${id}`);

export const createTemplate = (data: InterviewTemplateCreate) =>
  apiClient.post<InterviewTemplate>("/api/interview-templates", data);

export const updateTemplate = (id: string, data: InterviewTemplateUpdate) =>
  apiClient.put<InterviewTemplate>(`/api/interview-templates/${id}`, data);

export const archiveTemplate = (id: string) =>
  apiClient.post(`/api/interview-templates/${id}/archive`);

export const duplicateTemplate = (id: string) =>
  apiClient.post<InterviewTemplate>(`/api/interview-templates/${id}/duplicate`);
