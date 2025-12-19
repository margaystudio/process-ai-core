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

## Modelo de Datos Multi-Dominio

### Problema

- **Documentación de procesos**: Necesita `Client` (organización) → `Process` → `Run`
- **Recetas**: ¿Necesita `User` individual? ¿`Community`? ¿`Chef`?

### Solución: Workspace Genérico

Refactorizar el modelo actual para usar un concepto genérico de **Workspace** (tenant) que puede representar:

1. **Organización/Cliente** (para procesos)
2. **Usuario individual** (para recetas personales)
3. **Comunidad/Grupo** (para recetas compartidas)

```python
# db/models.py (genérico)

class Workspace(Base):
    """
    Workspace genérico (tenant) que puede ser:
    - Una organización/cliente (para procesos)
    - Un usuario individual (para recetas personales)
    - Una comunidad/grupo (para recetas compartidas)
    """
    __tablename__ = "workspaces"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    
    # Tipo de workspace
    workspace_type: Mapped[str] = mapped_column(String(20))  # "organization" | "user" | "community"
    
    # Metadata genérica (JSON flexible)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones genéricas
    documents: Mapped[list["Document"]] = relationship(back_populates="workspace")


class Document(Base):
    """
    Documento genérico que puede ser:
    - Process (para dominio de procesos)
    - Recipe (para dominio de recetas)
    """
    __tablename__ = "documents"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)
    
    # Tipo de documento (determina qué dominio usar)
    domain: Mapped[str] = mapped_column(String(20))  # "process" | "recipe"
    
    # Nombre del documento
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    
    # Metadata específica del dominio (JSON)
    domain_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    workspace: Mapped["Workspace"] = relationship(back_populates="documents")
    runs: Mapped[list["Run"]] = relationship(back_populates="document")


class Run(Base):
    """
    Ejecución genérica del motor (funciona para cualquier dominio).
    """
    __tablename__ = "runs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    
    # Dominio de esta ejecución
    domain: Mapped[str] = mapped_column(String(20))  # "process" | "recipe"
    
    # Perfil usado (específico del dominio)
    profile: Mapped[str] = mapped_column(String(50), default="")
    
    # Inputs de la corrida
    input_manifest_json: Mapped[str] = mapped_column(Text, default="{}")
    
    # Trazabilidad
    prompt_hash: Mapped[str] = mapped_column(String(64), default="")
    model_text: Mapped[str] = mapped_column(String(100), default="")
    model_transcribe: Mapped[str] = mapped_column(String(100), default="")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    document: Mapped["Document"] = relationship(back_populates="runs")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="run")
```

### Modelo Específico: Recetas

Para el dominio de recetas, el `Workspace` puede ser:

```python
# Ejemplo: Workspace para recetas
workspace = Workspace(
    workspace_type="user",  # Usuario individual
    name="Juan Pérez",
    slug="juan-perez",
    metadata_json='{"preferences": {"cuisine": "italian", "diet": "vegetarian"}}'
)

# O para una comunidad:
workspace = Workspace(
    workspace_type="community",
    name="Chefs Uruguayos",
    slug="chefs-uy",
    metadata_json='{"members": [...], "visibility": "public"}'
)

# Documento de receta
document = Document(
    domain="recipe",
    name="Pasta Carbonara",
    workspace_id=workspace.id,
    domain_metadata_json='{"cuisine": "italian", "difficulty": "medium", "servings": 4}'
)
```

### Modelo Específico: Procesos

Para procesos, el `Workspace` es una organización:

```python
# Workspace para procesos
workspace = Workspace(
    workspace_type="organization",
    name="Acme Corp",
    slug="acme",
    metadata_json='{"business_type": "retail", "country": "UY"}'
)

# Documento de proceso
document = Document(
    domain="process",
    name="Recepción de mercadería",
    workspace_id=workspace.id,
    domain_metadata_json='{"process_type": "operativo", "audience": "pistero"}'
)
```

### Usuarios y Autenticación

```python
class User(Base):
    """Usuario del sistema (autenticación/autorización)."""
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    
    # Relación con workspaces (un usuario puede tener múltiples workspaces)
    workspace_memberships: Mapped[list["WorkspaceMembership"]] = relationship()


class WorkspaceMembership(Base):
    """Relación muchos-a-muchos entre User y Workspace."""
    __tablename__ = "workspace_memberships"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)
    
    # Rol del usuario en el workspace
    role: Mapped[str] = mapped_column(String(20))  # "owner" | "admin" | "member" | "viewer"
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

### Ventajas de este Modelo

✅ **Genérico**: Un solo modelo funciona para ambos dominios
✅ **Flexible**: `metadata_json` permite campos específicos sin migraciones
✅ **Escalable**: Fácil agregar nuevos dominios (ej: "tutorials", "manuals")
✅ **Multi-tenant**: Soporta organizaciones, usuarios individuales y comunidades
✅ **Colaboración**: `WorkspaceMembership` permite compartir documentos

### Migración

1. **Fase 1**: Crear nuevas tablas (`Workspace`, `Document`, `User`, `WorkspaceMembership`)
2. **Fase 2**: Migrar datos de `Client` → `Workspace`, `Process` → `Document`
3. **Fase 3**: Deprecar tablas viejas (mantener compatibilidad temporal)
4. **Fase 4**: Eliminar tablas viejas

## Consideraciones

- Los modelos genéricos (`RawAsset`, `EnrichedAsset`) quedan en el root
- `llm_client.py` puede necesitar ser genérico (no solo `generate_process_document_json`)
- Los perfiles de documento son específicos de cada dominio
- La API HTTP puede tener endpoints por dominio o un endpoint genérico con parámetro de dominio
- El modelo de datos usa `Workspace` genérico en lugar de `Client` específico

