# FIX-COOKIES — Sesión SSO Hub → Process AI

**Fecha:** 2026-07-03  
**Módulo:** `process-ai-core/ui`  
**Síntoma reportado:** Error de hidratación / pantalla colgada en *"Verificando autenticación..."* con topbar mostrando *"Usuario"*, al entrar a Process AI desde el Hub estando logueado. En incógnito funcionaba.

---

## Resumen del problema

### Flujo que fallaba

1. Login en **Margay Hub** (`hub.local.margaystudio.io:3001`).
2. Supabase emite cookie `sb-<project>-auth-token` en dominio **`.local.margaystudio.io`** (HttpOnly).
3. Clic en tarjeta **Process AI** → navega a `process.local.margaystudio.io:3000`.
4. El **middleware de Process** lee la cookie en el servidor y deja pasar la request.
5. En el **browser**, varios componentes llamaban a `supabase.auth.getSession()` desde el cliente JS.
6. Las cookies **HttpOnly no son visibles** desde `document.cookie` → el cliente creía que no había sesión.
7. Consecuencias:
   - Spinner infinito (*Verificando autenticación...*).
   - Topbar con fallback `"Usuario"` (sin perfil cargado).
   - En un intento intermedio del fix, se **borraban cookies válidas** al fallar `getSession()`, empeorando el bucle Hub ↔ Process.
   - Error React (`NotFoundErrorBoundary` / hidratación) como efecto colateral de estados inconsistentes.

### Por qué incógnito parecía funcionar

Incógnito no tenía estado previo corrupto. Con sesión limpia y sin reintentos de `getSession()` + limpieza agresiva de cookies, el flujo podía completarse. El problema **no era basura acumulada en el navegador**, sino **cómo Process leía la sesión en el cliente** frente a cookies HttpOnly compartidas por SSO.

---

## Causa raíz

| Capa | ¿Lee cookie HttpOnly? | Comportamiento |
|------|------------------------|----------------|
| Middleware Process (`getUser()`) | ✅ Sí | Usuario autenticado, página renderiza shell |
| Cliente Supabase (`getSession()`) | ❌ No | Sesión aparentemente ausente |
| `getAccessToken()` (antes) | ❌ No | API `/users/me` sin Bearer → perfil no carga |

**Conclusión técnica:** Process AI asumía que el cliente browser podía leer la misma sesión que el servidor. En SSO con cookie compartida y HttpOnly (como en el Hub), eso es incorrecto. El token debe obtenerse **en el servidor** y exponerse al cliente por una ruta interna.

---

## Archivos modificados

### Archivos nuevos

| Archivo | Rol |
|---------|-----|
| `ui/lib/hub-login.ts` | Redirect al login del Hub con `next` |
| `ui/lib/clear-auth-state.ts` | Limpieza de cookies Supabase + localStorage (solo sign-out) |
| `ui/lib/supabase/cookie-options.ts` | Dominio `.local.margaystudio.io` alineado con Hub |
| `ui/app/api/auth/session/route.ts` | Puente servidor → cliente para el access token |

---

## Cambios por archivo (antes / después)

### 1. `ui/lib/api-auth.ts` — Obtención del token

**Antes** (cliente intentaba leer sesión directamente):

```typescript
import { createClient } from '@/lib/supabase/client'

export async function getAccessToken(): Promise<string | null> {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token || null
}
```

**Después** (token vía API server-side):

```typescript
export async function getAccessToken(): Promise<string | null> {
  try {
    const response = await fetch('/api/auth/session', { credentials: 'include' })
    if (!response.ok) return null
    const data = (await response.json()) as { access_token?: string | null }
    return data.access_token ?? null
  } catch {
    return null
  }
}
```

---

### 2. `ui/app/api/auth/session/route.ts` — **NUEVO**

```typescript
export async function GET() {
  const supabase = await createClient() // server — lee cookies HttpOnly
  const { data: { session }, error } = await supabase.auth.getSession()

  if (error || !session?.access_token) {
    return NextResponse.json({ access_token: null }, { status: 401 })
  }

  return NextResponse.json({ access_token: session.access_token })
}
```

---

### 3. `ui/app/page.tsx` — Home sin re-validación cliente

