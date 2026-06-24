# User

**Fusion domain:** `staff` (new, TBD)
**PHI:** no — internal user/staff directory.
**Spec section:** Resource 15 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| id | integer | unique identifier |
| userName | string | unique username |
| prefix | string | |
| firstName | string | |
| middleName | string | |
| lastName | string | |
| suffix | string | |
| designation | string | |
| email | string | |
| phone | string | |
| mobile | string | |
| defaultLocationId | integer | |
| address | Address | addressLine1/2, city, state, zipCode |

## Endpoints

### `GET /v1.0/users/{id}` — get user by id
- **Path params:** `id` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — User object
- **Notes:** spec documents only the single-user GET — no list endpoint.

## Fusion mapping

- Target table(s): `staff.user` (new domain, TBD).
- Ingestion strategy: on-demand; also referenced via `providers.userDetailId`.
- Open questions:
  - No list endpoint — do we bootstrap the user list by iterating `userDetailId`s returned from provider detail?
