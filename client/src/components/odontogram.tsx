import { useState, useCallback } from "react";
import type { ToothCondition } from "@shared/schema";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const CONDITION_COLORS: Record<string, string> = {
  missing: "#ef4444",
  implant: "#3b82f6",
  crown: "#a855f7",
  bridge: "#f59e0b",
  filling: "#22c55e",
  decay: "#dc2626",
  fracture: "#f97316",
  root_canal: "#6366f1",
  extraction_needed: "#be123c",
  pontic: "#0ea5e9",
  veneer: "#ec4899",
  inlay_onlay: "#14b8a6",
  impacted: "#78716c",
  healthy: "#10b981",
};

const CONDITION_LABELS: Record<string, string> = {
  missing: "Missing",
  implant: "Implant",
  crown: "Crown",
  bridge: "Bridge",
  filling: "Filling",
  decay: "Decay",
  fracture: "Fracture",
  root_canal: "Root Canal",
  extraction_needed: "Extract",
  pontic: "Pontic",
  veneer: "Veneer",
  inlay_onlay: "Inlay/Onlay",
  impacted: "Impacted",
  healthy: "Healthy",
};

const UPPER_TEETH = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];
const LOWER_TEETH = [32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17];

const TOOTH_NAMES: Record<number, string> = {
  1: "Upper Right 3rd Molar", 2: "Upper Right 2nd Molar", 3: "Upper Right 1st Molar",
  4: "Upper Right 2nd Premolar", 5: "Upper Right 1st Premolar", 6: "Upper Right Canine",
  7: "Upper Right Lateral Incisor", 8: "Upper Right Central Incisor",
  9: "Upper Left Central Incisor", 10: "Upper Left Lateral Incisor",
  11: "Upper Left Canine", 12: "Upper Left 1st Premolar",
  13: "Upper Left 2nd Premolar", 14: "Upper Left 1st Molar",
  15: "Upper Left 2nd Molar", 16: "Upper Left 3rd Molar",
  17: "Lower Left 3rd Molar", 18: "Lower Left 2nd Molar", 19: "Lower Left 1st Molar",
  20: "Lower Left 2nd Premolar", 21: "Lower Left 1st Premolar", 22: "Lower Left Canine",
  23: "Lower Left Lateral Incisor", 24: "Lower Left Central Incisor",
  25: "Lower Right Central Incisor", 26: "Lower Right Lateral Incisor",
  27: "Lower Right Canine", 28: "Lower Right 1st Premolar",
  29: "Lower Right 2nd Premolar", 30: "Lower Right 1st Molar",
  31: "Lower Right 2nd Molar", 32: "Lower Right 3rd Molar",
};

function isMolar(toothNum: number): boolean {
  return [1,2,3,14,15,16,17,18,19,30,31,32].includes(toothNum);
}

function isPremolar(toothNum: number): boolean {
  return [4,5,12,13,20,21,28,29].includes(toothNum);
}

function isAnterior(toothNum: number): boolean {
  return [6,7,8,9,10,11,22,23,24,25,26,27].includes(toothNum);
}

interface ToothSVGProps {
  toothNumber: number;
  isUpper: boolean;
  conditions: ToothCondition[];
  isSelected: boolean;
  onClick: (toothNum: number) => void;
}