**Antes** (doble auth + redirect a `/login` local inexistente):

```typescript
useEffect(() => {
  async function checkAuth() {
    const supabase = createClient()
    const timeoutId = setTimeout(() => {
      router.push('/login')  // ruta que no existe en Process
    }, 6000)

    const { data: { session }, error } = await supabase.auth.getSession()
    // ...
  }
  checkAuth()
}, [router])
```

**Después** (confía en middleware + WorkspaceContext):

```typescript
// El middleware ya validó la sesión SSO. Acá solo enrutamos según rol/workspace.
useEffect(() => {
  if (userValidation.isValid === null) return
  if (userValidation.isValid === false) return
  if (workspaceLoading) return
  // router.push según rol...
}, [userValidation, workspaceLoading, selectedWorkspaceId, roleLoading, role, router])
```

Mensaje de loading:

```diff
- 'Verificando autenticación...'
+ 'Cargando tu perfil...'
```

Sign-out:

```diff
- router.push('/login')
+ clearLocalAuthState()
+ redirectToHubLogin(false)
```

---

### 4. `ui/hooks/useUserValidation.ts`

**Antes** (~60 líneas con `getSession()` + timeout en cliente):

```typescript
const supabase = createClient()
const result = await Promise.race([
  supabase.auth.getSession(),
  new Promise((_, reject) => setTimeout(() => reject(new Error('SupabaseTimeout')), 6000)),
])
// ...
```

**Después** (solo WorkspaceContext):

```typescript
export function useUserValidation(): UserValidationState {
  const { loading: workspaceLoading, workspaces, currentUser } = useWorkspace()

  if (workspaceLoading) {
    return { isValid: null, hasWorkspaces: null, error: null, localUserId: null }
  }
  if (!currentUser) {
    return { isValid: false, hasWorkspaces: false, error: 'No se pudo cargar el perfil...', localUserId: null }
  }
  return { isValid: true, hasWorkspaces: workspaces.length > 0, error: null, localUserId: currentUser.id }
}
```

---

### 5. `ui/hooks/useUserId.ts`

**Antes** (~100 líneas: `getSession`, `localStorage`, listeners):

```typescript
const { data: { session } } = await supabase.auth.getSession()
const storedUserId = localStorage.getItem('local_user_id')
```

**Después**:

```typescript
export function useUserId(): string | null {
  const { currentUser, loading } = useWorkspace()
  if (loading) return null
  return currentUser?.id ?? null
}
```

---

### 6. `ui/hooks/useUser.ts`

**Antes** (`getSession()` + `onAuthStateChange`):

```typescript
const { data: { session } } = await supabase.auth.getSession()
if (session?.user) {
  setUser({ email: session.user.email, name: metadata.name, ... })
}
```

**Después** (WorkspaceContext):

```typescript
export function useUser(): UserInfo | null {
  const { currentUser, loading } = useWorkspace()
  if (loading || !currentUser) return null
  return { email: currentUser.email, name: currentUser.name, avatarUrl: null, supabaseUserId: null }
}
```

---

### 7. `ui/lib/hub-login.ts` — **NUEVO**

Reemplaza `router.push('/login')` por redirect al Hub SSO:

```typescript
// Antes (en varios archivos):
router.push('/login')

// Después:
const hub = process.env.NEXT_PUBLIC_HUB_URL ?? 'https://hub.margaystudio.io'
window.location.assign(`${hub}/login?next=${encodeURIComponent(window.location.href)}`)

// Encapsulado en:
redirectToHubLogin()           // auth fallida → Hub con next=URL actual
redirectToHubLogin(false)      // sign-out → Hub /login sin next
```

> **Nota:** `clearLocalAuthState()` solo se ejecuta en sign-out explícito, **no** al detectar fallo de `getSession()` en cliente.

---

### 8. `ui/components/layout/ChromeShell.tsx` — Sign out

**Antes:**

```typescript
await supabase.auth.signOut()
localStorage.removeItem('local_user_id')
router.push('/login')
```

**Después:**

```typescript
await supabase.auth.signOut()
clearLocalAuthState()
redirectToHubLogin(false)
```

---

### 9. `ui/lib/supabase/middleware.ts` — Dominio de cookies

**Antes:**

