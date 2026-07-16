# Handoff - Config Carpetas

Contexto: esta feature convierte "Carpetas" en una seccion propia de administracion y
agrega campos de gobierno por carpeta. El diseno visual toma como referencia
`prototipo/export_react 2/src/screens/CarpetasScreen.tsx`, adaptado al design system real.

## Alcance implementado

Tickets cubiertos: Config-Carpetas 1 a 8.

- Backend: nuevos campos de gobierno en `folders`.
- Backend: `PUT /api/v1/folders/{id}` acepta y persiste esos campos.
- Backend: `GET /api/v1/folders/{folder_id}/stats`.
- Backend: `GET /api/v1/folders/{folder_id}/governance`.
- Front: nueva ruta `/folders`.
- Front: nav lateral apunta "Carpetas" a `/folders`.
- Front: arbol de carpetas con expand/collapse, contador de documentos, color e icono.
- Front: creacion de carpeta usando `useFolderCrud`.
- Front: drag & drop para reparentar carpetas usando `useFolderCrud.reparentFolder`.
- Front: ficha de carpeta con header, strip de metricas y tabs.
- Front: tabs `Resumen`, `General`, `Gobierno` y `Tyto` conectados.

## Modelo de datos

En `process_ai_core/db/models.py`, modelo `Folder`, se agregaron:

- `icon: str | None`
- `default_document_type: str | None`
- `tyto_enabled: bool | None`
- `allow_document_override: bool`

Semantica de herencia:

- `default_document_type = null` significa que hereda del padre.
- `tyto_enabled = null` significa que hereda del padre.
- `allow_document_override` no es heredable en el MVP; siempre se toma el valor propio.

Migracion:

- `alembic/versions/0010_folder_governance_fields.py`

Nota de proceso: no aplicar migraciones al sandbox compartido desde una rama sin mergear.
Aplicarlas recien cuando la rama entra a `develop`.

## API

### PUT `/api/v1/folders/{id}`

Acepta los nuevos campos:

```json
{
  "icon": "folder",
  "default_document_type": "procedimiento",
  "tyto_enabled": true,
  "allow_document_override": true
}
```

Tambien permite enviar `default_document_type: null` o `tyto_enabled: null` para volver a
heredar.

### GET `/api/v1/folders/{folder_id}/stats`

Devuelve metricas para el strip de la ficha:

```json
{
  "documentos": 10,
  "aprobados": 6,
  "borradores": 2,
  "pendientes": 1,
  "archivados": 1,
  "relaciones_nuevas": 3,
  "confianza_prom": 0.92
}
```

Mapeo de estados de documentos:

- `draft` -> `borradores`
- `pending_validation` -> `pendientes`
- `approved` -> `aprobados`
- `archived` -> `archivados`

Relaciones:

- `relaciones_nuevas`: relaciones `candidate` de documentos de esa carpeta.
- `confianza_prom`: promedio de `confidence` de relaciones `confirmed`; `null` si no hay.

### GET `/api/v1/folders/{folder_id}/governance`

Devuelve valor efectivo y origen para los bloques heredables:

```json
{
  "default_document_type": {
    "value": "procedimiento",
    "origin": "heredado",
    "from": "Procesos"
  },
  "tyto_enabled": {
    "value": true,
    "origin": "personalizado",
    "from": null
  },
  "allow_document_override": {
    "value": true,
    "origin": "personalizado"
  }
}
```

Origenes posibles:

- `base`: no hay valor definido en la carpeta ni en ancestros.
- `heredado`: viene del primer ancestro que define el valor.
- `personalizado`: la carpeta define el valor localmente.

## Frontend

Archivos principales:

- `ui/app/folders/page.tsx`
- `ui/lib/api.ts`
- `ui/hooks/useFolderCrud.ts`
- `ui/components/layout/ChromeShell.tsx`

Primitivos reutilizados:

- `useAsync` para carga y estados `loading`/`empty`/`error`.
- `useFolderCrud` para crear, editar, reparentar y refrescar carpetas.
- `Tabs` / `TabsContent` para la ficha.
- `Switch` para toggles.
- `InheritancePill` para mostrar `base`, `inherited` o `custom`.
- `canAdministerWorkspace` para gating de nav.

### Pantalla `/folders`

Panel izquierdo:

- Arbol de carpetas.
- Expand/collapse.
- Contador de documentos.
- Color e icono.
- Boton "Nueva carpeta".
- Drag & drop para mover una carpeta dentro de otra.

Panel derecho:

- Header con breadcrumb, nombre, badge "Activa" y descripcion.
- Strip de metricas reales desde `/stats`.
- Tabs:
  - `Resumen`: tarjetas con metricas + documentos recientes.
  - `General`: editar nombre, descripcion, color e icono.
  - `Gobierno`: tipo documental por defecto + allow override.
  - `Tyto`: toggle heredable de disponibilidad para consultas.
  - `Permisos`: placeholder.
  - `Actividad`: placeholder.

## Gobierno y herencia en UI

El backend devuelve `origin` en espanol. El front lo mapea asi:

- `base` -> `InheritancePill kind="base"`
- `heredado` -> `InheritancePill kind="inherited"`
- `personalizado` -> `InheritancePill kind="custom"`

En `Gobierno`:

- "Tipo documental por defecto" muestra el valor efectivo y el pill.
- "Personalizar" guarda `default_document_type`.
- "Heredar" guarda `default_document_type: null`.
- "Permitir sobrescribir por documento" usa `allow_document_override`.

En `Tyto`:

- "Disponible para consultas" muestra el valor efectivo y el pill.
- Cambiar el switch guarda `tyto_enabled`.
- "Heredar configuracion" guarda `tyto_enabled: null`.

## Validacion realizada

Frontend:

```bash
cd ui
npm.cmd run build
```

Resultado: build OK.

Backend:

Se compilaron los archivos Python tocados durante la implementacion de endpoints.

## Como probar manualmente

1. Levantar backend y frontend.
2. Ir a `/folders`.
3. Crear una carpeta desde el panel izquierdo.
4. Seleccionar una carpeta y revisar:
   - header
   - metricas
   - tabs
5. En `General`, editar nombre, descripcion, color e icono.
6. En `Gobierno`, personalizar tipo documental y activar/desactivar override.
7. En `Tyto`, activar/desactivar disponibilidad para consultas.
8. Mover una carpeta arrastrandola sobre otra.
9. Refrescar la pantalla y confirmar que los cambios persisten.

## Pendientes fuera de este alcance

- Contenido real de `Permisos`.
- Contenido real de `Actividad`.
- Tests automatizados de la pantalla `/folders`.
- Validacion visual end-to-end con datos reales en sandbox despues de merge.
