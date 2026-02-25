import { Brain, Check, ChevronDown, Globe, Sparkles, Zap } from "lucide-react";
import * as React from "react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { AIModel } from "./model-data";

// Provider logos/icons
const providerIcons: Record<string, React.ReactNode> = {
	openai: <span className="text-[10px] font-bold">GPT</span>,
	google: <span className="text-[10px] font-bold">G</span>,
	gemini: <Sparkles className="w-3 h-3" />,
	anthropic: <span className="text-[10px] font-bold">A</span>,
	deepseek: <Brain className="w-3 h-3" />,
	perplexity: <Globe className="w-3 h-3" />,
};

// Capability badges
const capabilityConfig: Record<
	string,
	{ icon: React.ReactNode; label: string; color: string }
> = {
	reasoning: {
		icon: <Brain className="w-2.5 h-2.5" />,
		label: "Reasoning",
		color: "text-purple-400 bg-purple-500/10",
	},
	vision: {
		icon: <span>👁</span>,
		label: "Vision",
		color: "text-blue-400 bg-blue-500/10",
	},
	code: {
		icon: <span>{"</>"}</span>,
		label: "Code",
		color: "text-green-400 bg-green-500/10",
	},
	fast: {
		icon: <Zap className="w-2.5 h-2.5" />,
		label: "Fast",
		color: "text-yellow-400 bg-yellow-500/10",
	},
};

// Marquee text component for long model names - memoized
const MarqueeText = memo<{ text: string; className?: string }>(
	({ text, className }) => {
		const containerRef = useRef<HTMLDivElement>(null);
		const textRef = useRef<HTMLSpanElement>(null);
		const [shouldAnimate, setShouldAnimate] = useState(false);

		const checkOverflow = useCallback(() => {
			if (containerRef.current && textRef.current) {
				setShouldAnimate(
					textRef.current.scrollWidth > containerRef.current.clientWidth,
				);
			}
		}, []);

		useEffect(() => {
			let timeoutId: ReturnType<typeof setTimeout>;
			const handleResize = () => {
				clearTimeout(timeoutId);
				timeoutId = setTimeout(checkOverflow, 150);
			};
			window.addEventListener("resize", handleResize);
			checkOverflow();
			return () => {
				window.removeEventListener("resize", handleResize);
				clearTimeout(timeoutId);
			};
		}, [checkOverflow]);

		return (
			<div
				ref={containerRef}
				className={cn("overflow-hidden whitespace-nowrap", className)}
			>
				<span
					ref={textRef}
					className={cn(
						"inline-block",
						shouldAnimate && "animate-marquee hover:animate-marquee",
					)}
					style={
						shouldAnimate
							? {
									animation: "marquee 8s linear infinite",
									paddingRight: "2rem",
								}
							: undefined
					}
				>
					{text}
					{shouldAnimate && <span className="pl-8">{text}</span>}
				</span>
			</div>
		);
	},
);

MarqueeText.displayName = "MarqueeText";

// Simple Select-based Model Selector
export interface ModelSelectorProps {
	models: AIModel[];
	value?: string;
	onValueChange?: (value: string) => void;
	className?: string;
	placeholder?: string;
}

