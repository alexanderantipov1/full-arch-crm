# A2 Codex Follow-up: IAP Smoke Evidence

## Scope

Codex performed a read-only follow-up after `A2-live` because the Claude harness could not run `gcloud compute backend-services describe`.

No production mutations were performed.

## Commands

- `gcloud compute backend-services list --project=fusioncrm-494201 --format='table(name,protocol,loadBalancingScheme)'`
- `gcloud compute backend-services describe fusion-lb-backend-api --global --project=fusioncrm-494201 --format=json`
- `gcloud iap web get-iam-policy --project=fusioncrm-494201 --resource-type=backend-services --service=fusion-lb-backend-api --format=json`
- `gcloud auth print-identity-token --help | rg -n "include-email|audiences|impersonate" -C 3`

## Findings

- Backend service `fusion-lb-backend-api` has IAP enabled.
- Backend service IAP OAuth client ID is `800777477533-fv4l6nd3ou3c9euvr7re52rfcp680ess.apps.googleusercontent.com`.
- That OAuth client ID matches the pinned workflow `IAP_CLIENT_ID`.
- IAP IAM policy grants `roles/iap.httpsResourceAccessor` to `serviceAccount:cloud-build-deployer-sa@fusioncrm-494201.iam.gserviceaccount.com`.
- Therefore the earlier likely causes "wrong IAP client ID" and "deployer service account lacks IAP accessor" are not supported by current evidence.

## Strong Next Hypothesis

The smoke token is generated without an email claim:

```bash
gcloud auth print-identity-token \
  --impersonate-service-account="${DEPLOYER_SA}" \
  --audiences="${IAP_AUDIENCE}"
```

Google Cloud IAP documentation says a generated service-account OIDC token must have an `email` claim for IAP to accept it. Local `gcloud auth print-identity-token --help` says `--include-email` adds `email` and `email_verified` claims and is intended for service-account impersonation.

Next candidate fix:

```bash
gcloud auth print-identity-token \
  --impersonate-service-account="${DEPLOYER_SA}" \
  --audiences="${IAP_AUDIENCE}" \
  --include-email
```

## References

- Google Cloud IAP programmatic authentication: service-account OIDC token must include an `email` claim.
- Google Cloud SDK `gcloud auth print-identity-token`: `--include-email` includes `email` and `email_verified` claims for impersonated service accounts.

## Recommendation

Run a single-owner workflow patch in the deploy track:

1. Keep the A1 stderr diagnostics fix.
2. Add `--include-email` to the deploy-prod deep-smoke token command.
3. Add or update a static workflow test that asserts the token command uses both `--audiences="${IAP_AUDIENCE}"` and `--include-email`.
4. Do not rerun deploy-prod or move ENG-178/ENG-180 statuses without explicit user approval.
