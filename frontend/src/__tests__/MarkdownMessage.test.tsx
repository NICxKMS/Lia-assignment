import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MarkdownMessage from "../components/MarkdownMessage";

describe("MarkdownMessage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.clearAllMocks();
		vi.useRealTimers();
	});

	describe("Basic Rendering", () => {
		it("renders plain text", () => {
			render(<MarkdownMessage content="Hello, World!" />);

			expect(screen.getByText("Hello, World!")).toBeInTheDocument();
		});

		it("renders empty content", () => {
			const { container } = render(<MarkdownMessage content="" />);

			expect(container.firstChild).toHaveClass("max-w-none");
		});

		it("applies styling classes to container", () => {
			const { container } = render(<MarkdownMessage content="Test" />);

			expect(container.firstChild).toHaveClass("max-w-none", "text-foreground");
		});
	});

	describe("Markdown Formatting", () => {
		it("renders bold text", () => {
			render(<MarkdownMessage content="This is **bold** text" />);

			const boldText = screen.getByText("bold");
			expect(boldText.tagName).toBe("STRONG");
		});

		it("renders italic text", () => {
			render(<MarkdownMessage content="This is *italic* text" />);

			const italicText = screen.getByText("italic");
			expect(italicText.tagName).toBe("EM");
		});

		it("renders headings", () => {
			render(<MarkdownMessage content="# Heading 1" />);

			expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
				"Heading 1",
			);
		});

		it("renders multiple headings", () => {
			const content = `# H1

## H2

### H3`;
			render(<MarkdownMessage content={content} />);

			expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("H1");
			expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("H2");
			expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent("H3");
		});
	});

	describe("Lists", () => {
		it("renders unordered lists", () => {
			render(<MarkdownMessage content="- Item 1" />);

			const list = screen.getByRole("list");
			expect(list.tagName).toBe("UL");
		});

		it("renders ordered lists", () => {
			render(<MarkdownMessage content="1. First" />);

			const list = screen.getByRole("list");
			expect(list.tagName).toBe("OL");
		});

		it("renders task lists (GFM)", () => {
			render(<MarkdownMessage content="- [x] Checked" />);

			const checkbox = screen.getByRole("checkbox");
			expect(checkbox).toBeChecked();
		});

		it("makes task list checkboxes readonly", () => {
			render(<MarkdownMessage content="- [x] Task" />);

			const checkbox = screen.getByRole("checkbox");
			expect(checkbox).toHaveAttribute("readonly");
		});
	});

	describe("Links", () => {
		it("renders links", () => {
			render(<MarkdownMessage content="[Click here](https://example.com)" />);

			const link = screen.getByRole("link", { name: "Click here" });
			expect(link).toHaveAttribute("href", "https://example.com");
		});

		it("opens external links in new tab", () => {
			render(<MarkdownMessage content="[External](https://example.com)" />);

			const link = screen.getByRole("link", { name: "External" });
			expect(link).toHaveAttribute("target", "_blank");
			expect(link).toHaveAttribute("rel", "noopener noreferrer");
		});

		it("does not add target for internal links", () => {
			render(<MarkdownMessage content="[Internal](/path)" />);

			const link = screen.getByRole("link", { name: "Internal" });
			expect(link).not.toHaveAttribute("target");
			expect(link).not.toHaveAttribute("rel");
		});
	});

	describe("Code", () => {
		it("renders inline code", () => {
			render(<MarkdownMessage content="Use `console.log()` for debugging" />);

			const code = screen.getByText("console.log()");
			expect(code.tagName).toBe("CODE");
		});

		it("renders code blocks with pre element", () => {
			const content = "```javascript\nconst x = 1;\n```";
			const { container } = render(<MarkdownMessage content={content} />);

			// Code block should be wrapped in pre
			expect(container.querySelector("pre")).toBeInTheDocument();
			expect(container.querySelector("code")).toBeInTheDocument();
		});

		it("shows language badge for code blocks", () => {
			const content = '```python\nprint("hello")\n```';
			render(<MarkdownMessage content={content} />);

			expect(screen.getByText("python")).toBeInTheDocument();
		});

		it("shows copy button on code blocks", () => {
			const content = "```javascript\nconst x = 1;\n```";
			render(<MarkdownMessage content={content} />);

			expect(
				screen.getByRole("button", { name: /copy code/i }),
			).toBeInTheDocument();
		});
	});

	describe("Blockquotes", () => {
		it("renders blockquotes", () => {
			render(<MarkdownMessage content="> This is a quote" />);

			const quote = screen.getByText("This is a quote");
			expect(quote.closest("blockquote")).toBeInTheDocument();
		});
	});

	describe("Tables (GFM)", () => {
		it("renders tables", () => {
			const content = `
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
`;
			render(<MarkdownMessage content={content} />);

			expect(screen.getByRole("table")).toBeInTheDocument();
			expect(screen.getByText("Header 1")).toBeInTheDocument();
			expect(screen.getByText("Cell 1")).toBeInTheDocument();
		});
	});

	describe("Images", () => {
		it("renders images", () => {
			render(
				<MarkdownMessage content="![Alt text](https://example.com/image.jpg)" />,
			);

			const image = screen.getByRole("img", { name: "Alt text" });
			expect(image).toHaveAttribute("src", "https://example.com/image.jpg");
		});
	});

	describe("Raw HTML (rehype-raw)", () => {
		it("renders raw HTML elements", () => {
			render(<MarkdownMessage content="<strong>Bold HTML</strong>" />);

			const bold = screen.getByText("Bold HTML");
			expect(bold.tagName).toBe("STRONG");
		});
	});

	describe("Strikethrough (GFM)", () => {
		it("renders strikethrough text", () => {
			render(<MarkdownMessage content="~~deleted~~" />);

			const deleted = screen.getByText("deleted");
			expect(deleted.tagName).toBe("DEL");
		});
	});

	describe("Component Memoization", () => {
		it("is memoized to prevent unnecessary re-renders", () => {
			const { rerender } = render(<MarkdownMessage content="Test" />);

			// Re-render with same props should not cause issues
			rerender(<MarkdownMessage content="Test" />);

			expect(screen.getByText("Test")).toBeInTheDocument();
		});

		it("updates when content changes", () => {
			const { rerender } = render(<MarkdownMessage content="Initial" />);

			rerender(<MarkdownMessage content="Updated" />);

			expect(screen.getByText("Updated")).toBeInTheDocument();
			expect(screen.queryByText("Initial")).not.toBeInTheDocument();
		});
	});

	describe("Syntax Highlighting", () => {
		it("applies syntax highlighting classes to code", () => {
			const content = "```javascript\nconst x = 1;\n```";
			const { container } = render(<MarkdownMessage content={content} />);

			// rehype-highlight adds hljs class
			const codeBlock = container.querySelector("code");
			expect(codeBlock).toHaveClass("language-javascript");
		});
	});

	describe("Complex Content", () => {
		it("renders mixed content correctly", () => {
			const content = `
# Title

This is a **bold** and *italic* paragraph with \`inline code\`.

## Section

- Item 1
- Item 2

\`\`\`javascript
const hello = "world";
\`\`\`

> A quote

| Column A | Column B |
|----------|----------|
| Value 1  | Value 2  |

[Link](https://example.com)
`;
			render(<MarkdownMessage content={content} />);

			expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
				"Title",
			);
			expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
				"Section",
			);
			expect(screen.getByText("bold").tagName).toBe("STRONG");
			expect(screen.getByText("italic").tagName).toBe("EM");
			expect(screen.getByText("inline code").tagName).toBe("CODE");
			expect(screen.getAllByRole("listitem")).toHaveLength(2);
			expect(screen.getByRole("table")).toBeInTheDocument();
			expect(screen.getByRole("link", { name: "Link" })).toBeInTheDocument();
		});
	});
});
