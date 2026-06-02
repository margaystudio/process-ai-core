# Estrategia Comercial y Pricing — Process AI Core

> **Fecha:** 2026-05-28
> **Autores:** Santiago (Margay Studio) + análisis asistido (Claude)
> **Estado:** Borrador para validar con el primer cliente (GPU) y calibrar en dogfooding.
> **Documentos relacionados:** `docs/CODE_REVIEW_2026-05_MVP_PLAN.md`, `docs/RAG_IMPLEMENTATION_PLAN.md`

> ⚠️ **Aviso sobre los números:** los precios de OpenAI/Supabase y los rangos de tarifa de
> abajo son **estimaciones a 2026-05** para dimensionar el negocio. Reconfirmar precios
> vigentes de proveedores y calibrar las tarifas de venta con datos reales del dogfooding
> antes de cerrar una propuesta comercial.

---

## 1. ¿Agrega valor? Sí — pero el valor real no es "documentar"

Documentar es el *medio*, no el dolor que se paga por resolver. Los dolores reales y
costosos en una estación de servicio:

- **Rotación + reentrenamiento:** cada pistero que entra cuesta semanas de un encargado
  explicando lo mismo. ROI medible.
- **Errores operativos repetidos** (arqueos, recepción de mercadería, cierres de turno) →
  mermas y diferencias de caja.
- **Dependencia de la persona clave:** si se va el encargado, cae la calidad. Riesgo puro.

El producto ataca los tres. El diferenciador no es generar el PDF, es el **loop completo**:
capturar conocimiento informal → documentar → **mantenerlo vivo** (versiones + aprobación)
→ **consultarlo al instante** (RAG). Un editor de documentos no hace eso; un consultor
tradicional lo hace una vez y se va. Esto queda operando.

**Riesgo honesto:** el valor depende de la **adopción**, no de la tecnología. Si el dueño
compra pero nadie documenta ni consulta, se cae a los 3 meses. Por eso conviene **empezar
con consultoría** (Margay documenta los procesos clave): garantiza contenido útil desde el
día 1, que es justo donde mueren los SaaS de documentación.

---

## 2. Estrategia de venta: "consultoría que deja producto"

Secuencia recomendada:

1. **Land con servicio (alto ticket, alta confianza).** Vender un *Setup de Documentación*:
   Margay releva y documenta los procesos críticos. Entregable tangible, valor inmediato,
   no depende de que el cliente "aprenda a usar una app".
2. **Expand con SaaS (recurrente).** El cliente queda con la plataforma para mantener y
   ampliar. Suscripción mensual por estación.
3. **Retén con auditorías + RAG.** La revisión trimestral y el asistente son la excusa
   recurrente para seguir adentro y justificar la mensualidad.

Esto da caja temprana (el servicio paga el desarrollo) y construye los casos de éxito que
después venden el SaaS solo. **Margay (dogfooding) y GPU son los dos primeros casos.**

---

## 3. Costos: qué se puede predecir hoy y qué no

### 3.1 Costo de IA por documento — **predecible (determinístico)**

Modelos en uso: `gpt-4.1-mini` (texto/visión), `gpt-4o-mini-transcribe` / `whisper-1`
(audio). El costo = precio por token × tokens, acotado por escenario:

| Etapa | Modelo | Consume | Costo aprox. |
|---|---|---|---|
| Transcripción audio | whisper | minutos de audio | ~US$0.006/min |
| Inferencia de pasos | gpt-4.1-mini | la transcripción | centavos |
| Selección de frames | gpt-4.1-mini visión | **3 frames candidatos por paso** (`media.py:424`) | parte más variable |
| Generación del documento | gpt-4.1-mini | contexto → JSON | centavos |

- **Documento desde texto/audio corto:** **US$0.05–0.20** por documento.
- **Peor caso (video ~15 min, ~15 pasos → ~45 imágenes a visión):** **US$0.50–1.50**.

> **Conclusión:** el costo de IA por documento va de **centavos a ~US$1.5**. Frente a una
> suscripción mensual o un setup, es ruido. **La IA no es la restricción de margen.**
> Única palanca si se quisiera bajar: reducir los 3 frames por paso en video.

