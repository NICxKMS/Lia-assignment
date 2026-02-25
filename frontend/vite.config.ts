/// <reference types="vitest" />

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

const API_URL = process.env.VITE_API_URL || "http://localhost:8000";

// https://vite.dev/config/
export default defineConfig({
	plugins: [react(), tailwindcss()],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
	},
	server: {
		proxy: {
			"/api": {
				target: API_URL,
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, "/api/v1"),
			},
		},
	},
	build: {
		// Increase chunk size warning limit
		chunkSizeWarningLimit: 600,
		// Target modern browsers for smaller bundle
		target: "es2020",
		// Enable minification
		minify: "esbuild",
		// Enable source maps for production debugging (optional)
		sourcemap: false,
	},
});
