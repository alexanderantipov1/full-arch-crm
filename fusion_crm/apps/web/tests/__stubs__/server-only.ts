// Test-environment stub for ``server-only``. The real package is a
// build-time sentinel that the Next.js bundler uses to refuse client-side
// imports of server modules. Vitest does not run inside Next.js, so the
// guard is moot — leave the stub empty.
export {};
