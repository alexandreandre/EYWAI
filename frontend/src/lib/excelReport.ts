import type ExcelJS from "exceljs";

/** Briques de mise en forme partagées pour les exports Excel (rapports RH). */

export const REPORT_COLORS = {
  accent: "FF1D4ED8",
  titleText: "FF111827",
  subtitleText: "FF4B5563",
  sectionBg: "FFF3F4F6",
  sectionText: "FF1F2937",
  headerBg: "FFF9FAFB",
  headerText: "FF374151",
  label: "FF111827",
  muted: "FF6B7280",
  border: "FFD1D5DB",
  goodText: "FF15803D",
  warnText: "FFB45309",
  badText: "FFDC2626",
  neutralText: "FF6B7280",
} as const;

export const FMT = {
  PCT: '0.0" %"',
  PCT_INT: '0" %"',
  PCT2: '0.00" %"',
  EUR: '#,##0" €"',
  HOURS: '0.0" h"',
  INT: "#,##0",
  DEC1: "0.0",
} as const;

export type StatusKind = "good" | "warn" | "bad" | "neutral";

export const STATUS_STYLE: Record<StatusKind, { text: string; label: string }> = {
  good: { text: REPORT_COLORS.goodText, label: "OK" },
  warn: { text: REPORT_COLORS.warnText, label: "À surveiller" },
  bad: { text: REPORT_COLORS.badText, label: "Critique" },
  neutral: { text: REPORT_COLORS.neutralText, label: "—" },
};

export type CellValue =
  | { kind: "number"; value: number; fmt?: string }
  | { kind: "text"; value: string };

export const num = (value: number, fmt?: string): CellValue => ({ kind: "number", value, fmt });
export const text = (value: string): CellValue => ({ kind: "text", value });

export const thinBorder = {
  top: { style: "thin" as const, color: { argb: REPORT_COLORS.border } },
  left: { style: "thin" as const, color: { argb: REPORT_COLORS.border } },
  bottom: { style: "thin" as const, color: { argb: REPORT_COLORS.border } },
  right: { style: "thin" as const, color: { argb: REPORT_COLORS.border } },
};

const FONT = "Calibri";

export function applyValue(cell: ExcelJS.Cell, value: CellValue): void {
  if (value.kind === "number") {
    cell.value = value.value;
    if (value.fmt) cell.numFmt = value.fmt;
  } else {
    cell.value = value.value;
  }
}

export function applyStatusCell(cell: ExcelJS.Cell, status: StatusKind): void {
  const s = STATUS_STYLE[status];
  cell.value = s.label;
  cell.font = { name: FONT, size: 10, color: { argb: s.text } };
  cell.alignment = { vertical: "middle", horizontal: "left", wrapText: true, indent: 1 };
}

export function formatDateFr(isoDate: string): string {
  const parsed = new Date(isoDate);
  if (Number.isNaN(parsed.getTime())) return isoDate;
  return parsed.toLocaleDateString("fr-FR");
}

export function createReportSheet(
  wb: ExcelJS.Workbook,
  name: string,
  columnWidths: number[],
): ExcelJS.Worksheet {
  const ws = wb.addWorksheet(name, {
    views: [{ showGridLines: true }],
    properties: { defaultRowHeight: 20 },
  });
  ws.columns = columnWidths.map((width) => ({ width }));
  return ws;
}

/**
 * Constructeur de feuille avec curseur de ligne et helpers de mise en forme.
 * Modèle 3 colonnes : A = libellé, B = valeur, C = statut.
 */
export class SheetBuilder {
  private row = 1;

  constructor(
    private readonly ws: ExcelJS.Worksheet,
    private readonly lastCol: string = "C",
  ) {}

  private span(rowIdx: number): void {
    this.ws.mergeCells(`A${rowIdx}:${this.lastCol}${rowIdx}`);
  }

  get currentRow(): number {
    return this.row;
  }

  blank(height = 6): void {
    this.ws.getRow(this.row).height = height;
    this.row += 1;
  }

  titleBand(title: string, subtitle: string): void {
    const titleRow = this.ws.getRow(this.row);
    titleRow.height = 26;
    this.span(this.row);
    const titleCell = titleRow.getCell(1);
    titleCell.value = title;
    titleCell.font = { name: FONT, size: 14, bold: true, color: { argb: REPORT_COLORS.titleText } };
    titleCell.alignment = { vertical: "middle", horizontal: "left", wrapText: true, indent: 1 };
    titleCell.border = {
      bottom: { style: "thin", color: { argb: REPORT_COLORS.accent } },
    };
    this.row += 1;

    const subRow = this.ws.getRow(this.row);
    subRow.height = 32;
    this.span(this.row);
    const subCell = subRow.getCell(1);
    subCell.value = subtitle;
    subCell.font = { name: FONT, size: 10, color: { argb: REPORT_COLORS.subtitleText } };
    subCell.alignment = { vertical: "top", horizontal: "left", wrapText: true, indent: 1 };
    this.row += 1;
    this.blank(4);
  }

