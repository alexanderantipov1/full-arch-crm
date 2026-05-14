# ImplantBill AI - HIPAA-Compliant Deployment Guide

This guide helps developers deploy the ImplantBill AI application to a HIPAA-compliant hosting environment.

## Application Overview

- **Frontend**: React + TypeScript + Vite + TailwindCSS + Shadcn/UI
- **Backend**: Express.js + TypeScript
- **Database**: PostgreSQL with Drizzle ORM
- **Authentication**: OIDC-based (currently Replit Auth, can be swapped)

## Prerequisites

Before deployment, ensure you have:
- [ ] Signed BAA with your hosting provider
- [ ] PostgreSQL database with encryption at rest
- [ ] SSL/TLS certificates for HTTPS
- [ ] Environment variables configured

## Environment Variables Required

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require

# Session
SESSION_SECRET=your-secure-random-string-min-32-chars

# Authentication (if using OIDC)
ISSUER_URL=https://your-auth-provider.com
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret

# OpenAI (for AI features)
OPENAI_API_KEY=sk-your-openai-key
```

## Deployment Options

### Option 1: AWS (Recommended for Healthcare)

#### Services Needed:
- **EC2 or ECS**: Application hosting
- **RDS PostgreSQL**: Database (enable encryption)
- **ALB**: Load balancer with SSL
- **Secrets Manager**: Store credentials

#### Steps:
1. Request AWS BAA at https://aws.amazon.com/compliance/hipaa-compliance/
2. Create VPC with private subnets
3. Launch RDS PostgreSQL with encryption enabled
4. Deploy application to EC2/ECS
5. Configure ALB with SSL certificate
6. Set up CloudWatch for logging

#### Estimated Cost: $50-200/month

### Option 2: Google Cloud Platform

#### Services Needed:
- **Cloud Run**: Container hosting
- **Cloud SQL**: PostgreSQL database
- **Cloud Load Balancing**: HTTPS termination

#### Steps:
1. Request GCP BAA at https://cloud.google.com/security/compliance/hipaa
2. Create Cloud SQL instance with encryption
3. Build Docker container and push to Container Registry
4. Deploy to Cloud Run
5. Configure custom domain with SSL

#### Estimated Cost: $50-150/month

### Option 3: Railway + Neon (Simpler Setup)

#### Steps:
1. Contact Railway for BAA (sales@railway.app)
2. Contact Neon for BAA (enterprise@neon.tech)
3. Create Neon PostgreSQL database
4. Deploy to Railway from GitHub
5. Configure environment variables

#### Estimated Cost: $20-50/month

## Build & Deploy Commands

```bash
# Install dependencies
npm install

# Build the application
npm run build

# Push database schema
npm run db:push

# Apply infrastructure migrations (run AS DB SUPERUSER, once per env).
# These live outside Drizzle because they're permission / role changes, not
# schema DDL. See infra/sql/README.md for the catalog.
psql "$DATABASE_URL" -f infra/sql/001_audit_lockdown.sql

# Start production server
npm start
```

### HIPAA-required deployment posture

For the audit lockdown migration to actually protect against tampering,
production MUST run the application as a non-superuser role (commonly
named `app_role`) that is DISTINCT from the schema owner. Local dev
with one shared owner is OK — the migration still applies, but the
runtime user trivially bypasses the REVOKE.

Recommended role setup (run once as superuser before deploying):

```sql
CREATE ROLE app_role LOGIN PASSWORD 'redacted';
GRANT CONNECT ON DATABASE your_db TO app_role;
GRANT USAGE ON SCHEMA public TO app_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_role;
-- Then apply infra/sql/001_audit_lockdown.sql to strip UPDATE/DELETE on
-- audit_logs specifically.
```

## Docker Deployment

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

EXPOSE 5000
CMD ["npm", "start"]
```

## Database Migration

The application uses Drizzle ORM. To set up the database:

```bash
# Push schema to database
npm run db:push

# (Optional) Seed with sample data
npx tsx scripts/seed.ts
```

## HIPAA Compliance Checklist

### Technical Controls:
- [ ] Data encrypted at rest (database, backups)
- [ ] Data encrypted in transit (HTTPS/TLS)
- [ ] Access logging enabled (built into app)
- [ ] Session timeout (15 minutes - built into app)
- [ ] Strong authentication
- [ ] Regular backups with encryption

### Administrative Controls:
- [ ] BAA signed with hosting provider
- [ ] BAA signed with database provider
- [ ] Staff training completed
- [ ] Security policies documented
- [ ] Incident response plan
- [ ] Risk assessment completed

### Physical Controls:
- [ ] Cloud provider has SOC 2 certification
- [ ] Data center physical security verified

## Authentication Migration

The app currently uses Replit Auth (OIDC). To switch providers:

### Option A: Auth0
1. Create Auth0 account and application
2. Update environment variables:
   ```
   ISSUER_URL=https://your-tenant.auth0.com/
   CLIENT_ID=your-auth0-client-id
   CLIENT_SECRET=your-auth0-client-secret
   ```
3. Configure callback URLs in Auth0 dashboard

### Option B: Clerk
1. Create Clerk application
2. Install Clerk SDK: `npm install @clerk/clerk-sdk-node`
3. Update authentication middleware in `server/routes.ts`

## Monitoring & Logging

The application includes:
- **Audit Logs**: All PHI access is logged (view at /audit-logs)
- **Session Management**: Auto-logout after 15 minutes inactivity

For production, add:
- Application performance monitoring (DataDog, New Relic)
- Error tracking (Sentry)
- Log aggregation (CloudWatch, Stackdriver)

## Support

For questions about the codebase:
- Review `replit.md` for architecture overview
- Check `shared/schema.ts` for database schema
- API routes are in `server/routes.ts`

## Security Notes

- Never commit secrets to version control
- Rotate credentials regularly
- Keep dependencies updated
- Review audit logs regularly
- Conduct penetration testing before production launch
