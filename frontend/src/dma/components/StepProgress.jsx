import React from "react";

export default function StepProgress({ steps, currentStep, error }) {
  return (
    <div className="pipeline">
      <div className="pipeline-title">Processing Pipeline</div>
      {steps.map((step, i) => {
        let state = "pending";
        if (error && i === currentStep) state = "error";
        else if (i < currentStep) state = "done";
        else if (i === currentStep) state = "active";

        return (
          <div className={`pipeline-step ${state}`} key={i}>
            <div className="pipeline-icon">
              {state === "done" ? "✓" : state === "error" ? "✕" : state === "active" ? "●" : (i + 1)}
            </div>
            <div>
              <div className="pipeline-step-text">{step.label}</div>
              {step.sub && state !== "pending" && (
                <div className="pipeline-step-sub">{step.sub}</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