### 3.2 Costo de infraestructura — **predecible**

| Pieza | Dónde | Qué guarda | Costo |
|---|---|---|---|
| Base de datos | Supabase Postgres | Texto: documentos, versiones, metadata, RBAC. **Liviano.** | Incluido en plan Supabase |
| Storage de objetos | Supabase Storage | PDFs, **videos subidos**, frames | ~US$0.021/GB/mes + egreso |
| Compute | Hosting (Railway/Render/Fly/VPS) | API + Next.js | Tier fijo mensual, **se reparte entre clientes** |

**Estado actual (a corregir en el MVP):** hoy los archivos se guardan en **disco local**
del servidor (`api/routes/artifacts.py:33`, `output_dir`). No es apto para SaaS (se pierde
al reiniciar / no se comparte entre instancias). El plan MVP migra a Supabase Storage.

**Dato real medido:** 7 corridas de prueba generaron **32 MB** en `output/`. El peso lo
domina **el video**:
- Documento desde texto/audio: output (JSON+MD+PDF) en **kilobytes**. Despreciable.
- Documento desde video: el peso está en el **video crudo** (un screen recording de 15 min
  son ~100–300 MB). Los frames extraídos son chicos.

**Estimación por estación:** ~50 procesos **sin guardar videos crudos** → **< 1 GB** →
storage de **centavos/mes**. Guardando todos los videos → varios GB → algunos US$/mes.

> **Decisión de producto que define el costo de infra:**
> **¿Se guarda el video original o solo el documento resultante?**
> Recomendación: **no guardar el video crudo a largo plazo.** Una vez generado el documento
> aprobado, el video cumplió su función. Guardarlo temporal (X días, para reprocesar) y
> borrarlo. Así el storage se vuelve despreciable. Si el cliente quiere el video como
> evidencia permanente (auditoría/ISO) → **feature premium** que paga su propio costo.

### 3.3 Costo de tu tiempo de consultoría — **NO predecible desde el código**

Es el costo **dominante** del servicio. Depende de qué tan complejo es relevar un proceso
real con un cliente. **Se mide en el dogfooding:** cronometrar relevar + documentar +
aprobar **un** proceso real, de punta a punta. Ese número × costo/hora objetivo = piso del
precio del setup.

### 3.4 Veredicto de costos

- IA: centavos a ~US$1.5 por documento.
- Storage: centavos/mes por estación (sin videos crudos).
- Compute: tier fijo repartido entre clientes (baja por estación al escalar).

> **Costos marginales por estación = pocos dólares al mes.** Margen de software altísimo.
> El costo real y dominante es **el tiempo de consultoría**, no la infra ni la IA.
> → Cobrar **generoso por software** (margen casi puro) y **caro por el tiempo**.

---

## 4. Modelo de pricing recomendado

### 4.1 Unidad de cobro del SaaS: **por estación + tiers**

Se descarta "por usuario": el RAG solo agrega valor si lo usan los pisteros (muchos, alta
rotación). Cobrar por usuario hace que el dueño limite accesos y mate la adopción que
sostiene la renovación. Además, el dueño **piensa por estación**, no por empleado: la
unidad de cobro debe hablar su idioma.

> **Nota de plataforma:** process-ai-core se vende como **módulo (app `process-ai`) del
> control plane `margay-workspace`**. La "estación" como unidad de cobro mapea al **tenant**
> de margay-workspace (que ya gestiona tenants, usuarios y acceso a apps). Esto habilita un
> camino de upsell natural: un mismo tenant puede contratar otros módulos de Margay
> (insights, etc.), y el costo de gestión de usuarios se comparte entre módulos en vez de
> reconstruirse por app.

### 4.2 El servicio como proyecto cerrado: "Setup de Documentación Operativa"

> Relevamos y dejamos documentados tus **N procesos críticos** (ej: 12–15), aprobados y
> cargados en la plataforma, en X semanas.

- **Entregable tangible** → fácil de aprobar para el dueño.
- **Ancla el SaaS:** el cliente termina el setup ya con contenido adentro → el mes 1 de
  suscripción ya tiene valor. Resuelve el "compré pero está vacío".
- **Define el límite:** proceso #N+1 en adelante = nuevo paquete o lo hace el cliente con
  el SaaS. Evita scope creep.

