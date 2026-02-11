/**
 * Tests básicos para los helpers de permisos del documento.
 * Ejecutar con: npx vitest run lib/__tests__/documentPermissions.test.ts
 */
import { describe, it, expect } from 'vitest';
import {
  getDocumentRole,
  canApprove,
  canReject,
  canCancelSubmission,
  canEditMetadata,
  canCreateNewVersion,
  canSubmitForReview,
  type DocumentStatus,
} from '../documentPermissions';

describe('getDocumentRole', () => {
  it('returns creator when user created the in-review version', () => {
    expect(getDocumentRole(true, true, true)).toBe('creator');
    expect(getDocumentRole(true, false, false)).toBe('creator');
  });
  it('returns approver when not creator but has approve or reject permission', () => {
    expect(getDocumentRole(false, true, false)).toBe('approver');
    expect(getDocumentRole(false, false, true)).toBe('approver');
    expect(getDocumentRole(false, true, true)).toBe('approver');
  });
  it('returns viewer when no permissions', () => {
    expect(getDocumentRole(false, false, false)).toBe('viewer');
  });
});

describe('canApprove', () => {
  it('allows approver only when pending_validation', () => {
    expect(canApprove('approver', 'pending_validation')).toBe(true);
    expect(canApprove('approver', 'draft')).toBe(false);
    expect(canApprove('approver', 'approved')).toBe(false);
    expect(canApprove('creator', 'pending_validation')).toBe(false);
    expect(canApprove('viewer', 'pending_validation')).toBe(false);
  });
});

describe('canReject', () => {
  it('allows approver only when pending_validation', () => {
    expect(canReject('approver', 'pending_validation')).toBe(true);
    expect(canReject('approver', 'rejected')).toBe(false);
    expect(canReject('creator', 'pending_validation')).toBe(false);
  });
});

describe('canCancelSubmission', () => {
  it('allows only creator when pending_validation', () => {
    expect(canCancelSubmission('creator', 'pending_validation')).toBe(true);
    expect(canCancelSubmission('creator', 'draft')).toBe(false);
    expect(canCancelSubmission('approver', 'pending_validation')).toBe(false);
    expect(canCancelSubmission('viewer', 'pending_validation')).toBe(false);
  });
});

describe('canEditMetadata', () => {
  it('allows creator only in draft or pending_validation', () => {
    expect(canEditMetadata('creator', 'draft')).toBe(true);
    expect(canEditMetadata('creator', 'pending_validation')).toBe(true);
    expect(canEditMetadata('creator', 'approved')).toBe(false);
    expect(canEditMetadata('creator', 'rejected')).toBe(false);
    expect(canEditMetadata('approver', 'pending_validation')).toBe(false);
    expect(canEditMetadata('approver', 'draft')).toBe(false);
  });
});

describe('canCreateNewVersion', () => {
  it('allows only when approved or rejected', () => {
    expect(canCreateNewVersion('approved')).toBe(true);
    expect(canCreateNewVersion('rejected')).toBe(true);
    expect(canCreateNewVersion('draft')).toBe(false);
    expect(canCreateNewVersion('pending_validation')).toBe(false);
    expect(canCreateNewVersion('archived')).toBe(false);
  });
});

describe('canSubmitForReview', () => {
  it('allows only creator when draft', () => {
    expect(canSubmitForReview('creator', 'draft')).toBe(true);
    expect(canSubmitForReview('creator', 'pending_validation')).toBe(false);
    expect(canSubmitForReview('approver', 'draft')).toBe(false);
    expect(canSubmitForReview('viewer', 'draft')).toBe(false);
  });
});
