# Generación de documentos de muestra

Fixtures de `tools/generar_documentos_muestra.py`, que genera documentos de punta
a punta —JSON → Markdown → HTML → PDF— con el renderer y el exportador reales.

```bash
python tools/generar_documentos_muestra.py            # los 10 PDFs en muestras_pdf/
python tools/generar_documentos_muestra.py --limpiar  # borrando lo anterior
python tools/generar_documentos_muestra.py --solo inferido
python tools/generar_documentos_muestra.py --salida /tmp/antes
```

## Para qué

Es el último paso antes de mergear un cambio sobre el renderer, el exportador o el
CSS. La suite en verde dice que ninguna afirmación conocida se rompió; no dice que
el documento se siga leyendo bien.

El caso que lo motivó: en el Paso 5 el perfil de gestión imprimía "Contexto" dos
veces. Ningún test lo detectó —cada pieza hacía lo suyo— y se vio recién al mirar
un documento entero.

No llama al LLM. La entrada es un fixture versionado acá, así que corre gratis y
en segundos.

## Comparar antes y después

Las dos corridas dan PDFs **byte a byte idénticos**: las fechas están fijas en el
script y el PDF sellado se normaliza (PyMuPDF le mete un `/ID` aleatorio en cada
guardado). Eso permite:

```bash
git stash && python tools/generar_documentos_muestra.py --salida /tmp/antes --limpiar
git stash pop && python tools/generar_documentos_muestra.py --salida /tmp/despues --limpiar
find /tmp/antes /tmp/despues -name '*.pdf' | xargs shasum | sort -k2 | uniq -c -w40
```

Lo que quedó con cuenta 1 cambió. Si esperabas cambiar solo la portada y te cambian
los diez, cambiaste otra cosa.

## Qué mirar

- Ninguna sección con el encabezado solo, sin contenido debajo.
- Ninguna sección repetida.
- Los chips `A VALIDAR` acompañan **solo** lo inferido.
- Las tablas de actores, riesgos e indicadores entran en el ancho de la página.
- Borrador: marca de agua, bloque de invalidación en la primera página y nota al
  pie. Aprobado: **nada** de eso.
- Superado: la banda del sello legible y sin tapar texto.
- Portada del aprobado: código, versión, fechas, vigencia y firmas con su rol.

## Los fixtures

| Archivo | Qué ejercita |
|---|---|
| `completo_relevado.json` | Todos los campos poblados, todo `relevado`. Es la referencia: si acá aparece un chip `A VALIDAR`, hay un bug. |
| `campos_en_none.json` | Lo que no se relevó llega vacío. Verifica que no queden encabezados huérfanos ni se invente contenido. |
| `inferido.json` | `campos_inferidos` más `confianza: inferido` en actores, riesgos y pasos: los chips tienen que salir en los dos lugares. |
| `con_imagenes.json` | Evidencias insertadas por el pipeline de assets, con anclas por paso. |

Agregar un escenario es agregar un JSON acá; el script lo levanta solo.

## La matriz

Cada fixture sale en los dos perfiles (`operativo`, `gestion`) en estado aprobado
—ocho PDFs de cobertura de **contenido**— más `completo_relevado` en gestión como
borrador y como superado —dos de cobertura de **estado**—. Alcanza con uno para
los estados: entre borrador, aprobado y superado lo que cambia es la portada, la
marca de invalidación y el sello, no el contenido.

La salida (`muestras_pdf/`) está en `.gitignore`: se regenera en segundos y son
artefactos binarios.
