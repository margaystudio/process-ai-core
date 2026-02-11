/**
 * Helpers de permisos para la pantalla de detalle del documento.
 * Centralizan la lógica de qué acciones puede hacer cada rol según estado.
 */

export type DocumentStatus =
  | 'draft'
  | 'pending_validation'
  | 'approved'
  | 'rejected'
  | 'archived';

/** Rol del usuario en el contexto del documento (respecto a la versión en revisión). */
export type DocumentRole = 'creator' | 'approver' | 'viewer';

/**
 * Determina el rol del usuario:
 * - creator: creó la versión actualmente IN_REVIEW (created_by === userId)
 * - approver: tiene permiso para aprobar/rechazar y NO es el creador de esa versión
 * - viewer: resto
 */
export function getDocumentRole(
  isCreatorOfInReviewVersion: boolean,
  hasApprovePermission: boolean,
  hasRejectPermission: boolean
): DocumentRole {
  if (isCreatorOfInReviewVersion) return 'creator';
  if (hasApprovePermission || hasRejectPermission) return 'approver';
  return 'viewer';
}

/**
 * ¿Puede el usuario aprobar la versión en revisión?
 * Solo approver cuando el documento está pendiente de validación.
 * (El backend además exige que no sea el creador de la versión.)
 */
export function canApprove(role: DocumentRole, status: DocumentStatus): boolean {
  return role === 'approver' && status === 'pending_validation';
}

/**
 * ¿Puede el usuario rechazar la versión en revisión?
 */
export function canReject(role: DocumentRole, status: DocumentStatus): boolean {
  return role === 'approver' && status === 'pending_validation';
}

/**
 * ¿Puede el usuario cancelar el envío y volver a borrador?
 * Solo el creador cuando está pendiente de validación.
 */
export function canCancelSubmission(role: DocumentRole, status: DocumentStatus): boolean {
  return role === 'creator' && status === 'pending_validation';
}

/**
 * ¿Puede el usuario editar metadatos/contexto?
 * Solo el creador en borrador o pendiente de validación.
 * (No permite editar contenido generado; solo metadatos.)
 */
export function canEditMetadata(role: DocumentRole, status: DocumentStatus): boolean {
  return role === 'creator' && (status === 'draft' || status === 'pending_validation');
}

/**
 * ¿Se puede crear una nueva versión (botón "+ Nueva Versión")?
 * Solo cuando el documento está aprobado o rechazado.
 */
export function canCreateNewVersion(status: DocumentStatus): boolean {
  return status === 'approved' || status === 'rejected';
}

/**
 * ¿Puede el usuario enviar la versión DRAFT a revisión?
 * Solo el creador cuando el documento está en borrador.
 */
export function canSubmitForReview(role: DocumentRole, status: DocumentStatus): boolean {
  return role === 'creator' && status === 'draft';
}
