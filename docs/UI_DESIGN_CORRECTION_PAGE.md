# Diseño UX: Página de Corrección de Documentos

## Contexto

El usuario (creador) recibió un documento rechazado con observaciones. Necesita corregirlo y reenviarlo para aprobación.

## Principios de Diseño

1. **Claridad**: El usuario debe entender rápidamente qué opción elegir
2. **Progreso visible**: Debe ver qué está haciendo y qué falta
3. **Prevención de errores**: Guiar hacia la opción correcta según el caso
4. **Feedback inmediato**: Mostrar estados de carga y resultados

## Diseño Propuesto: Cards de Opciones + Formulario Expandible

### Layout General

```
┌─────────────────────────────────────────────────────────┐
│  [Observaciones del Rechazo] (Siempre visible)          │
│  ┌───────────────────────────────────────────────────┐  │
│  │ "El documento tiene errores gramaticales..."     │  │
│  │ Rechazado por: Juan Pérez | Fecha: 15/01/2024    │  │
│  └───────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  [Preview del Documento Actual] (Sidebar derecha)      │
│  ┌───────────────────────────────────────────────────┐  │
│  │  [PDF Preview en iframe]                          │  │
│  │  Versión: 1.0 | Última actualización: ...        │  │
│  └───────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  [Opciones de Corrección] (Sección principal)          │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Patch por IA │  │ Edición Manual│  │ Regenerar    │ │
│  │              │  │              │  │              │ │
│  │ Ideal para:  │  │ Ideal para:  │  │ Ideal para:  │ │
│  │ - Errores    │  │ - Cambios    │  │ - Cambios    │ │
│  │   gramaticales│  │   estructurales│ │   en medios │ │
│  │ - Ajustes    │  │ - Control    │  │ - Nuevos     │ │
│  │   menores    │  │   total      │  │   archivos   │ │
│  │              │  │              │  │              │ │
│  │ [Usar esta]  │  │ [Usar esta]  │  │ [Usar esta]  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                         │
│  [Formulario Expandido] (Aparece al seleccionar)       │
│  ┌───────────────────────────────────────────────────┐ │
│  │  [Formulario de la opción seleccionada]           │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Flujo de Interacción

1. **Estado Inicial**: Usuario ve las 3 cards con descripciones claras
2. **Selección**: Usuario hace clic en una card → se expande el formulario correspondiente
3. **Completar**: Usuario completa el formulario y envía
4. **Feedback**: Loading state → Éxito/Error → Redirección o actualización

## Detalle de Cada Opción

### 1. Patch por IA (Card)

**Cuándo usar:**
- Errores gramaticales o de estilo
- Ajustes menores en el contenido
- Correcciones basadas en observaciones textuales
- El usuario no quiere editar manualmente el JSON

**Card Design:**
```
┌─────────────────────────────────────┐
│ 🤖 Patch por IA                     │
│                                     │
│ Correcciones automáticas usando IA │
│                                     │
│ ✅ Ideal para:                      │
│ • Errores gramaticales             │
│ • Ajustes de estilo                │
│ • Correcciones menores             │
│                                     │
│ ⚡ Rápido y automático              │
│                                     │
│ [Usar esta opción]                 │
└─────────────────────────────────────┘
```

**Formulario Expandido:**
```
┌─────────────────────────────────────┐
│ 🤖 Patch por IA                     │
│                                     │
│ Observaciones adicionales          │
│ (opcional - las observaciones del   │
│  rechazo ya están incluidas)        │
│ ┌─────────────────────────────────┐ │
│ │ [Textarea]                      │ │
│ │                                 │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [Aplicar Patch por IA]             │
│ (Loading: "Procesando con IA...")  │
└─────────────────────────────────────┘
```

### 2. Edición Manual (Card)

**Cuándo usar:**
- Cambios estructurales importantes
- El usuario quiere control total
- Correcciones que requieren conocimiento del formato JSON
- Cuando la IA no puede hacer los cambios necesarios

**Card Design:**
```
┌─────────────────────────────────────┐
│ ✏️ Edición Manual                    │
│                                     │
│ Edita directamente el JSON del       │
│ documento                           │
│                                     │
│ ✅ Ideal para:                      │
│ • Cambios estructurales            │
│ • Control total del contenido      │
│ • Correcciones complejas           │
│                                     │
│ ⚠️ Requiere conocimiento técnico   │
│                                     │
│ [Usar esta opción]                 │
└─────────────────────────────────────┘
```

**Formulario Expandido:**
```
┌─────────────────────────────────────┐
│ ✏️ Edición Manual                    │
│                                     │
│ Editor JSON                         │
│ ┌─────────────────────────────────┐ │
│ │ {                              │ │
│ │   "title": "...",              │ │
│ │   "steps": [...]               │ │
│ │ }                              │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Preview Markdown (actualiza en vivo)│
│ ┌─────────────────────────────────┐ │
│ │ # Título                        │ │
│ │ ## Paso 1                        │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [Guardar Cambios]                  │
└─────────────────────────────────────┘
```

### 3. Regenerar con Nuevos Archivos (Card)

**Cuándo usar:**
- Se tienen nuevos archivos (video, audio, imágenes)
- El contenido original cambió significativamente
- Se quiere rehacer el documento desde cero con nuevos medios
- Los cambios no se pueden hacer solo con texto

**Card Design:**
```
┌─────────────────────────────────────┐
│ 🔄 Regenerar Documento              │
│                                     │
│ Crea una nueva versión con nuevos   │
│ archivos multimedia                 │
│                                     │
│ ✅ Ideal para:                      │
│ • Nuevos archivos disponibles      │
│ • Cambios en el proceso            │
│ • Regeneración completa            │
│                                     │
│ 📁 Sube nuevos archivos             │
│                                     │
│ [Usar esta opción]                 │
└─────────────────────────────────────┘
```

**Formulario Expandido:**
```
┌─────────────────────────────────────┐
│ 🔄 Regenerar Documento              │
│                                     │
│ Notas de revisión                  │
│ (instrucciones para la IA)         │
│ ┌─────────────────────────────────┐ │
│ │ [Textarea]                      │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Archivos                           │
│ ┌─────────────────────────────────┐ │
│ │ [Drag & Drop o File Input]      │ │
│ │ Audio, Video, Imágenes, Texto   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [Regenerar Documento]             │
└─────────────────────────────────────┘
```

## Estados y Feedback

### Estados de las Cards

1. **Default**: Card normal, hover effect
2. **Selected**: Card con borde azul, fondo ligeramente destacado
3. **Processing**: Card deshabilitada, loading spinner
4. **Success**: Card con checkmark verde, mensaje de éxito

### Estados del Formulario

1. **Hidden**: No visible (cards visibles)
2. **Visible**: Formulario expandido, cards colapsadas o atenuadas
3. **Loading**: Botón deshabilitado, spinner, mensaje "Procesando..."
4. **Success**: Mensaje de éxito, opción de ver el resultado
5. **Error**: Mensaje de error, opción de reintentar

## Responsive Design

### Desktop (> 1024px)
- Layout de 2 columnas: Preview a la derecha (30%), Contenido principal a la izquierda (70%)
- Cards en fila horizontal (3 columnas)
- Formulario expandido ocupa el ancho completo

### Tablet (768px - 1024px)
- Layout de 1 columna: Preview arriba, contenido abajo
- Cards en fila horizontal (3 columnas, más pequeñas)
- Formulario expandido ocupa el ancho completo

### Mobile (< 768px)
- Layout de 1 columna: Todo apilado
- Cards en columna vertical (1 columna)
- Formulario expandido ocupa el ancho completo
- Preview colapsable (accordion)

## Accesibilidad

1. **Navegación por teclado**: Todas las cards y botones son focusables
2. **ARIA labels**: Labels descriptivos para screen readers
3. **Contraste**: Cumplir con WCAG AA mínimo
4. **Focus visible**: Indicadores claros de focus
5. **Mensajes de error**: Descriptivos y accionables

## Consideraciones Técnicas

1. **Estado compartido**: Usar React Context o estado local para manejar qué opción está seleccionada
2. **Validación**: Validar JSON antes de enviar en edición manual
3. **Preview en vivo**: Actualizar preview del Markdown mientras se edita el JSON
4. **Optimistic updates**: Mostrar loading inmediatamente, actualizar UI cuando termine
5. **Error handling**: Capturar y mostrar errores de forma amigable

## Próximos Pasos de Implementación

1. Crear componente `CorrectionPage` principal
2. Crear componente `CorrectionOptionCard` (reutilizable)
3. Crear componentes de formularios:
   - `AIPatchForm`
   - `ManualEditForm`
   - `RegenerateForm`
4. Crear componente `DocumentPreview` (sidebar)
5. Crear componente `RejectionObservations` (sección superior)
6. Integrar con API
7. Agregar estados de loading y error
8. Testing y refinamiento


