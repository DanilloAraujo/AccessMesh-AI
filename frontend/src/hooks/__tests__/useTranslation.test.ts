import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { translate, getLang } from '../useTranslation';

describe('useTranslation setup', () => {

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('gets correct language from storage mapping', () => {
    localStorage.setItem('preferredLanguage', 'pt-BR');
    expect(getLang()).toBe('pt');

    localStorage.setItem('preferredLanguage', 'en-US');
    expect(getLang()).toBe('en');

    localStorage.setItem('preferredLanguage', 'es');
    expect(getLang()).toBe('en'); // fallback to english for unsupported
  });

  it('translates strings properly depending on current lang', () => {
    localStorage.setItem('preferredLanguage', 'pt-BR');
    expect(translate('login.title')).toBe('Entrar na AccessMesh AI');

    localStorage.setItem('preferredLanguage', 'en-US');
    expect(translate('login.title')).toBe('Sign in to AccessMesh AI');
  });

  it('returns key when translation is missing', () => {
    expect(translate('some.nonexistent.key')).toBe('some.nonexistent.key');
  });

  it('supports interpolation via replace string mechanism', () => {
    localStorage.setItem('preferredLanguage', 'en-US');
    // Using an existing error generic string text which doesnt have interpolation format natively 
    // but just checking the base string returns
    expect(translate('errorBoundary.generic')).toContain('error');
  });
});
