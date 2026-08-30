"use strict";

const demo = Object.freeze({
  project: "Civic Forms Pilot",
  currentStage: "release",
  stages: [
    "discovery",
    "requirements",
    "design",
    "implementation",
    "verification",
    "release",
  ],
  artifacts: 5,
  assignments: 5,
  proposals: 5,
  auditEvents: 32,
  auditValid: true,
});

function addMetric(container, label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = String(value);
  wrapper.append(term, description);
  container.append(wrapper);
}

function renderDemo() {
  const summary = document.querySelector("#stage-summary");
  const stageList = document.querySelector("#stage-list");
  const auditSummary = document.querySelector("#audit-summary");
  if (!summary || !stageList || !auditSummary) {
    return;
  }

  summary.textContent = `${demo.project} reached the ${demo.currentStage} stage after human approval.`;
  const currentIndex = demo.stages.indexOf(demo.currentStage);
  demo.stages.forEach((stage, index) => {
    const item = document.createElement("li");
    item.textContent = stage;
    if (index <= currentIndex) {
      item.classList.add("complete");
    }
    if (index === currentIndex) {
      item.setAttribute("aria-current", "step");
    }
    stageList.append(item);
  });

  addMetric(auditSummary, "Artifacts", demo.artifacts);
  addMetric(auditSummary, "Assignments", demo.assignments);
  addMetric(auditSummary, "Proposals", demo.proposals);
  addMetric(auditSummary, "Audit events", demo.auditEvents);
  addMetric(auditSummary, "Hash chain", demo.auditValid ? "valid" : "invalid");
}

renderDemo();