```typescript
supabaseResponse.cookies.set(name, value, options)
```

**Después:**

```typescript
import { withSupabaseCookieOptions } from '@/lib/supabase/cookie-options'
// ...
supabaseResponse.cookies.set(name, value, withSupabaseCookieOptions(options))
```

Alinea el dominio `.local.margaystudio.io` con el Hub al refrescar sesión.

---

### 10. `ui/lib/supabase/cookie-options.ts` — **NUEVO**

Centraliza opciones compartidas con Margay Hub:

```typescript
export function getSupabaseCookieDomain(): string | undefined {
  return process.env.NEXT_PUBLIC_COOKIE_DOMAIN
    ?? (process.env.NODE_ENV === 'production' ? '.margaystudio.io' : undefined)
}

export function withSupabaseCookieOptions(options?: CookieOptions): CookieOptions {
  // domain, sameSite: 'lax', secure, path: '/'
}
```

Usado en: `middleware.ts`, `server.ts`, `client.ts`.

---

## Diagrama del flujo corregido

```
Hub login
   │
   ▼
Cookie sb-*-auth-token  (.local.margaystudio.io, HttpOnly)
   │
   ▼
Clic Process AI → process.local.margaystudio.io:3000
   │
   ├─ Middleware: getUser() ✅ (lee cookie en request)
   │
   ├─ WorkspaceContext: GET /api/v1/users/me
   │     └─ getAccessToken() → fetch /api/auth/session ✅ (servidor lee cookie)
   │
   └─ Home: redirect por rol → /dashboard/to-review ✅
```

---

## Cómo verificar el fix

### Checklist manual

1. [ ] Login en Hub (`https://hub.local.margaystudio.io:3001`).
2. [ ] Ver cookie `sb-*-auth-token` en Application → Cookies → `.local.margaystudio.io`.
3. [ ] Clic en **Process AI** (pestaña normal, no incógnito).
4. [ ] Topbar muestra nombre real (ej. *Nacho Azaretto*), no *Usuario*.
5. [ ] Redirección automática al dashboard según rol (ej. `/dashboard/to-review`).
6. [ ] En DevTools → Network: `GET /api/auth/session` responde **200** con `{ access_token: "..." }`.
7. [ ] En DevTools → Network: `GET .../api/v1/users/me` responde **200**.

### Señales de que el bug persiste

| Señal | Posible causa |
|-------|----------------|
| Spinner *Verificando autenticación...* | Código viejo sin deploy / hot reload incompleto |
| `/api/auth/session` → 401 | Cookie no llega a Process (dominio, HTTPS, env) |
| `/api/v1/users/me` → 401 | Token no se inyecta en Authorization |
| Bucle Hub ↔ Process | Hub redirige con access token expirado pero refresh roto |

### Variables de entorno relevantes (`ui/.env.local`)

```env
NEXT_PUBLIC_HUB_URL=https://hub.local.margaystudio.io:3001
NEXT_PUBLIC_COOKIE_DOMAIN=.local.margaystudio.io
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
```

---

## Conclusión

El error **no era un problema de cookies sucias en el navegador**, sino un **desacople entre servidor y cliente** en Process AI:

- El **servidor** (middleware) sí veía la sesión SSO del Hub.
- El **cliente** intentaba validarla con `getSession()`, que **no puede leer cookies HttpOnly**.
- Eso dejaba la UI en estado intermedio (*Usuario*, spinner, errores de hidratación) aunque el usuario estuviera correctamente logueado en el Hub.

La solución adoptada sigue el patrón correcto para SSO con cookies HttpOnly:

1. **Confiar en el middleware** para proteger rutas.
2. **Obtener el access token en el servidor** (`/api/auth/session`) para llamadas al backend.
3. **Centralizar el perfil** en `WorkspaceContext` (`GET /users/me`) en lugar de duplicar lógica con `getSession()` en cada hook.
4. **Redirigir al Hub** (no a `/login` local) cuando haga falta re-autenticación.
5. **Limpiar cookies solo en sign-out explícito**, nunca al fallar una lectura imposible desde JS.

Con estos cambios, el flujo Hub → Process AI debe funcionar igual en pestaña normal e incógnito, siempre que la cookie SSO sea válida y las variables de dominio estén configuradas.