  sectionHeader(title: string): void {
    const r = this.ws.getRow(this.row);
    r.height = 24;
    this.span(this.row);
    const cell = r.getCell(1);
    cell.value = title;
    cell.font = { name: FONT, size: 11, bold: true, color: { argb: REPORT_COLORS.sectionText } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: REPORT_COLORS.sectionBg } };
    cell.alignment = { vertical: "middle", horizontal: "left", wrapText: true, indent: 1 };
    cell.border = thinBorder;
    this.row += 1;
  }

  synthesisTableHeader(headers: string[]): void {
    const r = this.ws.getRow(this.row);
    r.height = 24;
    headers.forEach((header, idx) => {
      const cell = r.getCell(idx + 1);
      cell.value = header;
      cell.font = { name: FONT, size: 10, bold: true, color: { argb: REPORT_COLORS.headerText } };
      cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: REPORT_COLORS.headerBg } };
      cell.alignment = {
        vertical: "middle",
        horizontal: "left",
        wrapText: true,
        indent: 1,
      };
      cell.border = thinBorder;
    });
    this.row += 1;
  }

  synthesisTableRow(
    domaine: string,
    indicateur: string,
    value: CellValue,
    status?: StatusKind,
  ): void {
    const r = this.ws.getRow(this.row);
    r.height = 24;

    const domaineCell = r.getCell(1);
    domaineCell.value = domaine;
    domaineCell.font = { name: FONT, size: 10, bold: true, color: { argb: REPORT_COLORS.label } };
    domaineCell.alignment = { vertical: "middle", horizontal: "left", wrapText: true, indent: 1 };
    domaineCell.border = thinBorder;

    const indicateurCell = r.getCell(2);
    indicateurCell.value = indicateur;
    indicateurCell.font = { name: FONT, size: 10, color: { argb: REPORT_COLORS.label } };
    indicateurCell.alignment = { vertical: "middle", horizontal: "left", wrapText: true, indent: 1 };
    indicateurCell.border = thinBorder;

    const valueCell = r.getCell(3);
    applyValue(valueCell, value);
    valueCell.font = { name: FONT, size: 10, bold: true, color: { argb: REPORT_COLORS.label } };
    valueCell.alignment = { vertical: "middle", horizontal: "right", wrapText: true, indent: 1 };
    valueCell.border = thinBorder;

    const statusCell = r.getCell(4);
    if (status) {
      applyStatusCell(statusCell, status);
    }
    statusCell.border = thinBorder;
    this.row += 1;
  }

  kpi(label: string, value: CellValue, status?: StatusKind): void {
    const r = this.ws.getRow(this.row);
    r.height = 22;

    const labelCell = r.getCell(1);
    labelCell.value = label;
    labelCell.font = { name: FONT, size: 10, color: { argb: REPORT_COLORS.label } };
    labelCell.alignment = { vertical: "middle", horizontal: "left", wrapText: true, indent: 1 };
    labelCell.border = thinBorder;

    const valueCell = r.getCell(2);
    applyValue(valueCell, value);
    valueCell.font = { name: FONT, size: 10, bold: true, color: { argb: REPORT_COLORS.label } };
    valueCell.alignment = { vertical: "middle", horizontal: "right", wrapText: true, indent: 1 };
    valueCell.border = thinBorder;

    const statusCell = r.getCell(3);
    if (status) {
      applyStatusCell(statusCell, status);
    }
    statusCell.border = thinBorder;
    this.row += 1;
  }

  tableHeader(headers: string[]): void {
    const r = this.ws.getRow(this.row);
    r.height = 24;
    headers.forEach((header, idx) => {
      const cell = r.getCell(idx + 1);
      cell.value = header;
      cell.font = { name: FONT, size: 10, bold: true, color: { argb: REPORT_COLORS.headerText } };
      cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: REPORT_COLORS.headerBg } };
      cell.alignment = {
        vertical: "middle",
        horizontal: idx === 0 ? "left" : "right",
        wrapText: true,
        indent: idx === 0 ? 1 : 1,
      };
      cell.border = thinBorder;
    });
    this.row += 1;
  }

  tableRow(cells: CellValue[], index: number, options?: { bold?: boolean }): void {
    void index;
    const r = this.ws.getRow(this.row);
    r.height = 22;
    cells.forEach((value, idx) => {
      const cell = r.getCell(idx + 1);
      applyValue(cell, value);
      cell.font = {
        name: FONT,
        size: 10,
        bold: options?.bold ?? false,
        color: { argb: REPORT_COLORS.label },
      };
      cell.alignment = {
        vertical: "middle",
        horizontal: idx === 0 ? "left" : "right",
        wrapText: true,
        indent: 1,
      };
      cell.border = thinBorder;
    });
    this.row += 1;
  }

  note(content: string): void {
    const r = this.ws.getRow(this.row);
    r.height = 36;
    this.span(this.row);
    const cell = r.getCell(1);
    cell.value = content;
    cell.font = { name: FONT, size: 9, italic: true, color: { argb: REPORT_COLORS.muted } };
    cell.alignment = { vertical: "top", horizontal: "left", wrapText: true, indent: 1 };
    this.row += 1;
  }
}

export async function loadExcelJS(): Promise<typeof ExcelJS> {
  return (await import("exceljs")).default;
}
