# Configuración de Confirmación de Email en Supabase

## IMPORTANTE: Confirmación de Email DESHABILITADA

Para que el flujo de invitación funcione correctamente, **la confirmación de email debe estar DESHABILITADA** en Supabase.

## Cómo Configurar

1. Ve a **Supabase Dashboard** → **Authentication** → **Settings**
2. Busca la sección **"Email Auth"** o **"Email Confirmation"**
3. **DESHABILITA** la opción **"Enable email confirmations"**
4. Guarda los cambios

## Por qué es necesario

El flujo de invitación está diseñado para que:
- Los usuarios nuevos puedan registrarse e ingresar inmediatamente
- No haya espera por confirmación de email
- El acceso al workspace sea inmediato después de aceptar la invitación

Si la confirmación de email está habilitada:
- El usuario no podrá ingresar inmediatamente después de registrarse
- Deberá esperar y confirmar su email primero
- Esto rompe la experiencia de onboarding fluida

## Alternativa: Magic Link solo para Reset Password

El flujo actual usa Magic Link **solo** para recuperación de contraseña ("Olvidé mi contraseña"), no para registro o login principal.

## Verificación

Para verificar que la configuración es correcta:

1. Intenta crear un nuevo usuario desde el flujo de invitación
2. Si el usuario puede ingresar inmediatamente después de crear su cuenta (sin esperar confirmación de email), la configuración es correcta
3. Si se muestra un mensaje pidiendo confirmar el email, la confirmación está habilitada y debe deshabilitarse

## Nota para Producción

En producción, puedes considerar:
- Mantener la confirmación deshabilitada para una mejor UX
- O habilitarla pero asegurarte de que el flujo maneje correctamente la espera de confirmación
- Configurar SMTP externo para mejor deliverabilidad de emails (ver `docs/ONBOARDING_EMAILS.md`)
