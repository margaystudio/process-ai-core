/**
 * Selector de acciones del documento — fuente ÚNICA de verdad sobre qué puede
 * hacer el usuario con un documento, dado su estado + versiones + identidad +
 * permisos efectivos (con el bypass de superadmin ya resuelto por el caller).
 *
 * Reemplaza la lógica dispersa de `documentPermissions` + cálculos inline de la
 * ficha, que combinaba ~10 variables y producía condiciones de carrera (un draft
 * cuyo creador/superadmin no veía "Enviar a revisión").
 *
 * Función PURA y testeable: misma entrada → misma salida. La ficha solo consume
 * `getDocumentActions(...)` y nunca recalcula reglas inline.
 */

import type { DocumentStatus } from './documentPermissions';

export interface DocumentActionsInput {
  /** Estado del documento. */
  status: DocumentStatus;
  /** ¿Existe una versión en estado DRAFT? */
  hasDraftVersion: boolean;
  /** ¿Existe una versión en estado IN_REVIEW? */
  hasInReviewVersion: boolean;
  /** ID local del usuario actual (null si todavía no cargó). */
  userId: string | null;
  /** `created_by` de la versión DRAFT (null si no hay/no cargó). */
  draftCreatedBy: string | null;
  /** `created_by` de la versión IN_REVIEW (null si no hay/no cargó). */
  inReviewCreatedBy: string | null;
  /** Permiso efectivo documents.approve (incluye bypass de superadmin). */
  canApprovePermission: boolean;
  /** Permiso efectivo documents.reject. */
  canRejectPermission: boolean;
  /** Permiso efectivo documents.edit. */
  canEditPermission: boolean;
  /** Permiso efectivo documents.delete. */
  canDeletePermission: boolean;
}

export interface DocumentActions {
  canSubmitForReview: boolean;
  canApprove: boolean;
  canReject: boolean;
  canCancelSubmission: boolean;
  canEditMetadata: boolean;
  canCreateNewVersion: boolean;
  canDelete: boolean;
}

function isCreatorOf(userId: string | null, createdBy: string | null): boolean {
  return Boolean(userId && createdBy && userId === createdBy);
}

export function getDocumentActions(input: DocumentActionsInput): DocumentActions {
  const {
    status,
    hasDraftVersion,
    hasInReviewVersion,
    userId,
    draftCreatedBy,
    inReviewCreatedBy,
    canApprovePermission,
    canRejectPermission,
    canEditPermission,
    canDeletePermission,
  } = input;

  const isCreatorOfDraft = isCreatorOf(userId, draftCreatedBy);
  const isCreatorOfInReview = isCreatorOf(userId, inReviewCreatedBy);

  // Enviar a revisión: hay un DRAFT y el usuario es su creador O tiene permiso de
  // edición de documentos (incluye superadmin). Este es el caso que rompía (D4).
  const canSubmitForReview =
    status === 'draft' && hasDraftVersion && (isCreatorOfDraft || canEditPermission);

  // Aprobar / rechazar: documento pendiente, hay versión IN_REVIEW, el usuario
  // tiene el permiso y NO es el creador de esa versión (segregación creador≠aprobador).
  const canApprove =
    status === 'pending_validation' &&
    hasInReviewVersion &&
    canApprovePermission &&
    !isCreatorOfInReview;

  const canReject =
    status === 'pending_validation' &&
    hasInReviewVersion &&
    canRejectPermission &&
    !isCreatorOfInReview;

  // Cancelar envío (volver a borrador): solo el creador de la versión en revisión.
  const canCancelSubmission =
    status === 'pending_validation' && hasInReviewVersion && isCreatorOfInReview;

  // Editar metadatos: en borrador o pendiente, por el creador (de draft o in-review)
  // o quien tenga permiso de edición.
  const canEditMetadata =
    (status === 'draft' || status === 'pending_validation') &&
    (isCreatorOfDraft || isCreatorOfInReview || canEditPermission);

  // Nueva versión: solo desde un documento ya resuelto (aprobado o rechazado).
  const canCreateNewVersion = status === 'approved' || status === 'rejected';

  return {
    canSubmitForReview,
    canApprove,
    canReject,
    canCancelSubmission,
    canEditMetadata,
    canCreateNewVersion,
    canDelete: canDeletePermission,
  };
}
