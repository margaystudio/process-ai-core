# Propuesta de Arquitectura: Core Genérico + Dominios

## Objetivo

Separar el motor de documentación genérico (reutilizable) de la lógica específica de cada dominio (procesos, recetas, etc.).

## Estructura Propuesta

```
process_ai_core/
├── core/                          # Motor genérico (reutilizable)
│   ├── media.py                   # Transcripción, extracción de frames
│   ├── llm_client.py              # Comunicación con OpenAI
│   ├── ingest.py                  # Descubrimiento de assets
│   ├── export/                    # Exportación (PDF, etc.)
│   └── engine.py                  # Orquestador genérico
│
├── domains/                       # Lógica específica por dominio
│   ├── processes/                 # Dominio: Documentación de procesos
│   │   ├── models.py              # ProcessDocument, Step
│   │   ├── prompts.py             # Prompts específicos de procesos
│   │   ├── parser.py              # parse_process_document
│   │   ├── renderer.py            # render_markdown para procesos
│   │   └── profiles.py            # DocumentProfile para procesos
│   │
│   └── recipes/                   # Dominio: Recetas de cocina
│       ├── models.py              # RecipeDocument, Ingredient, Instruction
│       ├── prompts.py             # Prompts específicos de recetas
│       ├── parser.py              # parse_recipe_document
│       ├── renderer.py            # render_markdown para recetas
│       └── profiles.py            # DocumentProfile para recetas
│
└── domain_models.py               # Modelos genéricos (RawAsset, EnrichedAsset)
```

## Abstracciones (Protocols/Interfaces)

### DocumentBuilder

Cada dominio implementa cómo construir el prompt y parsear el JSON:

```python
from typing import Protocol

class DocumentBuilder(Protocol):
    """Interfaz que cada dominio debe implementar."""
    
    def build_prompt(
        self, 
        document_name: str, 
        enriched_assets: List[EnrichedAsset]
    ) -> str:
        """Construye el prompt para el LLM."""
        ...
    
    def parse_document(self, json_str: str) -> Any:
        """Parsea el JSON del LLM a un modelo tipado del dominio."""
        ...
    
    def get_system_prompt(self) -> str:
        """Devuelve el prompt del sistema para este dominio."""
        ...
```

### DocumentRenderer

Cada dominio implementa cómo renderizar su documento:

```python
class DocumentRenderer(Protocol):
    """Interfaz para renderizar documentos según el dominio."""
    
    def render_markdown(
        self,
        document: Any,  # Tipo específico del dominio
        profile: Any,   # Perfil específico del dominio
        images_by_step: Dict[int, List[Dict[str, str]]],
        evidence_images: List[Dict[str, str]],
        output_base: Path | None = None,
    ) -> str:
        """Renderiza el documento a Markdown."""
        ...
```

## Engine Genérico

El `engine.py` se vuelve genérico y acepta un `DocumentBuilder`:

```python
def run_documentation_pipeline(
    *,
    document_name: str,
    raw_assets: Sequence[RawAsset],
    builder: DocumentBuilder,
    renderer: DocumentRenderer,
    profile: Any,  # Perfil específico del dominio
    context_block: str | None = None,
    output_base: Path | None = None,
) -> DocumentRunResult:
    """
    Pipeline genérico que funciona para cualquier dominio.
    
    Flujo:
    1. Enriquecer assets (genérico)
    2. Construir prompt (específico del dominio via builder)
    3. LLM → JSON (genérico)
    4. Parsear documento (específico del dominio via builder)
    5. Renderizar (específico del dominio via renderer)
    """
    # 1) Enriquecer (genérico)
    enriched, images_by_step, evidence_images = enrich_assets(
        list(raw_assets), output_base=output_base
    )
    
    # 2) Construir prompt (específico)
    prompt_body = builder.build_prompt(document_name, enriched)
    prompt = f"{context_block}{prompt_body}" if context_block else prompt_body
    
    # 3) LLM → JSON (genérico)
    json_str = generate_process_document_json(prompt)
    
    # 4) Parsear (específico)
    doc = builder.parse_document(json_str)
    
    # 5) Renderizar (específico)
    markdown = renderer.render_markdown(
        doc, profile, images_by_step, evidence_images, output_base
    )
    
    return DocumentRunResult(
        json_str=json_str,
        doc=doc,
        markdown=markdown,
        images_by_step=images_by_step,
        evidence_images=evidence_images,
    )
```

## Ejemplo: Dominio de Recetas

```python
# domains/recipes/models.py
@dataclass
class Ingredient:
    name: str
    quantity: str
    unit: str

@dataclass
class Instruction:
    order: int
    description: str
    duration: str | None
    temperature: str | None

@dataclass
class RecipeDocument:
    recipe_name: str
    description: str
    servings: int
    prep_time: str
    cook_time: str
    ingredients: List[Ingredient]
    instructions: List[Instruction]
    tips: str
    nutrition_info: str

# domains/recipes/prompts.py
RECIPE_SYSTEM_PROMPT = """
Sos un chef experto que genera recetas de cocina...
"""

# domains/recipes/builder.py
class RecipeBuilder:
    def build_prompt(self, recipe_name: str, enriched_assets: List[EnrichedAsset]) -> str:
        # Similar a build_prompt_from_enriched pero para recetas
        ...
    
    def parse_document(self, json_str: str) -> RecipeDocument:
        # Parsea JSON específico de recetas
        ...
```

## Migración Gradual

1. **Fase 1**: Crear estructura `domains/processes/` y mover código actual
2. **Fase 2**: Refactorizar `engine.py` para ser genérico
3. **Fase 3**: Crear `domains/recipes/` como ejemplo del nuevo dominio
4. **Fase 4**: Actualizar APIs/CLIs para usar la nueva estructura

## Ventajas

✅ **Reutilización**: El core (media, llm, ingest, export) se usa en todos los dominios
✅ **Separación de responsabilidades**: Cada dominio define su propia estructura
✅ **Extensibilidad**: Agregar un nuevo dominio es solo crear una nueva carpeta
✅ **Mantenibilidad**: Cambios en un dominio no afectan a otros
✅ **Testing**: Se puede testear el core genérico independientemente

## Consideraciones

- Los modelos genéricos (`RawAsset`, `EnrichedAsset`) quedan en el root
- `llm_client.py` puede necesitar ser genérico (no solo `generate_process_document_json`)
- Los perfiles de documento son específicos de cada dominio
- La API HTTP puede tener endpoints por dominio o un endpoint genérico con parámetro de dominio

