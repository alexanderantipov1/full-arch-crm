// Payments data-flow documentation — the canonical staff-facing explanation
// of how CareStack payment data reaches the Payments page, how we classify it,
// and what each derived metric means.
//
// DOC-SYNC RULE (ENG-300): this content is the human-readable mirror of the
// payment CLASSIFICATION and the Collected FORMULA. If you change either:
//   - `_PAYMENT_CODE_TO_KIND` / `_CASH_REVERSAL_CODES` in
//     `packages/ingest/carestack_accounting_transaction_service.py`, or
//   - the Collected aggregate in
//     `packages/interaction/repository.py::get_treatment_payment_aggregate`,
// you MUST update this file — BOTH `paymentsDocEn` and `paymentsDocRu` — in the
// same change. EN and RU must always describe the same behaviour. See
// `apps/web/CLAUDE.md` and `packages/ingest/CLAUDE.md`.

export type DocTable = {
  headers: string[];
  rows: string[][];
};

export type DocSection = {
  heading: string;
  paragraphs?: string[];
  bullets?: string[];
  table?: DocTable;
  formula?: string;
};

export type PaymentsDocContent = {
  title: string;
  subtitle: string;
  sections: DocSection[];
  maintenanceNote: string;
};

export type DocLanguage = "en" | "ru";

export const paymentsDocEn: PaymentsDocContent = {
  title: "Payments data — what we receive and how we count it",
  subtitle:
    "How CareStack billing data flows onto this page, what each transaction means, how we classify it, and how every metric is derived.",
  sections: [
    {
      heading: "1. Where the data comes from",
      paragraphs: [
        "Every figure on the Payments page originates from one CareStack feed: GET /sync/accounting-transactions. This is a double-entry accounting ledger, not a list of receipts.",
        "Double-entry means a single real payment is recorded as TWO ledger rows. When a patient pays $500, CareStack writes one CREDIT row (\"money received\") AND one DEBIT row (\"that money applied to an invoice\"). Both describe the same $500 — counting both would double the cash.",
        "We capture each ledger row verbatim into ingest.raw_event before doing anything with it (capture-then-route). That stored row is exactly the JSON you see when you click \"View raw\" on a payment — the original document, unmodified.",
      ],
    },
    {
      heading: "2. The fields we read on each row",
      bullets: [
        "transactionCode — what kind of ledger movement this is (the single most important field; classification is driven by it).",
        "folioType / transactionType — the accounting bucket and debit/credit direction.",
        "amount — the money on this ledger row.",
        "isReversed — true when this row was voided/reversed.",
        "locationId — which clinic location the movement belongs to (attached to the event so the page/dashboard can filter by location).",
        "patientId — used only to resolve the person (never shown as clinical data).",
        "invoiceId — the invoice the movement relates to.",
      ],
    },
    {
      heading: "3. How we classify each transaction",
      paragraphs: [
        "We classify strictly by transactionCode against an allow-list. Anything not on the list produces NO payment event — it is kept as a raw row only (charges, adjustments, fee changes, unknown codes). This strictness is deliberate: it prevents non-cash ledger movements from leaking into the money totals.",
      ],
      table: {
        headers: ["transactionCode", "What it means", "Our event kind", "Counts in Collected?"],
        rows: [
          [
            "PATIENTPAYMENTS, INSURANCEPAYMENTS",
            "Real money received from a payer (patient or insurance paid).",
            "payment_recorded",
            "Yes — this is cash in.",
          ],
          [
            "PATPAYMENTAPPLIED, INSPAYMENTAPPLIED",
            "The offset leg of double-entry — recorded money allocated onto an invoice. Not new cash.",
            "payment_applied",
            "No — excluded (would double-count).",
          ],
          [
            "PATIENTPAYMENTSDELETE, REFUND, PATIENTREFUND, INSURANCEREFUND",
            "A previously received payment was reversed / deleted / refunded.",
            "payment_reversed / payment_refunded",
            "Subtracted from Collected.",
          ],
          [
            "PROCEDURECOMPLETED, PATIENTADJUSTMENT, FEEUPDATION, anything else",
            "Billing or adjustment movement — not a payment.",
            "none (raw row only)",
            "Not counted.",
          ],
        ],
      },
    },
    {
      heading: "4. The isReversed rule",
      paragraphs: [
        "isReversed = true flips a row to \"reversed\" ONLY when its transactionCode is a real cash code (a recorded payment or a refund). It never turns an allocation leg or a charge/adjustment into a payment event.",
        "This restriction matters: a reversed allocation (PATPAYMENTAPPLIED with isReversed) is still just an allocation and stays excluded from Collected. Without this rule, reversed allocation legs would land in payment_reversed and subtract cash that the matching delete row already removed — which is exactly what once drove the Collected total negative.",
      ],
    },
    {
      heading: "5. What each metric means",
      bullets: [
        "Collected — real cash received, net of refunds and reversals. payment_applied is never part of it.",
        "Payments (count) — the number of payment_recorded events (real incoming payments).",
        "Outstanding — the sum of each patient's latest balance from CareStack's payment-summary (patient + insurance balance due). It is a point-in-time, tenant-wide number — it is NOT scoped by the date window or the location filter.",
        "AR-risk — patients whose latest balance is above $500.",
      ],
      formula: "Collected = Σ payment_recorded − Σ (payment_refunded + payment_reversed)",
    },
    {
      heading: "6. How and when we ingest it",
      bullets: [
        "Capture-then-route — the raw ledger row is stored first, then classified. We can always replay from the raw row if classification changes.",
        "Idempotent — re-pulling the same data does not create duplicate payment events.",
        "Location-aware — the clinic location is attached to the event when it is emitted, resolved from the row's locationId.",
        "Real-time — an incremental cron pulls recent transactions on a schedule (production ~ every 30 minutes, capped at a small page so we never hammer CareStack).",
        "Backfill — historical years are loaded by a separate, throttled operator-run backfill, kept gentle on purpose (CareStack rate-limits aggressively).",
      ],
    },
    {
      heading: "7. How filters apply",
      paragraphs: [
        "Leads, consultations, payments and treatment metrics all honour the page's date window and the location filter — so when you change the location, those numbers change with it.",
        "Outstanding and AR-risk are deliberately tenant-wide and point-in-time (today's balances), because a balance is a snapshot, not something that belongs to a date window or a single location.",
      ],
    },
    {
      heading: "8. Why we do it this way",
      paragraphs: [
        "Because the feed is double-entry, the naive approach — counting every row, or grouping by folio — inflates the money roughly 3.3× and, once reversed allocation legs are mixed in, can even drive Collected negative.",
        "Classifying strictly by transactionCode and counting only real cash received (net of refunds/reversals) is what makes the Collected total trustworthy.",
      ],
    },
  ],
  maintenanceNote:
    "Keep this document in sync with the code. If the payment classification (_PAYMENT_CODE_TO_KIND) or the Collected formula (get_treatment_payment_aggregate) changes, update this page — both the English and the Russian version — in the same change.",
};

