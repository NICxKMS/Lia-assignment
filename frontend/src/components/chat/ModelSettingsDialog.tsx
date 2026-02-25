import { RotateCcw, Settings } from "lucide-react";
import { memo, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ModelSettings } from "@/lib/types";
import { DEFAULT_MODEL_SETTINGS } from "@/lib/types";

interface ModelSettingsDialogProps {
	modelSettings: ModelSettings;
	setModelSettings: (settings: ModelSettings) => void;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

const ModelSettingsDialog = memo<ModelSettingsDialogProps>(
	({ modelSettings, setModelSettings, open, onOpenChange }) => {
		// Model settings update handlers
		const updateSetting = useCallback(
			<K extends keyof ModelSettings>(key: K, value: ModelSettings[K]) => {
				setModelSettings({ ...modelSettings, [key]: value });
			},
			[modelSettings, setModelSettings],
		);

		const resetSettings = useCallback(() => {
			setModelSettings(DEFAULT_MODEL_SETTINGS);
		}, [setModelSettings]);

		return (
			<Dialog open={open} onOpenChange={onOpenChange}>
				<Tooltip>
					<TooltipTrigger asChild>
						<DialogTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								className="text-muted-foreground hover:text-foreground"
							>
								<Settings className="w-5 h-5" />
							</Button>
						</DialogTrigger>
					</TooltipTrigger>
					<TooltipContent>Model Settings</TooltipContent>
				</Tooltip>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<Settings className="w-5 h-5" />
							Model Settings
						</DialogTitle>
						<DialogDescription>
							Configure the AI model behavior for your conversations.
						</DialogDescription>
					</DialogHeader>

					<div className="space-y-6 py-4">
						{/* Temperature */}
						<div className="space-y-3">
							<div className="flex items-center justify-between">
								<Label className="text-sm font-medium">Temperature</Label>
								<span className="text-sm font-mono text-muted-foreground">
									{modelSettings.temperature.toFixed(2)}
								</span>
							</div>
							<Slider
								value={[modelSettings.temperature]}
								onValueChange={([v]) => updateSetting("temperature", v)}
								min={0}
								max={2}
								step={0.1}
								className="w-full"
							/>
							<p className="text-xs text-muted-foreground">
								Higher values make output more random, lower values make it more
								focused.
							</p>
						</div>

						{/* Max Tokens */}
						<div className="space-y-3">
							<div className="flex items-center justify-between">
								<Label className="text-sm font-medium">Max Tokens</Label>
								<Input
									type="number"
									value={modelSettings.maxTokens}
									onChange={(e) =>
										updateSetting(
											"maxTokens",
											Math.min(
												32000,
												Math.max(1, parseInt(e.target.value, 10) || 1),
											),
										)
									}
									className="w-24 h-8 text-sm text-right font-mono"
									min={1}
									max={32000}
								/>
							</div>
							<p className="text-xs text-muted-foreground">
								Maximum number of tokens in the response.
							</p>
						</div>

						{/* Top P */}
						<div className="space-y-3">
							<div className="flex items-center justify-between">
								<Label className="text-sm font-medium">Top P</Label>
								<span className="text-sm font-mono text-muted-foreground">
									{modelSettings.topP.toFixed(2)}
								</span>
							</div>
							<Slider
								value={[modelSettings.topP]}
								onValueChange={([v]) => updateSetting("topP", v)}
								min={0}
								max={1}
								step={0.05}
								className="w-full"
							/>
							<p className="text-xs text-muted-foreground">
								Nucleus sampling: considers tokens with top_p probability mass.
							</p>
						</div>

						{/* Frequency Penalty */}
						<div className="space-y-3">
							<div className="flex items-center justify-between">
								<Label className="text-sm font-medium">Frequency Penalty</Label>
								<span className="text-sm font-mono text-muted-foreground">
									{modelSettings.frequencyPenalty.toFixed(2)}
								</span>
							</div>
							<Slider
								value={[modelSettings.frequencyPenalty]}
								onValueChange={([v]) => updateSetting("frequencyPenalty", v)}
								min={-2}
								max={2}
								step={0.1}
								className="w-full"
							/>
							<p className="text-xs text-muted-foreground">
								Reduces repetition based on how often tokens appear.
							</p>
						</div>

						{/* Presence Penalty */}
						<div className="space-y-3">
							<div className="flex items-center justify-between">
								<Label className="text-sm font-medium">Presence Penalty</Label>
								<span className="text-sm font-mono text-muted-foreground">
									{modelSettings.presencePenalty.toFixed(2)}
								</span>
							</div>
							<Slider
								value={[modelSettings.presencePenalty]}
								onValueChange={([v]) => updateSetting("presencePenalty", v)}
								min={-2}
								max={2}
								step={0.1}
								className="w-full"
							/>
							<p className="text-xs text-muted-foreground">
								Encourages the model to talk about new topics.
							</p>
						</div>

						{/* Reset Button */}
						<Button
							variant="outline"
							onClick={resetSettings}
							className="w-full"
						>
							<RotateCcw className="w-4 h-4 mr-2" />
							Reset to Defaults
						</Button>
					</div>
				</DialogContent>
			</Dialog>
		);
	},
);

ModelSettingsDialog.displayName = "ModelSettingsDialog";

export default ModelSettingsDialog;