function ToothSVG({ toothNumber, isUpper, conditions, isSelected, onClick }: ToothSVGProps) {
  const primaryCondition = conditions.find(c => c.status === "active");
  const condColor = primaryCondition ? CONDITION_COLORS[primaryCondition.conditionType] || "#94a3b8" : undefined;
  const isMissingTooth = conditions.some(c => c.conditionType === "missing" && c.status === "active");

  const w = 38;
  const h = 52;

  const rootPath = isUpper
    ? isMolar(toothNumber)
      ? "M10,26 L6,2 M19,26 L19,0 M28,26 L32,2"
      : isPremolar(toothNumber)
        ? "M14,26 L10,2 M24,26 L28,2"
        : "M19,26 L19,0"
    : isMolar(toothNumber)
      ? "M10,26 L6,50 M19,26 L19,52 M28,26 L32,50"
      : isPremolar(toothNumber)
        ? "M14,26 L10,50 M24,26 L28,50"
        : "M19,26 L19,52";

  const crownFill = condColor || "hsl(var(--card))";
  const crownStroke = isSelected ? "hsl(var(--primary))" : condColor || "hsl(var(--border))";
  const strokeWidth = isSelected ? 2.5 : 1.5;

  const condBadges = conditions.filter(c => c.status === "active");

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          className="flex flex-col items-center cursor-pointer group"
          onClick={() => onClick(toothNumber)}
          data-testid={`tooth-${toothNumber}`}
        >
          <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
            {isMissingTooth ? (
              <>
                <line x1="5" y1="5" x2="33" y2="47" stroke="#ef4444" strokeWidth="2" opacity="0.6" />
                <line x1="33" y1="5" x2="5" y2="47" stroke="#ef4444" strokeWidth="2" opacity="0.6" />
                <text x="19" y="30" textAnchor="middle" fontSize="8" fill="#ef4444" fontWeight="bold">X</text>
              </>
            ) : (
              <>
                <path d={rootPath} fill="none" stroke="hsl(var(--muted-foreground))" strokeWidth="1" opacity="0.5" />
                {isMolar(toothNumber) ? (
                  <rect x="4" y={isUpper ? 22 : 4} width="30" height="22" rx="5" ry="5"
                    fill={crownFill} stroke={crownStroke} strokeWidth={strokeWidth} />
                ) : isPremolar(toothNumber) ? (
                  <rect x="6" y={isUpper ? 22 : 4} width="26" height="20" rx="5" ry="5"
                    fill={crownFill} stroke={crownStroke} strokeWidth={strokeWidth} />
                ) : (
                  <rect x="8" y={isUpper ? 22 : 4} width="22" height="20" rx="6" ry="6"
                    fill={crownFill} stroke={crownStroke} strokeWidth={strokeWidth} />
                )}
                {primaryCondition && (
                  <circle
                    cx="19"
                    cy={isUpper ? 33 : 14}
                    r="4"
                    fill={condColor}
                    opacity="0.8"
                  />
                )}
              </>
            )}
          </svg>
          <span className={`text-xs font-mono mt-0.5 ${isSelected ? "text-primary font-bold" : "text-muted-foreground"}`}>
            {toothNumber}
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent side={isUpper ? "top" : "bottom"} className="max-w-[200px]">
        <p className="font-medium">#{toothNumber} - {TOOTH_NAMES[toothNumber]}</p>
        {condBadges.length > 0 ? (
          <div className="flex flex-wrap gap-1 mt-1">
            {condBadges.map(c => (
              <Badge key={c.id} variant="outline" className="text-xs" style={{ borderColor: CONDITION_COLORS[c.conditionType] }}>
                {CONDITION_LABELS[c.conditionType] || c.conditionType}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground mt-1">No conditions recorded</p>
        )}
      </TooltipContent>
    </Tooltip>
  );
}

interface OdontogramProps {
  conditions: ToothCondition[];
  selectedTooth: number | null;
  onSelectTooth: (toothNumber: number | null) => void;
}

export function Odontogram({ conditions, selectedTooth, onSelectTooth }: OdontogramProps) {
  const getConditionsForTooth = useCallback((toothNum: number) => {
    return conditions.filter(c => c.toothNumber === toothNum);
  }, [conditions]);

  const handleToothClick = useCallback((toothNum: number) => {
    onSelectTooth(selectedTooth === toothNum ? null : toothNum);
  }, [selectedTooth, onSelectTooth]);

  const activeConditionCounts = conditions.reduce((acc, c) => {
    if (c.status === "active") {
      acc[c.conditionType] = (acc[c.conditionType] || 0) + 1;
    }
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Right</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Left</span>
        </div>
      </div>

      <div className="border rounded-md p-4 bg-card">
        <div className="text-xs text-center text-muted-foreground mb-2 font-medium">Maxillary (Upper)</div>
        <div className="flex justify-center gap-0.5 flex-wrap">
          {UPPER_TEETH.map(num => (
            <ToothSVG
              key={num}
              toothNumber={num}
              isUpper={true}
              conditions={getConditionsForTooth(num)}
              isSelected={selectedTooth === num}
              onClick={handleToothClick}
            />
          ))}
        </div>

        <div className="border-t border-dashed my-3" />

        <div className="flex justify-center gap-0.5 flex-wrap">
          {LOWER_TEETH.map(num => (
            <ToothSVG
              key={num}
              toothNumber={num}
              isUpper={false}
              conditions={getConditionsForTooth(num)}
              isSelected={selectedTooth === num}
              onClick={handleToothClick}
            />
          ))}
        </div>
        <div className="text-xs text-center text-muted-foreground mt-2 font-medium">Mandibular (Lower)</div>
      </div>

      {Object.keys(activeConditionCounts).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(activeConditionCounts).map(([type, count]) => (
            <div key={type} className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: CONDITION_COLORS[type] }} />
              <span className="text-xs text-muted-foreground">
                {CONDITION_LABELS[type] || type} ({count})
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export { CONDITION_COLORS, CONDITION_LABELS, TOOTH_NAMES };
