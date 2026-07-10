/**
 * Tests del helper canónico de gating por administración de workspace.
 * Cubre la unificación de las dos condiciones dispersas:
 *   - settings/page.tsx  (isSuperadmin || canEditWorkspace || owner || admin)
 *   - workspace/page.tsx (superadmin en platformRoles || owner || creator || admin)
 */
import { describe, it, expect } from "vitest";
import { canAdministerWorkspace } from "../adminGating";

// ─── Superadmin ─────────────────────────────────────────────────────────────

describe("canAdministerWorkspace — superadmin", () => {
  it("accede vía flag isSuperadmin", () => {
    expect(canAdministerWorkspace({ isSuperadmin: true, workspaceRole: "member" })).toBe(true);
  });

  it("accede vía platformRoles includes 'superadmin'", () => {
    expect(
      canAdministerWorkspace({ platformRoles: ["superadmin", "user"], workspaceRole: "member" })
    ).toBe(true);
  });

  it("NO accede si isSuperadmin es false y platformRoles no incluye superadmin", () => {
    expect(
      canAdministerWorkspace({
        isSuperadmin: false,
        platformRoles: ["user"],
        workspaceRole: "member",
      })
    ).toBe(false);
  });

  it("isSuperadmin false + platformRoles vacío + sin rol → false", () => {
    expect(
      canAdministerWorkspace({ isSuperadmin: false, platformRoles: [] })
    ).toBe(false);
  });
});

// ─── Permiso granular ────────────────────────────────────────────────────────

describe("canAdministerWorkspace — canEditWorkspace", () => {
  it("accede con canEditWorkspace true aunque el rol sea 'member'", () => {
    expect(
      canAdministerWorkspace({ workspaceRole: "member", canEditWorkspace: true })
    ).toBe(true);
  });

  it("canEditWorkspace false no otorga acceso por sí solo", () => {
    expect(
      canAdministerWorkspace({ workspaceRole: "member", canEditWorkspace: false })
    ).toBe(false);
  });
});

// ─── Roles de workspace ──────────────────────────────────────────────────────

describe("canAdministerWorkspace — workspaceRole", () => {
  it("owner tiene acceso", () => {
    expect(canAdministerWorkspace({ workspaceRole: "owner" })).toBe(true);
  });

  it("creator tiene acceso", () => {
    expect(canAdministerWorkspace({ workspaceRole: "creator" })).toBe(true);
  });

  it("admin tiene acceso", () => {
    expect(canAdministerWorkspace({ workspaceRole: "admin" })).toBe(true);
  });

  it("member NO tiene acceso", () => {
    expect(canAdministerWorkspace({ workspaceRole: "member" })).toBe(false);
  });

  it("viewer NO tiene acceso", () => {
    expect(canAdministerWorkspace({ workspaceRole: "viewer" })).toBe(false);
  });

  it("workspaceRole null → false (sin otros permisos)", () => {
    expect(canAdministerWorkspace({ workspaceRole: null })).toBe(false);
  });

  it("workspaceRole undefined → false (sin otros permisos)", () => {
    expect(canAdministerWorkspace({})).toBe(false);
  });
});

// ─── Combinaciones ───────────────────────────────────────────────────────────

describe("canAdministerWorkspace — combinaciones", () => {
  it("member con canEditWorkspace=true accede (patrón settings page)", () => {
    expect(
      canAdministerWorkspace({
        isSuperadmin: false,
        platformRoles: ["user"],
        workspaceRole: "member",
        canEditWorkspace: true,
      })
    ).toBe(true);
  });

  it("admin sin canEditWorkspace accede (patrón workspace page)", () => {
    expect(
      canAdministerWorkspace({
        platformRoles: ["user"],
        workspaceRole: "admin",
        canEditWorkspace: false,
      })
    ).toBe(true);
  });

  it("sin ninguna flag → false", () => {
    expect(
      canAdministerWorkspace({
        isSuperadmin: false,
        platformRoles: [],
        workspaceRole: "viewer",
        canEditWorkspace: false,
      })
    ).toBe(false);
  });
});
