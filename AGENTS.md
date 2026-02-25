

## vexp ## vexp <!-- vexp v1.2.12 -->

**MANDATORY: use vexp MCP tools for ALL file analysis.**
Do NOT use grep, glob, search, or file reads to explore the codebase.
Use vexp MCP tools instead — they return pre-indexed, relevant context.

Before any code change or question, call `get_context_capsule` with a description of your task.
This provides the most relevant source files and their skeletons with minimal token usage.

### Workflow
1. `get_context_capsule` — ALWAYS FIRST for any task or question
2. Review the provided pivot files and skeletons
3. Make targeted changes based on the context
4. `get_impact_graph` before refactoring exported symbols

### Available MCP tools
- `get_context_capsule` — most relevant code (ALWAYS FIRST). Auto-detects intent from your query
- `get_impact_graph` — what breaks if you change a symbol
- `search_logic_flow` — execution paths between functions
- `get_skeleton` — token-efficient file structure
- `index_status` — indexing status
- `workspace_setup` — bootstrap vexp config for a new project
- `get_session_context` — recall observations from current/previous sessions
- `search_memory` — cross-session search for past decisions and insights
- `save_observation` — persist important insights with optional code symbol linking

### Smart Features
vexp auto-detects query intent (debug/refactor/modify/read) and uses hybrid ranking
(keyword + semantic + graph centrality). Session memory auto-captures observations.
Repeated queries auto-expand result budget. Use `include_tests: true` when debugging.

### Multi-Repo
`get_context_capsule` auto-queries all indexed repos. Use `repos: ["alias"]` to scope, `cross_repo: true` on `get_impact_graph`/`search_logic_flow` to trace across repos. Run `index_status` to see available aliases.
<!-- /vexp -->