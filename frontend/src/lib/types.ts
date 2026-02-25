// Shared types and constants for model settings
// Single source of truth — imported by ChatInterface, ModelSettingsDialog, useChat

export interface ModelSettings {
	temperature: number;
	maxTokens: number;
	topP: number;
	frequencyPenalty: number;
	presencePenalty: number;
}

export const DEFAULT_MODEL_SETTINGS: ModelSettings = {
	temperature: 0.7,
	maxTokens: 8192,
	topP: 1.0,
	frequencyPenalty: 0.0,
	presencePenalty: 0.0,
};
