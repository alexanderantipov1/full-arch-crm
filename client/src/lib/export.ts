import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import Papa from "papaparse";

const PRACTICE_NAME = "GoldenStateDental";

function dateSuffix(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

function buildFilename(reportType: string, ext: "csv" | "pdf"): string {
  return `${PRACTICE_NAME}_${reportType}_${dateSuffix()}.${ext}`;
}

// ─── CSV export ───────────────────────────────────────────────────────────────
export function exportToCSV(
  data: Record<string, unknown>[],
  reportType: string,
): void {
  const csv = Papa.unparse(data);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = buildFilename(reportType, "csv");
  a.click();
  URL.revokeObjectURL(url);
}

// ─── PDF section types ────────────────────────────────────────────────────────
export interface PDFTitleSection {
  type: "title";
  title: string;
  subtitle?: string;
  showLogo?: boolean;
}

export interface PDFKPISection {
  type: "kpis";
  heading: string;
  items: { label: string; value: string }[];
}

export interface PDFTableSection {
  type: "table";
  heading: string;
  columns: string[];
  rows: (string | number)[][];
}

export type PDFSection = PDFTitleSection | PDFKPISection | PDFTableSection;

// ─── PDF export ───────────────────────────────────────────────────────────────
export function exportToPDF(sections: PDFSection[], reportType: string): void {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "letter" });
  const pageW = doc.internal.pageSize.getWidth();
  const margin = 14;
  let y = margin;

  // Header bar
  doc.setFillColor(37, 99, 235);
  doc.rect(0, 0, pageW, 14, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(9);
  doc.setFont("helvetica", "bold");
  doc.text(PRACTICE_NAME, margin, 9);
  doc.setFont("helvetica", "normal");
  doc.text(`Generated ${new Date().toLocaleDateString()}`, pageW - margin, 9, { align: "right" });
  y = 22;

  for (const section of sections) {
    if (section.type === "title") {
      // Optional logo placeholder
      if (section.showLogo) {
        doc.setFillColor(248, 250, 252);
        doc.setDrawColor(203, 213, 225);
        doc.roundedRect(margin, y, 40, 16, 2, 2, "FD");
        doc.setFontSize(7);
        doc.setFont("helvetica", "normal");
        doc.setTextColor(148, 163, 184);
        doc.text("[ PRACTICE LOGO ]", margin + 20, y + 9, { align: "center" });
        y += 20;
      }
      doc.setTextColor(15, 23, 42);
      doc.setFontSize(18);
      doc.setFont("helvetica", "bold");
      doc.text(section.title, margin, y);
      y += 7;
      if (section.subtitle) {
        doc.setFontSize(10);
        doc.setFont("helvetica", "normal");
        doc.setTextColor(100, 116, 139);
        doc.text(section.subtitle, margin, y);
        y += 6;
      }
      y += 4;
    } else if (section.type === "kpis") {
      doc.setFontSize(11);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(15, 23, 42);
      doc.text(section.heading, margin, y);
      y += 5;

      const colW = (pageW - margin * 2) / 3;
      let col = 0;
      let rowY = y;

      for (const item of section.items) {
        const x = margin + col * colW;
        doc.setFillColor(248, 250, 252);
        doc.roundedRect(x, rowY, colW - 3, 14, 2, 2, "F");
        doc.setFontSize(7);
        doc.setFont("helvetica", "normal");
        doc.setTextColor(100, 116, 139);
        doc.text(item.label, x + 4, rowY + 5);
        doc.setFontSize(11);
        doc.setFont("helvetica", "bold");
        doc.setTextColor(15, 23, 42);
        doc.text(item.value, x + 4, rowY + 11);
        col++;
        if (col === 3) {
          col = 0;
          rowY += 17;
        }
      }
      y = rowY + (col > 0 ? 17 : 0) + 6;
    } else if (section.type === "table") {
      doc.setFontSize(11);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(15, 23, 42);
      doc.text(section.heading, margin, y);
      y += 3;

      autoTable(doc, {
        startY: y,
        head: [section.columns],
        body: section.rows,
        margin: { left: margin, right: margin },
        styles: { fontSize: 8, cellPadding: 2.5 },
        headStyles: { fillColor: [37, 99, 235], textColor: 255, fontStyle: "bold" },
        alternateRowStyles: { fillColor: [248, 250, 252] },
        didDrawPage: (data) => {
          y = data.cursor?.y ?? y;
        },
      });
      y = (doc as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 8;
    }
  }

  // Footer
  const pageCount = doc.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(148, 163, 184);
    doc.text(
      `${PRACTICE_NAME} — Confidential — Page ${i} of ${pageCount}`,
      pageW / 2,
      doc.internal.pageSize.getHeight() - 8,
      { align: "center" },
    );
  }

  doc.save(buildFilename(reportType, "pdf"));
}
