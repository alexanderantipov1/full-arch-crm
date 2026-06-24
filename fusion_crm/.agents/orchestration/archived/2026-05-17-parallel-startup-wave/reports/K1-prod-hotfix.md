# K1 — Production Salesforce callback hotfix

## Scope

- Targeted Cloud Run production mutation approved by the user.
- No code deploy, no image rebuild, no secret change, no database mutation.
- Goal: stop Salesforce OAuth from redirecting back to localhost by setting
  the runtime callback URL env var on `fusion-api`.

## Actions

1. Ran targeted env update:

```text
gcloud run services update fusion-api \
  --project=fusioncrm-494201 \
  --region=us-west1 \
  --update-env-vars=SALESFORCE_CALLBACK_URL=https://fusioncrm.app/api/integrations/salesforce/callback \
  --quiet
```

2. Cloud Run initially kept traffic on the manually pinned old revision
   `fusion-api-00052-xb7`, so the env-only update did not affect live
   traffic.

3. Created a uniquely named revision with the same env update:

```text
gcloud run services update fusion-api \
  --project=fusioncrm-494201 \
  --region=us-west1 \
  --revision-suffix=sfcb-0016 \
  --update-env-vars=SALESFORCE_CALLBACK_URL=https://fusioncrm.app/api/integrations/salesforce/callback \
  --quiet
```

4. Verified `fusion-api-sfcb-0016` contains:

```text
SALESFORCE_CALLBACK_URL=https://fusioncrm.app/api/integrations/salesforce/callback
```

5. Shifted traffic:

```text
gcloud run services update-traffic fusion-api \
  --project=fusioncrm-494201 \
  --region=us-west1 \
  --to-revisions=fusion-api-sfcb-0016=100 \
  --quiet
```

## Verification

- `fusion-api-sfcb-0016` is now latest created + latest ready revision.
- `fusion-api-sfcb-0016` serves 100% traffic.
- Startup logs are clean.
- Direct Cloud Run proxy check:

```text
GET  /integrations -> 200
POST /integrations/salesforce/connect/start -> 200
```

- The returned Salesforce authorize URL now contains:

```text
redirect_uri=https%3A%2F%2Ffusioncrm.app%2Fapi%2Fintegrations%2Fsalesforce%2Fcallback
```

## Notes

- Local CLI IAP smoke with the deployer service account could not run
  because the active user lacks `serviceAccountTokenCreator` on
  `cloud-build-deployer-sa`.
- Full browser OAuth completion still needs an operator click through
  Salesforce consent, but the previously broken start URL no longer
  contains localhost.
