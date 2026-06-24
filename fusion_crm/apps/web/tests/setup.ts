import "@testing-library/jest-dom/vitest";

// React Flow (used by IdentityGraphModal) measures node sizes via
// ResizeObserver, which jsdom does not implement. Provide a no-op stub so
// rendering the component in tests does not throw. Same trick is documented
// in https://reactflow.dev/learn/troubleshooting/testing.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

// React Flow also queries DOMMatrix and HTMLCanvasElement.getContext at
// mount time; jsdom has neither. Stub both quietly.
if (typeof globalThis.DOMMatrixReadOnly === "undefined") {
  // @ts-expect-error — minimal stub for layout queries
  globalThis.DOMMatrixReadOnly = class {
    m22 = 1;
    constructor() {
      /* noop */
    }
  };
}
