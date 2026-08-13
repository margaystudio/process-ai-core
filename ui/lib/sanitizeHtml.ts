/**
 * Sanitización del HTML de documentos antes de renderizarlo en modo lectura
 * (`dangerouslySetInnerHTML`).
 *
 * El HTML de un documento se persiste vía `saveEditableContent` y puede venir
 * de tres fuentes no confiables: el editor Tiptap (usuarios del workspace con
 * permiso de edición), contenido generado por IA, o — si el backend cambia —
 * cualquier otro productor. Nunca hay que asumir que "vino de Tiptap" es
 * suficiente: Tiptap sanea la EDICIÓN, no la LECTURA. Este helper es la única
 * puerta de entrada segura para pintar ese HTML fuera del editor.
 *
 * Allow-list explícita, NO la config default de DOMPurify: solo los tags y
 * atributos que el editor (`components/documents/ManualEditorTiptap.tsx`)
 * realmente produce (ver extensiones de StarterKit + Link + Image + Table).
 */
import DOMPurify from "dompurify";

/**
 * Tags que el editor Tiptap puede producir:
 * - StarterKit: p, headings (niveles 1-4, ver `heading: { levels: [1,2,3,4] }`),
 *   ul/ol/li, strong, em, u, s (marks), blockquote, code (inline) y pre>code
 *   (bloque de código), br, hr.
 * - Link → a
 * - Image → img
 * - Table/TableRow/TableHeader/TableCell → table/thead/tbody/tr/th/td
 * - span/div: Tiptap los usa para envolturas con `class` (p. ej. nodeviews de
 *   tabla); no los produce StarterKit por sí solo pero los dejamos por si
 *   contenido legítimo los trae con una clase utilitaria.
 */
const ALLOWED_TAGS = [
  "h1",
  "h2",
  "h3",
  "h4",
  "p",
  "ul",
  "ol",
  "li",
  "strong",
  "em",
  "u",
  "s",
  "a",
  "img",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "blockquote",
  "code",
  "pre",
  "br",
  "hr",
  "span",
  "div",
];

/**
 * Atributos mínimos que el editor produce. Notar que NO incluye `style`
 * (prohibido explícitamente: es el vector de `url()` / expresiones CSS) ni
 * ningún `on*` (DOMPurify los remueve siempre, no hace falta listarlos).
 * `rel` se agrega porque el `Link` del editor lo fija (`rel="noopener"`) y
 * queremos que sobreviva; es un atributo de solo-lectura inocuo.
 */
const ALLOWED_ATTR = [
  "href",
  "src",
  "alt",
  "title",
  "class",
  "colspan",
  "rowspan",
  "rel",
];

/**
 * Esquemas de URL permitidos para `href`/`src`: http, https y rutas
 * relativas (sin esquema, p. ej. `/api/doc-assets/...` que sirve el proxy de
 * imágenes del front). Deliberadamente NO incluye `data:` acá — eso se
 * habilita aparte, solo para `img src`, vía el hook de abajo — ni
 * `javascript:`, `vbscript:`, `mailto:`, etc.
 *
 * Adaptado del regex default de DOMPurify pero restringido a http/https
 * (el default también permite mailto/tel/sms/cid/xmpp, que no necesitamos).
 */
const SAFE_URI_REGEXP =
  /^(?:(?:https?):|[^a-z]|[a-z\d+.\-]+(?:[^a-z\d+.\-:]|$))/i;

/**
 * `data:image/*;base64,...` permitido ÚNICAMENTE como `src` de `<img>`
 * (nunca en `href` de `<a>`, ni siquiera con esta forma). Restringido a
 * base64 de formatos raster conocidos — así evitamos `data:image/svg+xml,`
 * con XML plano (donde alguien podría intentar colar markup) y cualquier
 * variante de `data:text/html` o similar.
 */
const DATA_IMAGE_SRC_REGEXP =
  /^data:image\/(?:png|jpe?g|gif|webp|bmp|avif);base64,[a-z0-9+/]+=*$/i;

let hooksInstalled = false;

/** Instala los hooks una sola vez (DOMPurify los comparte a nivel de módulo). */
function ensureHooks() {
  if (hooksInstalled) return;
  hooksInstalled = true;

  DOMPurify.addHook("uponSanitizeAttribute", (node, data) => {
    if (data.attrName !== "src" && data.attrName !== "href") return;

    const isDataUri = /^data:/i.test(data.attrValue.trim());
    if (!isDataUri) return;

    // DOMPurify permite `data:` en `src`/`href` de ciertos tags (img, video,
    // audio, source, image, track) SIN pasar por `ALLOWED_URI_REGEXP` — es
    // comportamiento default suyo (`DATA_URI_TAGS`), no algo que hayamos
    // configurado. Lo revertimos acá: solo `<img src>` puede llevar `data:`,
    // y solo si matchea el raster-base64 estricto de abajo. Cualquier otro
    // caso (incluido `href`, o un `data:` no-raster) se descarta.
    if (
      data.attrName === "src" &&
      node.tagName === "IMG" &&
      DATA_IMAGE_SRC_REGEXP.test(data.attrValue)
    ) {
      data.forceKeepAttr = true;
    } else {
      data.keepAttr = false;
    }
  });
}

/**
 * Sanea HTML de documento para render en modo lectura. Devuelve un string
 * seguro para `dangerouslySetInnerHTML`.
 */
export function sanitizeDocumentHtml(html: string): string {
  if (!html) return "";

  // Sin DOM no hay saneo posible, así que no se devuelve nada: fail-closed.
  // No es un caso que se dé hoy (el cuerpo del documento se pide desde el
  // cliente, así que en SSR `html` ya viene vacío y se corta arriba), pero si
  // alguna vez llegara contenido en el servidor, devolver el HTML sin sanear
  // sería exactamente el agujero que este módulo viene a tapar. Se usa
  // `dompurify` y no `isomorphic-dompurify` a propósito: este render es de
  // navegador, y la variante isomórfica arrastra jsdom al bundle del cliente.
  if (typeof window === "undefined") return "";

  ensureHooks();

  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOWED_URI_REGEXP: SAFE_URI_REGEXP,
    // Defensa en profundidad: explícitos aunque ya estén fuera de ALLOWED_TAGS/ATTR.
    FORBID_TAGS: ["script", "style", "iframe", "object", "embed", "svg", "math"],
    FORBID_ATTR: ["style"],
    ALLOW_DATA_ATTR: false,
    // No queremos <html>/<head>/<body> ni comentarios/CDATA con payloads.
    WHOLE_DOCUMENT: false,
  }) as string;
}
