/**
 * Tests del selector de acciones del documento.
 * Ejecutar con: npx vitest run lib/__tests__/documentActions.test.ts
 */
import { describe, it, expect } from 'vitest';
import { getDocumentActions, type DocumentActionsInput } from '../documentActions';

/** Entrada base sin permisos ni versiones; cada test sobreescribe lo necesario. */
function base(overrides: Partial<DocumentActionsInput> = {}): DocumentActionsInput {
  return {
    status: 'draft',
    hasDraftVersion: false,
    hasInReviewVersion: false,
    userId: null,
    draftCreatedBy: null,
    inReviewCreatedBy: null,
    canApprovePermission: false,
    canRejectPermission: false,
    canEditPermission: false,
    canDeletePermission: false,
    ...overrides,
  };
}

describe('getDocumentActions — Enviar a revisión (caso D4)', () => {
  it('el CREADOR del draft puede enviar a revisión (sin otros permisos)', () => {
    const a = getDocumentActions(base({
      status: 'draft',
      hasDraftVersion: true,
      userId: 'u1',
      draftCreatedBy: 'u1',
    }));
    expect(a.canSubmitForReview).toBe(true);
  });

  it('quien tiene documents.edit (ej. superadmin) puede enviar aunque NO sea el creador', () => {
    const a = getDocumentActions(base({
      status: 'draft',
      hasDraftVersion: true,
      userId: 'u1',
      draftCreatedBy: 'u2',
      canEditPermission: true,
    }));
    expect(a.canSubmitForReview).toBe(true);
  });

  it('NO puede enviar si no es creador ni tiene permiso de edición', () => {
    const a = getDocumentActions(base({
      status: 'draft',
      hasDraftVersion: true,
      userId: 'u1',
      draftCreatedBy: 'u2',
    }));
    expect(a.canSubmitForReview).toBe(false);
  });

  it('NO puede enviar si no hay versión DRAFT', () => {
    const a = getDocumentActions(base({
      status: 'draft',
      hasDraftVersion: false,
      userId: 'u1',
      draftCreatedBy: 'u1',
    }));
    expect(a.canSubmitForReview).toBe(false);
  });

  it('NO puede enviar si el documento no está en borrador', () => {
    const a = getDocumentActions(base({
      status: 'pending_validation',
      hasDraftVersion: true,
      userId: 'u1',
      draftCreatedBy: 'u1',
    }));
    expect(a.canSubmitForReview).toBe(false);
  });
});

describe('getDocumentActions — Aprobar / Rechazar (segregación)', () => {
  it('un aprobador puede aprobar/rechazar una versión que NO creó', () => {
    const a = getDocumentActions(base({
      status: 'pending_validation',
      hasInReviewVersion: true,
      userId: 'approver',
      inReviewCreatedBy: 'creator',
      canApprovePermission: true,
      canRejectPermission: true,
    }));
    expect(a.canApprove).toBe(true);
    expect(a.canReject).toBe(true);
  });

  it('el CREADOR de la versión NO puede aprobar la suya (segregación)', () => {
    const a = getDocumentActions(base({
      status: 'pending_validation',
      hasInReviewVersion: true,
      userId: 'creator',
      inReviewCreatedBy: 'creator',
      canApprovePermission: true,
      canRejectPermission: true,
    }));
    expect(a.canApprove).toBe(false);
    expect(a.canReject).toBe(false);
  });

  it('sin permiso de aprobación no puede aprobar', () => {
    const a = getDocumentActions(base({
      status: 'pending_validation',
      hasInReviewVersion: true,
      userId: 'x',
      inReviewCreatedBy: 'creator',
    }));
    expect(a.canApprove).toBe(false);
  });
});

describe('getDocumentActions — Cancelar envío / Nueva versión', () => {
  it('el creador de la versión en revisión puede cancelar el envío', () => {
    const a = getDocumentActions(base({
      status: 'pending_validation',
      hasInReviewVersion: true,
      userId: 'creator',
      inReviewCreatedBy: 'creator',
    }));
    expect(a.canCancelSubmission).toBe(true);
  });

  it('nueva versión solo desde aprobado o rechazado', () => {
    expect(getDocumentActions(base({ status: 'approved' })).canCreateNewVersion).toBe(true);
    expect(getDocumentActions(base({ status: 'rejected' })).canCreateNewVersion).toBe(true);
    expect(getDocumentActions(base({ status: 'draft' })).canCreateNewVersion).toBe(false);
  });
});

describe('getDocumentActions — robustez ante carga async', () => {
  it('con userId nulo y sin permisos, no habilita acciones de creador (no rompe)', () => {
    const a = getDocumentActions(base({
      status: 'draft',
      hasDraftVersion: true,
      userId: null,
      draftCreatedBy: 'u1',
    }));
    expect(a.canSubmitForReview).toBe(false);
    expect(a.canEditMetadata).toBe(false);
  });
});
