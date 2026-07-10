/**
 * Tests del reducer puro de useAsync.
 * Verifica todas las transiciones de estado sin DOM ni hooks.
 */
import { describe, it, expect } from "vitest";
import { asyncReducer, initialAsyncState, type AsyncState } from "../../hooks/useAsync";

function idle<T>(): AsyncState<T> {
  return initialAsyncState<T>();
}

describe("asyncReducer — LOADING", () => {
  it("cambia status a loading desde idle", () => {
    const next = asyncReducer(idle(), { type: "LOADING" });
    expect(next.status).toBe("loading");
  });

  it("preserva data previa al entrar en loading (no flickea)", () => {
    const withData: AsyncState<string[]> = {
      status: "success",
      data: ["item"],
      error: null,
    };
    const next = asyncReducer(withData, { type: "LOADING" });
    expect(next.data).toEqual(["item"]);
    expect(next.error).toBeNull();
  });

  it("limpia error previo al entrar en loading", () => {
    const withError: AsyncState<null> = {
      status: "error",
      data: null,
      error: "Error anterior",
    };
    const next = asyncReducer(withError, { type: "LOADING" });
    expect(next.error).toBeNull();
  });
});

describe("asyncReducer — SUCCESS", () => {
  it("pasa a success y guarda data", () => {
    const next = asyncReducer(idle<number[]>(), { type: "SUCCESS", data: [1, 2, 3] });
    expect(next.status).toBe("success");
    expect(next.data).toEqual([1, 2, 3]);
  });

  it("success con array vacío NO es idle ni error (distinto semántico)", () => {
    const next = asyncReducer(idle<string[]>(), { type: "SUCCESS", data: [] });
    expect(next.status).toBe("success");
    expect(next.data).toEqual([]);
  });

  it("success con null data (ej. recurso no encontrado) no rompe", () => {
    const next = asyncReducer(idle<string | null>(), { type: "SUCCESS", data: null });
    expect(next.status).toBe("success");
    expect(next.data).toBeNull();
  });

  it("limpia error previo", () => {
    const withError: AsyncState<string> = {
      status: "error",
      data: null,
      error: "algo falló",
    };
    const next = asyncReducer(withError, { type: "SUCCESS", data: "ok" });
    expect(next.error).toBeNull();
  });
});

describe("asyncReducer — ERROR", () => {
  it("pasa a error con el mensaje", () => {
    const next = asyncReducer(idle(), { type: "ERROR", error: "No autorizado" });
    expect(next.status).toBe("error");
    expect(next.error).toBe("No autorizado");
  });

  it("limpia data al entrar en error", () => {
    const withData: AsyncState<string[]> = {
      status: "success",
      data: ["algo"],
      error: null,
    };
    const next = asyncReducer(withData, { type: "ERROR", error: "fallo" });
    expect(next.data).toBeNull();
  });
});

describe("asyncReducer — RESET", () => {
  it("vuelve a idle desde success", () => {
    const withData: AsyncState<string> = {
      status: "success",
      data: "ok",
      error: null,
    };
    const next = asyncReducer(withData, { type: "RESET" });
    expect(next.status).toBe("idle");
    expect(next.data).toBeNull();
    expect(next.error).toBeNull();
  });

  it("vuelve a idle desde error", () => {
    const withError: AsyncState<null> = {
      status: "error",
      data: null,
      error: "algo falló",
    };
    const next = asyncReducer(withError, { type: "RESET" });
    expect(next.status).toBe("idle");
    expect(next.error).toBeNull();
  });
});

describe("asyncReducer — estado inicial", () => {
  it("initialAsyncState devuelve idle sin data ni error", () => {
    const state = initialAsyncState<string[]>();
    expect(state.status).toBe("idle");
    expect(state.data).toBeNull();
    expect(state.error).toBeNull();
  });
});

describe("asyncReducer — transición completa (idle → loading → success → reset)", () => {
  it("ejecuta el ciclo completo correctamente", () => {
    let state = idle<string[]>();
    state = asyncReducer(state, { type: "LOADING" });
    expect(state.status).toBe("loading");

    state = asyncReducer(state, { type: "SUCCESS", data: ["a", "b"] });
    expect(state.status).toBe("success");
    expect(state.data).toEqual(["a", "b"]);

    state = asyncReducer(state, { type: "RESET" });
    expect(state.status).toBe("idle");
  });

  it("ciclo con error y retry: loading → error → loading → success", () => {
    let state = idle<number>();
    state = asyncReducer(state, { type: "LOADING" });
    state = asyncReducer(state, { type: "ERROR", error: "timeout" });
    expect(state.status).toBe("error");

    // retry
    state = asyncReducer(state, { type: "LOADING" });
    expect(state.status).toBe("loading");
    expect(state.error).toBeNull(); // error limpiado

    state = asyncReducer(state, { type: "SUCCESS", data: 42 });
    expect(state.status).toBe("success");
    expect(state.data).toBe(42);
  });
});
