# Ambientes — Ecosistema Margay

> Fecha: 2026-06-02 · **Matriz de Supabase corregida el 2026-07-31** (ver el aviso abajo).
> Fuente de verdad del mapeo de ambientes. Si algo contradice esto, actualizá este doc.

## Modelo de ambientes

```
LOCAL (cada dev)   → hub/workspace de TEST    → Supabase TEST
TEST (deployado)   → margay-platform-test     → Supabase TEST
PROD (deployado)   → margay-platform-prod     → Supabase PROD
```

Los módulos en **local** NO corren su propio hub/workspace: consumen el de **TEST** (deployado),
que corre contra Supabase **sandbox**. Así el desarrollo nunca toca datos reales.

## Matriz de referencia

| | LOCAL | TEST | PROD |
|---|---|---|---|
| **GCP project** | (máquina del dev) | `margay-platform-test` | `margay-platform-prod` |
| **Supabase project** | Margay Platform Test | Margay Platform Test | Margay Platform Prod |
| **Supabase ref** | `zgujorkqulkdsnmjdxtj` | `zgujorkqulkdsnmjdxtj` | `sjujhroqaoggwbwiviqu` |
| **Supabase URL** | `https://zgujorkqulkdsnmjdxtj.supabase.co` | idem | `https://sjujhroqaoggwbwiviqu.supabase.co` |
| **NODE_ENV/ENVIRONMENT** | local | test | prod |

> ⚠️ **Corregido el 2026-07-31: esta matriz decía `nbigc…` y `mqld…`, y ninguno de los dos
> está en uso.** El cutover a europe-west1 + Supabase nuevo ya ocurrió (ver el CHANGELOG de
> process-ai-core). Verificado contra la fuente real, no contra los docs:
>
> - **PROD** = `sjujhroqaoggwbwiviqu`, leído del secreto `process-ai-database-url` en
>   `margay-platform-prod` y coincidente con el `SUPABASE_URL` de `ops/api/prod.config.toml`.
> - **TEST/LOCAL** = `zgujorkqulkdsnmjdxtj`, de `ops/api/test.config.toml` y del `.env` local.
>
> Los comentarios de `ops/api/prod.config.toml` también decían `mqld` y se corrigieron. Si
> encontrás `nbigc` o `mqld` en algún lado, es residuo previo al cutover: verificá contra el
> secreto o el `.config.toml` antes de creerle a un doc — es lo que costó una hora acá.
>
> **PROD ya tiene datos reales** (usuarios, tenants, configuración). Dejó de ser un staging.

> ⚠️ **El JWKS es por proyecto Supabase.** Un JWT firmado por sandbox NO valida contra el
> JWKS de prod. Cada ambiente debe usar el `SUPABASE_JWKS_URL`, `SUPABASE_URL`, anon key y
> service role key **del mismo proyecto Supabase**. No mezclar.

## Esquema de dominios

Patrón: `{servicio}.{ambiente}.margaystudio.io` — prod sin segmento de ambiente.

| Servicio | LOCAL | TEST | PROD |
|---|---|---|---|
| Hub | hub.local.margaystudio.io | hub.test.margaystudio.io | hub.margaystudio.io |
| Workspace (API) | (usa test) | workspace.test.margaystudio.io | workspace.margaystudio.io |
| Process-ai (front) | process.local.margaystudio.io | process.test.margaystudio.io | process.margaystudio.io |
| Process-ai (API) | api.local.margaystudio.io | api.process.test.margaystudio.io | api.process.margaystudio.io |

- **LOCAL**: DNS wildcard `*.local.margaystudio.io → 127.0.0.1` (ya configurado en Squarespace).
- **TEST/PROD**: dominio custom de Cloud Run (requiere domain mapping en GCP + registro DNS).

## Estado actual vs objetivo (qué falta para ordenar)

| Item | Estado | Acción |
|---|---|---|
| workspace test deployado | ✅ público + DB OK (resuelto 2026-06-02) | — |
| dev local → workspace test | ✅ funcionando (camino A) | — |
| workspace `prod.config` | ⚠️ **sin verificar** — este doc mentía sobre los refs | revisar contra el secreto de ese repo, no contra este doc |
| workspace `test.config` | apunta a sandbox ✅ | OK (ya es sandbox) |
| hub `test.config` | **no existe** | crear (sandbox + workspace test URL) — para admin/staging |
| hub `prod.config` | ⚠️ **sin verificar** — ídem | revisar contra el secreto de ese repo |
| process-ai `ops/*.config` | ✅ reales, test + prod (verificado 2026-07-31) | — |
| SA hub/process en test | **no existen** (solo workspace-sa) | crear antes de deployar |
| Dominios test | no existen | crear domain mappings + DNS |
| workspace dominio prod | usa `.run.app` | darle `workspace.margaystudio.io` (consistencia) |
| Supabase prod (`sjujhr…`) | ✅ en uso, con datos reales | — (el `mqld…` que decía este doc nunca se usó) |

## Gotchas de infra resueltos (no repetir)

- **Org policy `iam.allowedPolicyMemberDomains`**: bloquea `allUsers` invoker → servicios
  Cloud Run dan 403 aunque `allow_unauthenticated=true`. Fix: override a nivel proyecto
  `listPolicy: allValues: ALLOW` (prod ya lo tenía; test se aplicó 2026-06-02). Todo proyecto
  nuevo lo necesita.
- **Supabase pooler + SQLAlchemy/psycopg3**: si la `DATABASE_URL` trae `?prepare_threshold=0`,
  SQLAlchemy lo pasa como **string** a psycopg3 → `TypeError: '>=' not supported between int
  and str` al primer query. Fix: NO poner `prepare_threshold` en la URL (dejar la URL del
  pooler limpia, como prod). Si hiciera falta deshabilitar prepared statements, hacerlo en
  `create_engine(connect_args={"prepare_threshold": None})`, nunca como query param.

## Secretos por ambiente (Secret Manager)

Cada GCP project tiene sus propios secrets. NO compartir entre test y prod:
- `margay-platform-test`: service role key del **sandbox**, DB url de sandbox, etc.
- `margay-platform-prod`: service role key del **prod nuevo**, DB url de prod, etc.

Las **anon keys** de Supabase son públicas (van en config del front, no en secrets).
