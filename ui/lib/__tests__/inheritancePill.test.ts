/**
 * Tests de la función pura deriveInheritancePill.
 * Importa solo la lógica pura, sin tocar DOM ni React.
 */
import { describe, it, expect } from "vitest";
import { deriveInheritancePill } from "../inheritancePill";

describe("deriveInheritancePill — kind: base", () => {
  it('devuelve label "Configuración base"', () => {
    const result = deriveInheritancePill({ kind: "base" });
    expect(result.label).toBe("Configuración base");
  });

  it('devuelve variant "base"', () => {
    const result = deriveInheritancePill({ kind: "base" });
    expect(result.variant).toBe("base");
  });

  it("ignora el campo `from` cuando kind es base", () => {
    const result = deriveInheritancePill({ kind: "base", from: "Carpeta X" });
    expect(result.label).toBe("Configuración base");
  });
});

describe("deriveInheritancePill — kind: inherited", () => {
  it('con `from` devuelve "Heredado de [nombre]"', () => {
    const result = deriveInheritancePill({ kind: "inherited", from: "Carpeta Raíz" });
    expect(result.label).toBe("Heredado de Carpeta Raíz");
  });

  it('sin `from` devuelve "Heredado" (fallback seguro)', () => {
    const result = deriveInheritancePill({ kind: "inherited" });
    expect(result.label).toBe("Heredado");
  });

  it('devuelve variant "inherited"', () => {
    const result = deriveInheritancePill({ kind: "inherited", from: "X" });
    expect(result.variant).toBe("inherited");
  });

  it("interpola correctamente nombres con espacios", () => {
    const result = deriveInheritancePill({ kind: "inherited", from: "Operaciones Norte" });
    expect(result.label).toBe("Heredado de Operaciones Norte");
  });
});

describe("deriveInheritancePill — kind: custom", () => {
  it('devuelve label "Personalizado"', () => {
    const result = deriveInheritancePill({ kind: "custom" });
    expect(result.label).toBe("Personalizado");
  });

  it('devuelve variant "custom"', () => {
    const result = deriveInheritancePill({ kind: "custom" });
    expect(result.variant).toBe("custom");
  });

  it("ignora el campo `from` cuando kind es custom", () => {
    const result = deriveInheritancePill({ kind: "custom", from: "Carpeta Y" });
    expect(result.label).toBe("Personalizado");
  });
});
