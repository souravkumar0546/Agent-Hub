import React from "react";

/** Horizontal stepper showing the run's progress through CACM's six
 *  pipeline stages. The current stage gets a pulsing primary highlight,
 *  completed stages get a checkmark, pending ones are grey.
 */
export default function StageStepper({
  stages,
  currentStage,
  completedStages = [],
}) {
  const completedSet = new Set(completedStages);
  return (
    <div className="cacm-stepper">
      {stages.map((stage, i) => {
        const isCompleted = completedSet.has(stage.key);
        const isCurrent = stage.key === currentStage;
        let state = "pending";
        if (isCompleted) state = "done";
        else if (isCurrent) state = "active";
        return (
          <React.Fragment key={stage.key}>
            <div className={`cacm-step cacm-step--${state}`}>
              <div className="cacm-step-circle">
                {state === "done" ? "✓" : i + 1}
              </div>
              <div className="cacm-step-label">{stage.label}</div>
            </div>
            {i < stages.length - 1 && (
              <div
                className={`cacm-step-bar${
                  isCompleted ? " cacm-step-bar--done" : ""
                }`}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export const CACM_STAGES = [
  { key: "extract", label: "Extract" },
  { key: "transform", label: "Transform" },
  { key: "load", label: "Load" },
  { key: "rules", label: "Rule Engine" },
  { key: "exceptions", label: "Exceptions" },
  { key: "dashboard", label: "Dashboard" },
];