Estructura: **Setup (one-time) + suscripción mensual obligatoria desde el mes 1.**

---

## 5. Prototipo de precios (borrador para validar)

> Moneda: USD. Mercado: Uruguay / LATAM. **Anclados a valor, no a costo** — el costo
> (sección 3) confirma que el margen es amplio en todos los escalones.

### 5.1 Suscripción SaaS — por estación / mes

| Plan | Precio/mes (por estación) | Incluye | Costo marginal estimado | Margen |
|---|---|---|---|---|
| **Base** | **US$49** | Documentación con IA + versiones + aprobación + export PDF. Usuarios ilimitados. Storage de documentos (sin videos crudos). | ~US$1–3 | ~95% |
| **Pro** | **US$99** | Base + **RAG (asistente de consulta)** + más storage. | ~US$3–6 | ~94% |
| **Enterprise** | **US$199+** | Pro + **auditorías trimestrales** + soporte prioritario + consolidado multi-estación + retención de videos como evidencia. | ~US$8–15 | ~93% |

- Descuento anual sugerido: **2 meses gratis** (pago 10, usás 12) para asegurar caja y reducir churn.
- Multi-estación: descuento por volumen a partir de N estaciones (a definir; el compute se diluye).

### 5.2 Servicio — one-time

| Paquete | Precio (one-time) | Qué incluye |
|---|---|---|
| **Setup Esencial** | **US$800–1.200** | Relevamiento + documentación de **hasta 10 procesos** críticos, aprobados y cargados. |
| **Setup Completo** | **US$1.800–2.500** | Hasta **20 procesos** + configuración de roles/visibilidad + capacitación del equipo. |
| **Proceso adicional** | **US$80–120 c/u** | Por proceso extra fuera del paquete. |

> El rango del setup se cierra cuando el dogfooding dé el costo/hora real por proceso
> (sección 3.3). Piso = tiempo real × costo/hora; precio final = por valor.

### 5.3 Auditoría (recurrente, fase 2)

| Modelo | Precio | Notas |
|---|---|---|
| Auditoría trimestral | **US$300–600 por revisión** | Revisión de procesos, hallazgos, acciones correctivas, informe. Incluida en Enterprise; add-on en Base/Pro. |

### 5.4 Ejemplo de cuenta — estación típica, año 1

```
Setup Completo (one-time)............. US$2.000
Suscripción Pro (US$99 × 12)......... US$1.188
                                      ---------
Año 1.................................US$3.188
Año 2+ (solo suscripción)............US$1.188/año recurrente

Costo marginal anual estimado (IA+infra): < US$100
→ El margen lo consume el TIEMPO de Margay (setup + auditorías), no la plataforma.
```

---

## 6. Lógica de precios (cómo defender el número)

La venta no es "cuesta X generar el doc". Es:

> "¿Cuánto te cuesta reentrenar un pistero? ¿Cuánto perdés por mes en diferencias de
> arqueo? Una fracción de eso, todos los meses, y el problema deja de existir."

Anclar el precio mensual a una **fracción pequeña del dolor evitado** (rotación + mermas).
En ese marco, US$49–199/mes por estación es trivial frente al costo de **un solo** error
operativo o una recontratación.

---

## 7. Próximos pasos para fijar precios definitivos

1. **Medir en dogfooding (Margay):** tiempo real por proceso (sección 3.3) + costo de IA
   real por documento (instrumentar la tabla `Run` para registrar tokens/costo).
2. **Cerrar rangos:** con esos datos, fijar precio del Setup y los 3 escalones mensuales.
3. **Validar con GPU:** presentar Setup + suscripción y observar reacción al precio. El
   primer cliente real calibra todo.
4. **Decidir la política de videos** (sección 3.2): retención temporal por defecto;
   permanente solo en Enterprise.

---

## 8. Resumen en una línea

El sistema **agrega valor real, pero el valor se captura por adopción**: conviene vender
consultoría que deja producto operando, **cobrar generoso por software** (margen ~95%) y
**caro por el tiempo**, y medir el costo/hora en el dogfooding antes de cerrar tarifas. La
infra y la IA son ruido en la estructura de costos.
