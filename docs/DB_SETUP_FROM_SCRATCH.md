# Crear la base de datos desde cero

Guía paso a paso para inicializar la base de datos en un entorno nuevo (local, test o producción).

## Opción A: Base de datos vacía (primera vez)

### 1. Crear las tablas

```bash
python tools/init_db.py
```

Crea todas las tablas definidas en los modelos SQLAlchemy.

### 2. Seed de permisos y roles

```bash
python tools/seed_permissions.py
```

Crea roles (superadmin, owner, admin, approver, member), permisos y sus asignaciones.

### 3. (Opcional) Planes de suscripción

```bash
python tools/seed_subscription_plans.py
```

### 4. (Opcional) Catálogos

```bash
python tools/seed_catalogs.py
```

### 5. Crear super admins

```bash
# Crea Santiago y Nacho (definidos por defecto)
python tools/create_super_admin.py

# O agregar uno específico por email y nombre
python tools/create_super_admin.py otro@email.com "Nombre Apellido"
```

---

## Opción B: Resetear BD existente (mantener estructura, borrar datos)

Si ya tenés una BD con datos y querés volver a estado "primer día":

```bash
python tools/reset_to_production_ready.py
```

**⚠️ Elimina** todos los datos dinámicos (usuarios, workspaces, documentos, runs, etc.).

**✅ Mantiene** permisos, roles, planes de suscripción y catálogos.

Luego volvé a crear los super admins:

```bash
python tools/create_super_admin.py
```

---

## Opción C: Borrar todo y empezar de cero

Si querés una BD completamente limpia (por ejemplo, cambiaste el schema):

```bash
# 1. Eliminar el archivo de la BD (SQLite)
# Mac/Linux:
rm -f data/process_ai_core.sqlite
# Windows:
# del data\process_ai_core.sqlite

# 2. Crear el directorio si no existe
# Mac/Linux: mkdir -p data
# Windows: mkdir data

# 3. Seguir con Opción A desde el paso 1
python tools/init_db.py
python tools/seed_permissions.py
python tools/seed_subscription_plans.py
python tools/seed_catalogs.py
python tools/create_super_admin.py
```

---

## Resumen rápido (copy-paste)

```bash
# Desde cero absoluto
rm -f data/process_ai_core.sqlite
python tools/init_db.py
python tools/seed_permissions.py
python tools/seed_subscription_plans.py
python tools/seed_catalogs.py
python tools/create_super_admin.py
```
