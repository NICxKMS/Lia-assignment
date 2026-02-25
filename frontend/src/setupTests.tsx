import "@testing-library/jest-dom";
import React from "react";
import { vi } from "vitest";

console.log("setupTests.ts running");

// Suppress expected console.error calls during tests
const originalError = console.error;
console.error = (...args: unknown[]) => {
	const message = String(args[0]);
	// Suppress expected error patterns in tests
	if (
		message.includes("[useChat] Error:") ||
		message.includes("An update to") ||
		message.includes("act(...)") ||
		message.includes("No queryFn was passed") ||
		message.includes("is unrecognized in this browser") ||
		message.includes("using incorrect casing")
	) {
		return;
	}
	originalError.apply(console, args);
};

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
(
	globalThis as unknown as { ResizeObserver: typeof ResizeObserver }
).ResizeObserver = ResizeObserver;

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

// Mock framer-motion to strip motion-only props in JSDOM
vi.mock("framer-motion", () => {
	// Props that framer-motion uses that should be stripped from DOM elements
	const motionProps = new Set([
		"initial",
		"animate",
		"exit",
		"whileHover",
		"whileTap",
		"whileFocus",
		"whileDrag",
		"whileInView",
		"variants",
		"transition",
		"layout",
		"layoutId",
		"drag",
		"dragConstraints",
		"dragElastic",
		"dragMomentum",
		"dragTransition",
		"onDragStart",
		"onDrag",
		"onDragEnd",
		"onAnimationStart",
		"onAnimationComplete",
		"onLayoutAnimationStart",
		"onLayoutAnimationComplete",
	]);

	const filterMotionProps = (props: Record<string, unknown>) => {
		const filtered: Record<string, unknown> = {};
		for (const key in props) {
			if (!motionProps.has(key)) {
				filtered[key] = props[key];
			}
		}
		return filtered;
	};

	const Mock = React.forwardRef<HTMLElement, Record<string, unknown>>(
		(props, ref) =>
			React.createElement("div", { ...filterMotionProps(props), ref }),
	);
	return {
		motion: new Proxy(
			{},
			{
				get: () => Mock,
			},
		),
		AnimatePresence: ({ children }: { children: React.ReactNode }) => (
			<>{children}</>
		),
	};
});

// Mock recharts to avoid unsupported SVG warnings in JSDOM
vi.mock("recharts", () => {
	const Mock = ({ children }: { children?: React.ReactNode }) => (
		<div data-recharts-mock>{children}</div>
	);
	return {
		ResponsiveContainer: Mock,
		LineChart: Mock,
		Line: Mock,
		CartesianGrid: Mock,
		XAxis: Mock,
		YAxis: Mock,
		Tooltip: Mock,
		Legend: Mock,
		ReferenceLine: Mock,
	};
});
