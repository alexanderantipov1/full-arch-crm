# Revenue Intelligence Analytics Platform

## Mission Specification for Agents

Version: 1.0
Status: Approved for Implementation
Priority: High
Scope: Executive Analytics, Revenue Intelligence, Funnel Intelligence, Staff Performance Analytics

---

# Overview

This document defines the complete analytics and business intelligence layer for the Dental Clinic Operating System.

The objective is to build a unified Revenue Intelligence Platform that tracks the entire lifecycle of every patient from advertising spend to collected revenue.

The system must provide visibility into:

* marketing effectiveness
* sales effectiveness
* coordinator effectiveness
* doctor effectiveness
* operational bottlenecks
* patient conversion flow
* revenue attribution
* ROI by campaign and employee

The platform should function as a business operating system rather than a traditional CRM reporting module.

---

# Business Objective

Leadership must be able to answer the following questions instantly:

1. Which campaigns generate the most revenue?
2. Which vendor delivers the highest ROI?
3. Which caller schedules the most consultations?
4. Which coordinator converts the most consultations into surgeries?
5. Which doctor generates the most production and revenue?
6. Where are patients being lost?
7. What is the true cost of each funnel stage?
8. What is the revenue contribution of every employee?
9. Which bottlenecks are limiting growth?
10. Where should additional advertising budget be invested?

---

# Business Funnel

The analytics platform must support the following business flow:

```text
Facebook / Google
        ↓
Vendor / Marketing Manager
        ↓
Lead Created (Salesforce)
        ↓
Caller Assigned
        ↓
Lead Contacted
        ↓
Consultation Scheduled
        ↓
Coordinator Assigned
        ↓
Consultation Show
        ↓
Doctor Assigned
        ↓
Treatment Plan Presented
        ↓
Treatment Accepted
        ↓
Surgery Scheduled
        ↓
Surgery Completed
        ↓
Payments Collected
        ↓
Revenue
```

Every patient must be traceable through the entire journey.

---

# Data Sources

## Advertising Platforms

Facebook Ads

Available:

* Spend
* Campaign
* Ad Set
* Ad
* Impressions
* Clicks
* Leads

Google Ads

Available:

* Spend
* Campaign
* Ad Group
* Keywords
* Clicks
* Conversions
* Leads

---

## Salesforce

Available entities:

* Lead
* Contact
* Opportunity
* Task
* Event

Available business fields:

* Lead Owner (Caller)
* Opportunity Owner (Coordinator)
* UTM Fields
* Campaign Information
* Source Information
* Appointment Information
* Financing Information
* Treatment Plan Amount
* Opportunity Stages

---

## CareStack

Available entities:

* Patients
* Appointments
* Treatment Plans
* Treatment Procedures
* Providers
* Invoices
* Payments
* Production Types

---

# Analytics Navigation Structure

Create a new application section:

```text
Analytics
├── Executive Overview
├── Funnel Analytics
├── Marketing Performance
├── Vendor Performance
├── Caller Performance
├── Coordinator Performance
├── Doctor Performance
├── Revenue Intelligence
├── Cost Intelligence
├── Patient Journey Analytics
├── Bottleneck Detection
├── Attribution Analytics
├── Cohort Analytics
└── Revenue Influence Matrix
```

---

# Page 1 — Executive Overview

## Purpose

Single-screen executive dashboard.

This page should be optimized for owners and executives.

---

## Revenue Widgets

Display:

* Revenue Today
* Revenue Yesterday
* Revenue Last 7 Days
* Revenue Last 30 Days
* Revenue Month To Date
* Revenue Quarter To Date
* Revenue Year To Date

---

## Funnel Widgets

Display:

* Leads
* Reached
* Consultations Scheduled
* Shows
* Treatment Plans Presented
* Treatment Accepted
* Surgeries Scheduled
* Surgeries Completed

---

## Cost Metrics

Display:

* Cost Per Lead
* Cost Per Consultation
* Cost Per Show
* Cost Per Surgery
* Cost Per Revenue Dollar

---

## Conversion Metrics

Display:

* Lead → Contact
* Contact → Consultation
* Consultation → Show
* Show → Surgery
* Surgery → Revenue

---

## ROI

Display:

* Marketing Spend
* Revenue
* ROI Multiple

---

# Page 2 — Funnel Analytics

## Purpose

Analyze the full patient funnel.

---

Visual Funnel:

```text
Leads
↓
Reached
↓
Consult Scheduled
↓
Show
↓
Treatment Presented
↓
Treatment Accepted
↓
Surgery Scheduled
↓
Surgery Completed
↓
Revenue
```

For every stage display:

* Total Count
* Conversion %
* Cost
* Revenue Generated

---

# Page 3 — Marketing Performance

## Purpose

Measure actual business impact of marketing.

---

Breakdowns:

### Campaign

Display:

* Spend
* Leads
* Consultations
* Shows
* Surgeries
* Revenue
* ROI

### Ad Set

Same metrics.

### Ad

Same metrics.

### Source

Display:

* Facebook
* Google
* Organic
* Referral
* Direct
* CallRail

---

# Page 4 — Vendor Performance

## Purpose

Measure marketing vendor effectiveness.

---

Group By:

Vendor

Display:

* Spend Managed
* Leads Generated
* Consultations
* Shows
* Surgeries
* Revenue
* ROI

Ranking Table Required.

---

# Page 5 — Caller Performance

## Purpose

Measure caller effectiveness.

---

Group By:

Caller

Display:

* Leads Assigned
* Calls Made
* Leads Reached
* Consultations Booked