export const ModelSelector = memo(
	({
		models,
		value,
		onValueChange,
		className,
		placeholder = "Select model",
	}: ModelSelectorProps) => {
		// Group models by provider - memoized
		const groupedModels = useMemo(() => {
			const groups: Record<string, AIModel[]> = {};
			models.forEach((model) => {
				if (!groups[model.provider]) {
					groups[model.provider] = [];
				}
				groups[model.provider].push(model);
			});
			return groups;
		}, [models]);

		const selectedModel = useMemo(
			() => models.find((m) => m.id === value),
			[models, value],
		);

		return (
			<Select value={value} onValueChange={onValueChange}>
				<SelectTrigger className={cn("h-9 gap-2 max-w-[200px]", className)}>
					<div className="flex items-center gap-2 min-w-0 flex-1">
						{selectedModel && (
							<div className="w-5 h-5 rounded flex items-center justify-center bg-muted text-muted-foreground shrink-0">
								{selectedModel.icon ||
									providerIcons[selectedModel.provider.toLowerCase()] || (
										<Sparkles className="w-3 h-3" />
									)}
							</div>
						)}
						<div className="min-w-0 flex-1 overflow-hidden">
							<MarqueeText
								text={selectedModel?.name || placeholder}
								className="text-sm"
							/>
						</div>
					</div>
				</SelectTrigger>
				<SelectContent className="max-h-[300px]">
					{Object.entries(groupedModels).map(([provider, providerModels]) => (
						<SelectGroup key={provider}>
							<SelectLabel className="text-xs text-muted-foreground uppercase tracking-wider">
								{provider}
							</SelectLabel>
							{providerModels.map((model) => (
								<SelectItem
									key={model.id}
									value={model.id}
									className="py-2 cursor-pointer focus:bg-secondary focus:text-secondary-foreground data-[highlighted]:bg-secondary data-[highlighted]:text-secondary-foreground"
								>
									<div className="flex items-center gap-2">
										<div className="w-5 h-5 rounded flex items-center justify-center bg-muted text-muted-foreground text-xs">
											{model.icon ||
												providerIcons[model.provider.toLowerCase()] || (
													<Sparkles className="w-3 h-3" />
												)}
										</div>
										<div className="flex flex-col">
											<span className="text-sm font-medium">{model.name}</span>
											{model.description && (
												<span className="text-xs text-muted-foreground">
													{model.description}
												</span>
											)}
										</div>
										{model.badge && (
											<Badge
												variant="secondary"
												className="ml-auto text-[9px] px-1.5 py-0"
											>
												{model.badge}
											</Badge>
										)}
									</div>
								</SelectItem>
							))}
						</SelectGroup>
					))}
				</SelectContent>
			</Select>
		);
	},
);

ModelSelector.displayName = "ModelSelector";

// Dropdown-based Model Selector (more visual)
export interface ModelDropdownProps {
	models: AIModel[];
	value?: string;
	onValueChange?: (value: string) => void;
	className?: string;
}

export const ModelDropdown = memo(
	({ models, value, onValueChange, className }: ModelDropdownProps) => {
		const [open, setOpen] = useState(false);

		// Store callback in ref for stable handler
		const onValueChangeRef = useRef(onValueChange);
		useEffect(() => {
			onValueChangeRef.current = onValueChange;
		}, [onValueChange]);

		const selectedModel = useMemo(
			() => models.find((m) => m.id === value),
			[models, value],
		);

		// Group models by provider - memoized
		const groupedModels = useMemo(() => {
			const groups: Record<string, AIModel[]> = {};
			models.forEach((model) => {
				if (!groups[model.provider]) {
					groups[model.provider] = [];
				}
				groups[model.provider].push(model);
			});
			return groups;
		}, [models]);

		// Stable handler using ref
		const handleSelect = useCallback((modelId: string) => {
			onValueChangeRef.current?.(modelId);
			setOpen(false);
		}, []);

		return (
			<DropdownMenu open={open} onOpenChange={setOpen}>
				<DropdownMenuTrigger asChild>
					<Button
						variant="outline"
						role="combobox"
						aria-expanded={open}
						className={cn(
							"h-9 justify-between gap-2 font-normal max-w-[200px]",
							className,
						)}
					>
						<div className="flex items-center gap-2 min-w-0 flex-1">
							{selectedModel && (
								<div className="w-5 h-5 rounded flex items-center justify-center bg-primary/10 text-primary shrink-0">
									{selectedModel.icon ||
										providerIcons[selectedModel.provider.toLowerCase()] || (
											<Sparkles className="w-3 h-3" />
										)}
								</div>
							)}
							<div className="min-w-0 flex-1 overflow-hidden">
								<MarqueeText
									text={selectedModel?.name || "Select model"}
									className="text-sm"
								/>
							</div>
						</div>
						<ChevronDown className="w-4 h-4 opacity-50 shrink-0" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent className="w-[280px]" align="start">
					{Object.entries(groupedModels).map(
						([provider, providerModels], groupIndex) => (
							<React.Fragment key={provider}>
								{groupIndex > 0 && <DropdownMenuSeparator />}
								<DropdownMenuLabel className="text-xs text-muted-foreground uppercase tracking-wider">
									{provider}
								</DropdownMenuLabel>
								<DropdownMenuGroup>
									{providerModels.map((model) => (
										<DropdownMenuItem
											key={model.id}
											onClick={() => handleSelect(model.id)}
											className="flex items-center gap-3 py-2 cursor-pointer focus:bg-secondary focus:text-secondary-foreground"
										>
											<div
												className={cn(
													"w-6 h-6 rounded-md flex items-center justify-center",
													value === model.id
														? "bg-primary text-primary-foreground"
														: "bg-muted text-muted-foreground",
												)}
											>
												{model.icon ||
													providerIcons[model.provider.toLowerCase()] || (
														<Sparkles className="w-3 h-3" />
													)}
											</div>
											<div className="flex-1 min-w-0">
												<div className="flex items-center gap-2">
													<span className="text-sm font-medium truncate">
														{model.name}
													</span>
													{model.badge && (
														<Badge
															variant="outline"
															className="text-[9px] px-1 py-0 shrink-0"
														>
															{model.badge}
														</Badge>
													)}
												</div>
												{model.capabilities &&
													model.capabilities.length > 0 && (
														<div className="flex gap-1 mt-1">
															{model.capabilities.map((cap) => {
																const config = capabilityConfig[cap];
																return config ? (
																	<span
																		key={cap}
																		className={cn(
																			"inline-flex items-center gap-0.5 px-1 py-0.5 rounded text-[9px]",
																			config.color,
																		)}
																	>
																		{config.icon}
																	</span>
																) : null;
															})}
														</div>
													)}
											</div>
											{value === model.id && (
												<Check className="w-4 h-4 text-primary shrink-0" />
											)}
										</DropdownMenuItem>
									))}
								</DropdownMenuGroup>
							</React.Fragment>
						),
					)}
				</DropdownMenuContent>
			</DropdownMenu>
		);
	},
);

