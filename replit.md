# Full Arch CRM - HIPAA-Compliant Patient CRM for Dental Implant Practices

## Overview
Full Arch CRM is a comprehensive practice management system specifically designed for dental implant practices. Its primary purpose is to streamline and optimize the complex process of medical billing for high-value full arch dental implant procedures (All-on-4, All-on-6). The platform aims to maximize practice revenue through intelligent coding, AI-powered appeals, and robust patient management, ensuring HIPAA compliance and enhancing operational efficiency for dental practices.

## User Preferences
- Focus on medical billing workflow for full arch implants
- All-on-4 and All-on-6 are the primary procedures
- AI assistance for insurance approvals, appeals, and coding
- Medical necessity documentation is key to getting claims approved
- Professional, clinical appearance

## System Architecture
The system is built with a modern web stack: React with TypeScript, Vite, TailwindCSS, and Shadcn/UI for the frontend, and Express.js with TypeScript for the backend. PostgreSQL with Drizzle ORM is used for data persistence, and Replit Auth handles authentication. AI capabilities are powered by OpenAI GPT-5.2 via Replit AI Integrations.

Key architectural decisions and features include:
- **HIPAA Compliance**: Implemented through comprehensive audit logging for PHI access, 15-minute inactivity session timeouts, and secure handling of sensitive patient data.
- **AI-Powered Automation**: Integrates AI for critical functions such as:
    - Intelligent Coding Engine: Cross-coding CDT to CPT/ICD-10 with high accuracy.
    - Smart Appeals Engine: AI-generated appeals and denial analysis.
    - AI Documentation Engine: Generation of medical necessity letters, operative reports, and progress notes.
    - Predictive Analytics: Collection forecasting and at-risk claim identification.
    - AI Phone Agent, Smart Scheduling, and Fee Optimizer for operational enhancements.
- **Modular Design**: The system is designed with distinct modules for various dental specialties and operational functions (e.g., Periodontal Charting, Orthodontics Tracker, Endodontics, Oral Surgery, Multi-Location Support, 2-Way Patient Communication).
- **Patient Workflow Management**: Comprehensive features for patient intake, treatment planning, digital consent forms, appointment scheduling, and patient document management.
- **Revenue Cycle Management**: Tools for insurance verification, claims management, ERA processing, payment tracking, and financial analytics.
- **User Interface**: A professional, clinical design theme featuring a primary clinical blue and accent teal/green for success states, with support for light/dark modes.
- **Specialty Onboarding & AI Personalization**: Onboarding flow customizes user experience based on dental specialty, leveraging AI to recommend relevant modules.

## External Dependencies
- **Database**: PostgreSQL
- **ORM**: Drizzle ORM
- **Authentication**: Replit Auth (OIDC)
- **AI Services**: OpenAI GPT-5.2 via Replit AI Integrations