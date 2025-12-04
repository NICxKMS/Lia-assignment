import "@testing-library/jest-dom";
import { vi } from "vitest";
console.log("setupTests.ts running");

class TextEncoder {
  encoding = "utf-8";
  encode(input?: string): Uint8Array {
    const utf8 = unescape(encodeURIComponent(input || ""));
    const result = new Uint8Array(utf8.length);
    for (let i = 0; i < utf8.length; i++) {
      result[i] = utf8.charCodeAt(i);
    }
    return result;
  }
}

class TextDecoder {
  encoding = "utf-8";
  decode(input?: Uint8Array): string {
    if (!input) return "";
    let str = "";
    for (let i = 0; i < input.length; i++) {
      str += String.fromCharCode(input[i]);
    }
    return decodeURIComponent(escape(str));
  }
}

Object.assign(globalThis, { TextEncoder, TextDecoder });

// Polyfill ResizeObserver
class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver = ResizeObserver;

// Polyfill matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