ModelDropdown.displayName = "ModelDropdown";

// Compact inline model selector (badge style)
export interface ModelBadgeSelectorProps {
	models: AIModel[];
	value?: string;
	onValueChange?: (value: string) => void;
	className?: string;
}

export const ModelBadgeSelector = memo(
	({ models, value, onValueChange, className }: ModelBadgeSelectorProps) => {
		// Store callback in ref for stable handler
		const onValueChangeRef = useRef(onValueChange);
		useEffect(() => {
			onValueChangeRef.current = onValueChange;
		}, [onValueChange]);

		const selectedModel = useMemo(
			() => models.find((m) => m.id === value),
			[models, value],
		);

		// Stable handler using ref
		const handleSelect = useCallback((modelId: string) => {
			onValueChangeRef.current?.(modelId);
		}, []);

		return (
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<button
						className={cn(
							"inline-flex items-center gap-1.5 px-2 py-1 rounded-full",
							"bg-muted/50 hover:bg-muted border border-border/50",
							"text-xs font-medium text-muted-foreground hover:text-foreground",
							"transition-colors cursor-pointer",
							className,
						)}
					>
						{selectedModel && (
							<span className="w-4 h-4 rounded-full flex items-center justify-center bg-primary/10 text-primary">
								{selectedModel.icon ||
									providerIcons[selectedModel.provider.toLowerCase()] ||
									"✨"}
							</span>
						)}
						<span>{selectedModel?.name || "Model"}</span>
						<ChevronDown className="w-3 h-3" />
					</button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="start" className="w-[200px]">
					{models.map((model) => (
						<DropdownMenuItem
							key={model.id}
							onClick={() => handleSelect(model.id)}
							className="flex items-center gap-2 cursor-pointer"
						>
							<span className="w-4 h-4 rounded-full flex items-center justify-center bg-muted text-muted-foreground text-[10px]">
								{model.icon ||
									providerIcons[model.provider.toLowerCase()] ||
									"✨"}
							</span>
							<span className="flex-1 text-sm">{model.name}</span>
							{value === model.id && <Check className="w-3 h-3 text-primary" />}
						</DropdownMenuItem>
					))}
				</DropdownMenuContent>
			</DropdownMenu>
		);
	},
);

ModelBadgeSelector.displayName = "ModelBadgeSelector";
