# Teléfono en perfil de usuario (front y back)

Resumen de lo implementado para guardar y mostrar el teléfono del usuario en Mi perfil (característica + número, banderas, verificado).

---

## Backend

### Modelo `User` (`process_ai_core/db/models.py`)

- **phone_e164** (string, nullable): número en formato E.164 (ej. `+59891234567`).
- **phone_verified** (bool): si el número está verificado.
- **phone_verified_at** (datetime, nullable): cuándo se verificó.

### Migración

- **Archivo:** `tools/migrate_add_user_phone.py`
- Crea las columnas `phone_e164`, `phone_verified`, `phone_verified_at` en la tabla `users`.
- Ejecutar (con el entorno activo):  
`python tools/migrate_add_user_phone.py`

### API (`api/routes/users.py`)

- **GET** `/api/v1/users/{user_id}`  
La respuesta incluye: `phone_e164`, `phone_verified`, `phone_verified_at`.
- **PUT** `/api/v1/users/{user_id}`  
Body opcional: `name`, `phone_e164`. Solo el propio usuario puede actualizar su perfil. Los campos `phone_verified` y `phone_verified_at` no se editan desde este endpoint (quedan para un flujo futuro de verificación).

---

## Frontend

### Cliente API (`ui/lib/api.ts`)

- Tipo **UserProfile** con: `id`, `email`, `name`, `phone_e164`, `phone_verified`, `phone_verified_at`.
- **getUser(userId)** devuelve `UserProfile` (incluye los campos de teléfono).
- **updateMyProfile(userId, { name?, phone_e164? })** hace PUT al perfil con token; usado al guardar en Mi perfil.

### Página Mi perfil (`ui/app/profile/page.tsx`)

- **Formulario:** nombre (editable), email (solo lectura), teléfono en dos partes.
- **Teléfono en dos partes:**
  - Selector de **código de país** (dropdown): lista fija con opciones (Uruguay +598, Argentina +54, Brasil +55, México +52, Colombia +57, Chile +56, Perú +51, España +34, EE.UU./Canadá +1, Alemania +49, Francia +33, Italia +39). Si el número guardado tiene un código no listado, se muestra como opción extra “Otro” con ese código.
  - Campo **número**: solo dígitos (ej. 91234567). Se persiste en backend el E.164 completo (código + número).
- **Banderas:** imágenes desde el CDN **flagcdn.com** (`https://flagcdn.com/w40/{iso}.png`), sin dependencias npm. Componente `FlagImage` para cada país; opción “Otro” con ícono de globo (SVG).
- **Estado verificado:** icono ✓ (verde) o ✗ (rojo) al lado del teléfono según `phone_verified`; si está verificado se muestra la fecha (`phone_verified_at`).
- **Botón “Verificar”:** al tocarlo se muestra un pop-up: “Se envió un código de verificación al número: {número}”. El pop-up se cierra solo a los 3 segundos (por ahora no hay envío real de código).
- **Etiqueta:** el campo se llama “Teléfono” (sin “E.164” en la UI).

### Header (`ui/components/layout/Header.tsx`)

- El ítem “Mi perfil” en el menú de usuario enlaza a `/profile`.
- El nombre mostrado (y las iniciales del avatar) vienen del perfil en el backend. Al guardar en Mi perfil se dispara el evento `profileUpdated` y el Header vuelve a cargar el nombre.

---

## Flujo de datos

1. Al cargar Mi perfil se llama `getUser(userId)`; el E.164 guardado se parte en código de país y número con `parsePhoneE164` (según la lista de códigos conocidos).
2. El usuario elige país y escribe número; al guardar se arma el E.164 con `buildPhoneE164(prefix, number)` y se envía vía `updateMyProfile(userId, { phone_e164 })`.
3. El backend guarda `phone_e164`; `phone_verified` y `phone_verified_at` solo se muestran (por ahora no hay flujo de verificación real).

