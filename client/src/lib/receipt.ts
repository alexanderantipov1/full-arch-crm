export interface ReceiptData {
  patientName: string;
  amount: number;
  currency?: string;
  date?: string;
  stripePaymentIntentId: string;
  description?: string | null;
  receiptEmail?: string | null;
  status?: string;
  testMode?: boolean;
  isSimulated?: boolean;
}

const PRACTICE_NAME = "ImplantBill AI Dental Practice";

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatCurrency(amountCents: number, currency = "usd"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amountCents / 100);
}

function formatDate(dateStr?: string): string {
  const d = dateStr ? new Date(dateStr) : new Date();
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function printPaymentReceipt(receipt: ReceiptData): void {
  const amount = escapeHtml(formatCurrency(receipt.amount, receipt.currency));
  const date = escapeHtml(formatDate(receipt.date));
  const receiptId = escapeHtml(receipt.stripePaymentIntentId);
  const patientName = escapeHtml(receipt.patientName);
  const description = escapeHtml(receipt.description || "Dental Services");
  const receiptEmail = receipt.receiptEmail ? escapeHtml(receipt.receiptEmail) : null;
  const status = escapeHtml(receipt.status || "succeeded");
  const modeLabel = receipt.isSimulated ? "SIMULATED" : receipt.testMode ? "TEST MODE" : "LIVE";
  const isTest = receipt.testMode || receipt.isSimulated;

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Payment Receipt &mdash; ${patientName}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      color: #111827;
      background: #fff;
      padding: 40px;
      max-width: 560px;
      margin: 0 auto;
    }
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-bottom: 20px;
      border-bottom: 2px solid #e5e7eb;
      margin-bottom: 28px;
    }
    .practice-name {
      font-size: 18px;
      font-weight: 700;
      color: #1e40af;
    }
    .receipt-label {
      font-size: 13px;
      font-weight: 600;
      color: #6b7280;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .amount-block {
      text-align: center;
      padding: 24px 0;
      margin-bottom: 28px;
      background: #f0fdf4;
      border-radius: 10px;
      border: 1px solid #bbf7d0;
    }
    .amount-label {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #16a34a;
      margin-bottom: 6px;
    }
    .amount-value {
      font-size: 40px;
      font-weight: 800;
      color: #15803d;
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.5px;
    }
    .details-table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 28px;
    }
    .details-table tr {
      border-bottom: 1px solid #f3f4f6;
    }
    .details-table tr:last-child {
      border-bottom: none;
    }
    .details-table td {
      padding: 10px 0;
      font-size: 13px;
      vertical-align: top;
    }
    .details-table td:first-child {
      color: #6b7280;
      font-weight: 500;
      width: 140px;
    }
    .details-table td:last-child {
      color: #111827;
      font-weight: 500;
    }
    .receipt-id {
      font-family: "SF Mono", "Fira Code", "Courier New", monospace;
      font-size: 11px;
      color: #374151;
      word-break: break-all;
    }
    .status-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 600;
      background: #dcfce7;
      color: #15803d;
      text-transform: capitalize;
    }
    .test-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 600;
      background: #fef3c7;
      color: #92400e;
      margin-left: 6px;
    }
    .footer {
      text-align: center;
      padding-top: 20px;
      border-top: 1px solid #e5e7eb;
      color: #9ca3af;
      font-size: 11px;
      line-height: 1.6;
    }
    .powered {
      margin-top: 6px;
      font-size: 10px;
      color: #d1d5db;
    }
    @media print {
      body { padding: 20px; }
      .no-print { display: none; }
    }
    .print-btn {
      display: block;
      margin: 24px auto 0;
      padding: 10px 28px;
      background: #1e40af;
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
    }
    .print-btn:hover { background: #1d4ed8; }
  </style>
</head>
<body>
  <div class="header">
    <div class="practice-name">${escapeHtml(PRACTICE_NAME)}</div>
    <div class="receipt-label">Payment Receipt</div>
  </div>

  <div class="amount-block">
    <div class="amount-label">Amount Paid</div>
    <div class="amount-value">${amount}</div>
  </div>

  <table class="details-table">
    <tr>
      <td>Patient</td>
      <td>${patientName}</td>
    </tr>
    <tr>
      <td>Date</td>
      <td>${date}</td>
    </tr>
    <tr>
      <td>Description</td>
      <td>${description}</td>
    </tr>
    <tr>
      <td>Receipt ID</td>
      <td><span class="receipt-id">${receiptId}</span></td>
    </tr>
    ${receiptEmail ? `<tr><td>Receipt Email</td><td>${receiptEmail}</td></tr>` : ""}
    <tr>
      <td>Status</td>
      <td>
        <span class="status-badge">${status}</span>
        ${isTest ? `<span class="test-badge">${escapeHtml(modeLabel)}</span>` : ""}
      </td>
    </tr>
    <tr>
      <td>Practice</td>
      <td>${escapeHtml(PRACTICE_NAME)}</td>
    </tr>
  </table>

  <div class="footer">
    <p>Thank you for your payment. Please retain this receipt for your records.</p>
    <p>Questions? Contact your dental practice directly.</p>
    <div class="powered">Processed securely via Stripe &middot; ImplantBill AI</div>
  </div>

  <button class="print-btn no-print" onclick="window.print()">Print / Save as PDF</button>
</body>
</html>`;

  const win = window.open("", "_blank", "width=680,height=820,noopener,noreferrer");
  if (!win) {
    alert("Pop-up blocked — please allow pop-ups for this site to print receipts.");
    return;
  }
  win.opener = null;
  win.document.write(html);
  win.document.close();
  win.focus();
}
