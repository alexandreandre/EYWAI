import apiClient from "./apiClient";

export type EmployeeLite = {
  id: string;
  first_name: string;
  last_name: string;
};

export const getEmployeesLite = async (): Promise<EmployeeLite[]> => {
  const response = await apiClient.get<EmployeeLite[]>("/api/employees");
  return response.data ?? [];
};

