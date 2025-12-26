# Configuración Rápida de Supabase para Test

## 📋 Resumen de Claves Necesarias

### 1. Project URL
- **Dónde encontrarlo**: Settings → API (parte superior de la página)
- **Formato**: `https://xxxxx.supabase.co`
- **Usar en**: Ambos archivos (backend y frontend)

### 2. Publishable Key (Frontend)
- **Dónde encontrarlo**: Settings → API → Sección "Publishable key"
- **Cómo copiarlo**: 
  - Busca la clave con nombre "default" (o la que hayas creado)
  - Haz clic en el ícono de copiar 📋
  - El valor empieza con `sb_publishable_...`
- **Usar en**: `ui/.env.test` → `NEXT_PUBLIC_SUPABASE_ANON_KEY`

### 3. Secret Key (Backend)
- **Dónde encontrarlo**: Settings → API → Sección "Secret keys"
- **Cómo copiarlo**:
  - Busca la clave con nombre "default" (o la que hayas creado)
  - Haz clic en el ícono del ojo 👁️ para revelar la clave
  - Haz clic en el ícono de copiar 📋
  - El valor empieza con `sb_secret_...`
- **Usar en**: `.env.test` → `SUPABASE_SERVICE_ROLE_KEY`
- ⚠️ **IMPORTANTE**: Esta clave es secreta, nunca la compartas ni la expongas

## 📝 Ejemplo de Configuración

### Backend (`.env.test`)
```env
SUPABASE_URL=https://tu-proyecto-test.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_NsGIdxxxxxxxxxxxxxxxxxxxxx
```

### Frontend (`ui/.env.test`)
```env
NEXT_PUBLIC_SUPABASE_URL=https://tu-proyecto-test.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_w2Bywk5iAGHYam9GDdrd3w_EKm7T...
```

## ✅ Verificación

Después de configurar, verifica que:
1. ✅ El Project URL es el mismo en ambos archivos
2. ✅ La Publishable key va en el frontend
3. ✅ La Secret key va en el backend
4. ✅ No hay espacios extra al copiar las claves
5. ✅ Las claves están completas (no cortadas)

## 🚀 Siguiente Paso

Una vez configuradas las claves, configura las URLs de redirección:
1. Ve a **Authentication** → **URL Configuration**
2. Site URL: `http://localhost:3001`
3. Redirect URLs: `http://localhost:3001/auth/callback`