export const paymentsDocRu: PaymentsDocContent = {
  title: "Данные по платежам — что мы получаем и как считаем",
  subtitle:
    "Как данные биллинга CareStack попадают на эту страницу, что значит каждая транзакция, как мы её классифицируем и как считается каждая метрика.",
  sections: [
    {
      heading: "1. Откуда берутся данные",
      paragraphs: [
        "Каждая цифра на странице Payments берётся из одного фида CareStack: GET /sync/accounting-transactions. Это бухгалтерская книга двойной записи, а не список квитанций.",
        "Двойная запись означает, что один реальный платёж записывается ДВУМЯ строками. Когда пациент платит $500, CareStack создаёт одну строку КРЕДИТ («деньги получены») И одну строку ДЕБЕТ («эти деньги отнесены на счёт/инвойс»). Обе описывают одни и те же $500 — если посчитать обе, сумма удвоится.",
        "Каждую строку мы сначала сохраняем дословно в ingest.raw_event и только потом обрабатываем (capture-then-route). Именно эта сохранённая строка — тот JSON, который вы видите по кнопке «View raw»: оригинальный документ без изменений.",
      ],
    },
    {
      heading: "2. Какие поля мы читаем в каждой строке",
      bullets: [
        "transactionCode — какой это тип движения по книге (самое важное поле; именно по нему идёт классификация).",
        "folioType / transactionType — бухгалтерская корзина и направление (дебет/кредит).",
        "amount — сумма по данной строке книги.",
        "isReversed — true, если строка была отменена/сторнирована.",
        "locationId — к какой локации клиники относится движение (привязывается к событию, чтобы страница/дашборд могли фильтровать по локации).",
        "patientId — используется только чтобы определить персону (никогда не показывается как клинические данные).",
        "invoiceId — инвойс, к которому относится движение.",
      ],
    },
    {
      heading: "3. Как мы классифицируем каждую транзакцию",
      paragraphs: [
        "Мы классифицируем строго по transactionCode по белому списку. Всё, чего нет в списке, НЕ создаёт платёжного события — остаётся только сырой строкой (начисления, корректировки, изменения цен, неизвестные коды). Эта строгость намеренная: она не даёт неденежным движениям книги просочиться в денежные итоги.",
      ],
      table: {
        headers: ["transactionCode", "Что значит", "Наш тип события", "Идёт в Collected?"],
        rows: [
          [
            "PATIENTPAYMENTS, INSURANCEPAYMENTS",
            "Реально полученные деньги от плательщика (заплатил пациент или страховая).",
            "payment_recorded",
            "Да — это приход денег.",
          ],
          [
            "PATPAYMENTAPPLIED, INSPAYMENTAPPLIED",
            "Встречная нога двойной записи — полученные деньги отнесены на инвойс. Это не новые деньги.",
            "payment_applied",
            "Нет — исключается (иначе двойной счёт).",
          ],
          [
            "PATIENTPAYMENTSDELETE, REFUND, PATIENTREFUND, INSURANCEREFUND",
            "Ранее полученный платёж был сторнирован / удалён / возвращён.",
            "payment_reversed / payment_refunded",
            "Вычитается из Collected.",
          ],
          [
            "PROCEDURECOMPLETED, PATIENTADJUSTMENT, FEEUPDATION и всё остальное",
            "Начисление или корректировка — это не платёж.",
            "нет события (только сырая строка)",
            "Не считается.",
          ],
        ],
      },
    },
    {
      heading: "4. Правило isReversed",
      paragraphs: [
        "isReversed = true переводит строку в «сторнировано» ТОЛЬКО когда её transactionCode — реальный денежный код (полученный платёж или возврат). Он никогда не превращает ногу-аллокацию или начисление/корректировку в платёжное событие.",
        "Это ограничение важно: сторнированная аллокация (PATPAYMENTAPPLIED с isReversed) — всё равно просто аллокация и остаётся исключённой из Collected. Без этого правила сторнированные ноги-аллокации попадали бы в payment_reversed и вычитали бы деньги, которые соответствующая строка-удаление уже убрала, — именно это однажды и увело Collected в минус.",
      ],
    },
    {
      heading: "5. Что означает каждая метрика",
      bullets: [
        "Collected — реально полученные деньги, за вычетом возвратов и сторно. payment_applied в неё никогда не входит.",
        "Payments (count) — количество событий payment_recorded (реальные входящие платежи).",
        "Outstanding — сумма последнего баланса каждого пациента из payment-summary CareStack (задолженность пациента + страховой). Это значение на текущий момент и по всему тенанту — оно НЕ ограничивается окном дат или фильтром локации.",
        "AR-risk — пациенты, чей последний баланс превышает $500.",
      ],
      formula: "Collected = Σ payment_recorded − Σ (payment_refunded + payment_reversed)",
    },
    {
      heading: "6. Как и когда мы это получаем",
      bullets: [
        "Capture-then-route — сырая строка книги сохраняется первой, классификация идёт потом. Если логика классификации изменится, мы всегда можем переиграть из сырой строки.",
        "Идемпотентно — повторная выкачка тех же данных не создаёт дублей платёжных событий.",
        "С учётом локации — локация клиники привязывается к событию при его создании, определяется из locationId строки.",
        "Реальное время — инкрементальный cron по расписанию подтягивает свежие транзакции (в проде ~ каждые 30 минут, с ограничением на маленькую страницу, чтобы не нагружать CareStack).",
        "Backfill — исторические годы загружаются отдельным дросселированным операторским backfill, намеренно «мягким» (CareStack агрессивно ограничивает частоту запросов).",
      ],
    },
    {
      heading: "7. Как применяются фильтры",
      paragraphs: [
        "Лиды, консультации, платежи и метрики лечения учитывают окно дат страницы и фильтр локации — поэтому при смене локации эти цифры меняются вместе с ней.",
        "Outstanding и AR-risk намеренно считаются по всему тенанту и на текущий момент (сегодняшние балансы), потому что баланс — это снимок состояния, а не то, что относится к окну дат или одной локации.",
      ],
    },
    {
      heading: "8. Почему мы делаем именно так",
      paragraphs: [
        "Поскольку фид — двойная запись, наивный подход (считать все строки или группировать по folio) завышает деньги примерно в 3.3 раза, а если подмешать сторнированные ноги-аллокации, может даже увести Collected в минус.",
        "Строгая классификация по transactionCode и подсчёт только реально полученных денег (за вычетом возвратов/сторно) — это и делает итог Collected достоверным.",
      ],
    },
  ],
  maintenanceNote:
    "Держите этот документ синхронным с кодом. Если меняется классификация платежей (_PAYMENT_CODE_TO_KIND) или формула Collected (get_treatment_payment_aggregate), обновите эту страницу — обе версии, английскую и русскую, — в том же изменении.",
};

export const paymentsDoc: Record<DocLanguage, PaymentsDocContent> = {
  en: paymentsDocEn,
  ru: paymentsDocRu,
};