Conversions:

* Lead → Contact
* Lead → Consultation

Revenue Metrics:

* Revenue Influenced
* Revenue Per Lead
* Revenue Per Consultation

---

# Page 6 — Coordinator Performance

## Purpose

Measure treatment coordinator effectiveness.

---

Group By:

Coordinator

Display:

* Consultations Assigned
* Shows
* Treatment Plans Presented
* Surgeries Scheduled
* Surgeries Completed
* Revenue Generated

Conversions:

* Scheduled → Show
* Show → Surgery
* Show → Revenue

Ranking Table Required.

---

# Page 7 — Doctor Performance

## Purpose

Measure doctor effectiveness.

---

Group By:

Doctor

Display:

* Consultations
* Treatment Plans
* Accepted Cases
* Surgeries
* Revenue

Conversions:

* Consultation → Accepted
* Accepted → Surgery

Revenue Metrics:

* Revenue Per Consultation
* Revenue Per Surgery

---

# Page 8 — Revenue Intelligence

## Purpose

Understand revenue generation.

---

Revenue By:

* Campaign
* Source
* Vendor
* Caller
* Coordinator
* Doctor
* Location

Display:

* Gross Revenue
* Collected Revenue
* Outstanding Balance
* Average Case Value

---

# Page 9 — Cost Intelligence

## Purpose

Understand actual business costs.

---

Marketing Costs:

* Cost Per Lead
* Cost Per Consultation
* Cost Per Show
* Cost Per Surgery

Operational Costs:

* Cost Per Caller Conversion
* Cost Per Coordinator Conversion
* Cost Per Revenue Dollar

---

# Page 10 — Patient Journey Analytics

## Purpose

Full patient timeline.

---

Timeline:

```text
Lead Created
↓
Caller Assigned
↓
Consult Scheduled
↓
Coordinator Assigned
↓
Show
↓
Doctor Assigned
↓
Treatment Accepted
↓
Surgery
↓
Payments
```

Display:

* Timestamp
* Responsible Employee
* Campaign
* Source
* Revenue

---

# Page 11 — Bottleneck Detection

## Purpose

Automatically identify revenue leaks.

---

Examples:

* Campaign generates leads but poor shows
* Coordinator has poor surgery conversion
* Doctor has poor acceptance rate
* Caller has poor booking rate

For every issue display:

* Description
* Estimated Revenue Loss
* Severity
* Suggested Action

---

# Page 12 — Attribution Analytics

## Purpose

Revenue attribution analysis.

---

For every completed case store:

```text
Campaign
Vendor
Caller
Coordinator
Doctor
Revenue
```

Build reports:

Revenue By:

* Campaign
* Vendor
* Caller
* Coordinator
* Doctor

---

# Page 13 — Cohort Analytics

## Purpose

Measure long-term lead value.

---

Group by Lead Creation Month.

Example:

January Leads

Display:

* Revenue after 30 Days
* Revenue after 60 Days
* Revenue after 90 Days
* Revenue after 180 Days
* Revenue after 365 Days

---

# Page 14 — Revenue Influence Matrix

## Purpose

Show contribution of every employee.

---

Display:

| Employee    | Role        | Revenue Influenced |
| ----------- | ----------- | ------------------ |
| Tomas       | Vendor      | $4,800,000         |
| Sofia       | Caller      | $3,900,000         |
| Anna        | Coordinator | $2,700,000         |
| Dr. Antipov | Doctor      | $5,200,000         |

---

# Global Filters

Every analytics page must support:

* Date Range
* Location
* Campaign
* Source
* Vendor
* Caller
* Coordinator
* Doctor

---

# Supported Time Ranges

* Today
* Yesterday
* Last 7 Days
* Last 30 Days
* Last 90 Days
* This Month
* This Quarter
* This Year
* Custom Range

---

# Required Analytics Fact Table

Create:

## fact_patient_journey

One row per patient.

Fields:

```sql
person_uid

campaign_id
campaign_name

source

vendor_id

caller_id

coordinator_id

doctor_id

lead_date

first_contact_date

consult_scheduled_date

show_date

treatment_presented_date

treatment_accepted_date

surgery_scheduled_date

surgery_completed_date

first_payment_date

revenue_amount

collected_amount

marketing_cost_allocated
```

---

# Required Derived Metrics

Automatically calculate:

```text
Lead Cost

Marketing Spend / Leads
```

```text
Consult Cost

Marketing Spend / Consultations
```

```text
Show Cost

Marketing Spend / Shows
```

```text
Surgery Cost

Marketing Spend / Surgeries
```

```text
Revenue Per Lead

Revenue / Leads
```

```text
Revenue Per Show

Revenue / Shows
```

```text
ROI

Revenue / Spend
```

---

# Technical Requirements

The system must:

* support millions of records
* support drill-down from dashboard to patient
* support cross-filtering
* support export to CSV
* support export to Excel
* support future AI-generated insights

---

# Future AI Analytics Layer

The architecture should support future AI functionality:

Examples:

* identify bottlenecks automatically
* identify high-performing campaigns
* identify underperforming coordinators
* predict no-shows
* predict treatment acceptance probability
* recommend budget allocation

---

# Success Criteria

The project is complete when leadership can:

* understand revenue generation end-to-end
* identify bottlenecks instantly
* evaluate employee performance objectively
* understand true acquisition costs
* understand ROI by campaign
* understand ROI by employee
* understand ROI by location
* understand patient conversion behavior

The final result should function as a complete Revenue Intelligence Platform and executive operating system for the clinic.
