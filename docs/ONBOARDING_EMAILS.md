# Configuración de Emails para Onboarding B2B

## Contexto

El flujo de onboarding B2B utiliza Supabase Auth para autenticación. Durante el proceso de aceptación de invitaciones, los usuarios pueden:

1. **Registrarse con Email + Contraseña**: Requiere confirmación de email
2. **Usar Magic Link**: Envía un email con link de autenticación
3. **Usar OAuth (Google)**: No requiere email

## Problema: Rate Limits en Desarrollo

En desarrollo, Supabase tiene límites estrictos de envío de emails:
- **Magic Link**: ~3-4 emails por hora por IP
- **Email de confirmación**: ~3-4 emails por hora por IP
- **Recuperación de contraseña**: ~3-4 emails por hora por IP

Si se excede el límite, Supabase retorna errores como:
- `"rate limit exceeded"`
- `"too many requests"`

## Soluciones

### Para Desarrollo (DEV)

**Opción 1: Usar Email + Contraseña como método principal**
- El formulario de aceptación de invitación muestra "Email + Contraseña" como opción principal
- Magic Link se muestra como opción secundaria
- Si el usuario ya tiene cuenta, puede usar "Ya tengo cuenta" para iniciar sesión

**Opción 2: Deshabilitar confirmación de email en Supabase**
1. Ir a Supabase Dashboard → Authentication → Settings
2. Deshabilitar "Enable email confirmations"
3. Esto permite registro sin confirmación (solo para desarrollo)

**Opción 3: Usar OAuth (Google)**
- No requiere emails
- Funciona inmediatamente
- Recomendado para desarrollo rápido

### Para Producción (PROD)

**Configurar SMTP externo en Supabase:**

1. **Ir a Supabase Dashboard → Settings → Auth → SMTP Settings**

2. **Configurar con un proveedor de email:**
   - **SendGrid** (recomendado)
   - **Mailgun**
   - **Resend** (moderno, fácil)
   - **Amazon SES**
   - **Postmark**

3. **Ejemplo con Resend:**
   ```
   SMTP Host: smtp.resend.com
   SMTP Port: 465 (SSL) o 587 (TLS)
   SMTP User: resend
   SMTP Password: [API Key de Resend]
   Sender Email: noreply@tudominio.com
   Sender Name: Process AI
   ```

4. **Verificar dominio (opcional pero recomendado):**
   - Configurar SPF, DKIM, DMARC en tu dominio
   - Mejora la deliverabilidad

## Recomendaciones por Ambiente

### Desarrollo Local
- ✅ Usar **Email + Contraseña** como método principal
- ✅ Deshabilitar confirmación de email en Supabase
- ✅ Usar **OAuth (Google)** para pruebas rápidas
- ⚠️ Magic Link solo para pruebas ocasionales

### Staging
- ✅ Configurar SMTP con servicio gratuito (Resend free tier: 3,000 emails/mes)
- ✅ Mantener confirmación de email habilitada
- ✅ Probar todos los flujos (registro, magic link, recuperación)

### Producción
- ✅ **OBLIGATORIO**: Configurar SMTP con servicio confiable
- ✅ Verificar dominio (SPF, DKIM, DMARC)
- ✅ Monitorear rate limits y deliverabilidad
- ✅ Configurar webhooks para tracking de emails

## Manejo de Errores en la UI

La UI ya maneja errores de rate limit mostrando mensajes claros:

```typescript
if (error.message.toLowerCase().includes('rate limit') || 
    error.message.toLowerCase().includes('too many')) {
  setError(
    'Se ha alcanzado el límite de envíos de email. Por favor, espera unos minutos o usa Google OAuth para continuar inmediatamente.'
  )
}
```

## Alternativas cuando hay Rate Limit

1. **Esperar 1 hora** y reintentar
2. **Usar OAuth (Google)** - funciona inmediatamente
3. **Usar Email + Contraseña** si ya tienes cuenta
4. **Contactar al administrador** para reset manual

## Configuración Recomendada por Proveedor

### Resend (Recomendado para empezar)
- **Free tier**: 3,000 emails/mes
- **Setup**: 5 minutos
- **API**: Moderna y fácil
- **Docs**: https://resend.com/docs

### SendGrid
- **Free tier**: 100 emails/día
- **Setup**: 10-15 minutos
- **API**: Robusta
- **Docs**: https://docs.sendgrid.com

### Mailgun
- **Free tier**: 5,000 emails/mes (primeros 3 meses)
- **Setup**: 10 minutos
- **API**: Completa
- **Docs**: https://documentation.mailgun.com

## Checklist de Configuración

### Desarrollo
- [ ] Deshabilitar confirmación de email en Supabase
- [ ] Probar flujo con Email + Contraseña
- [ ] Probar flujo con OAuth (Google)
- [ ] Verificar que los mensajes de error de rate limit se muestran correctamente

### Producción
- [ ] Configurar SMTP externo
- [ ] Verificar dominio (SPF, DKIM, DMARC)
- [ ] Probar envío de emails (registro, magic link, recuperación)
- [ ] Configurar monitoreo de deliverabilidad
- [ ] Documentar límites del proveedor elegido
- [ ] Configurar alertas para rate limits

## Troubleshooting

### "Rate limit exceeded" en desarrollo
**Solución**: Esperar 1 hora o usar OAuth

### Emails no llegan en producción
**Verificar**:
1. SMTP configurado correctamente
2. Credenciales correctas
3. Dominio verificado
4. Logs de Supabase para errores específicos

### Emails van a spam
**Solución**:
1. Verificar SPF, DKIM, DMARC
2. Usar dominio verificado (no subdomain genérico)
3. Configurar "From" address con dominio propio

## Referencias

- [Supabase Auth Email Settings](https://supabase.com/docs/guides/auth/auth-email)
- [Resend Documentation](https://resend.com/docs)
- [SendGrid Setup Guide](https://docs.sendgrid.com/for-developers/sending-email/getting-started-smtp)
- [Mailgun SMTP Setup](https://documentation.mailgun.com/en/latest/user_manual.html#sending-via-smtp)
