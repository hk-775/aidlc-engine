"use strict";

const scenarios = Object.freeze({
  lifecycle: Object.freeze({
    eyebrow: "Lifecycle flow",
    title: "A bounded request becomes a recorded stage decision",
    summary:
      "The engine accepts a command, validates authority and policy, applies one adjacent lifecycle operation, and persists the result.",
    steps: Object.freeze([
      Object.freeze({
        title: "Receive command",
        lane: "Interface",
        copy:
          "The CLI parses the command, constructs the asserted actor, and prepares a stable JSON response boundary.",
      }),
      Object.freeze({
        title: "Validate request",
        lane: "Application service",
        copy:
          "The service validates identifiers, current state, assignment scope, evidence references, and expected operation shape.",
      }),
      Object.freeze({
        title: "Apply policy",
        lane: "Authority boundary",
        copy:
          "Fail-closed policy rules reject unsafe agent authority, missing human separation, and weakened mandatory gates.",
      }),
      Object.freeze({
        title: "Advance one stage",
        lane: "Lifecycle core",
        copy:
          "Only the next adjacent stage can be proposed or approved. Release is a recorded terminal decision, not deployment.",
      }),
      Object.freeze({
        title: "Commit transaction",
        lane: "Persistence",
        copy:
          "The repository prepares one event and state pair, exclusively creates the audit event, then atomically replaces state.",
      }),
      Object.freeze({
        title: "Return JSON",
        lane: "Interface",
        copy:
          "Success and expected failures return machine-readable objects with stable status and error semantics.",
      }),
    ]),
  }),
  governance: Object.freeze({
    eyebrow: "Governance flow",
    title: "Agents prepare work; people retain delivery authority",
    summary:
      "Proposal capabilities are separated from approval, risk acceptance, and release authority throughout the lifecycle.",
    steps: Object.freeze([
      Object.freeze({
        title: "Propose bounded work",
        lane: "Agent or human",
        copy:
          "An agent may propose work only for itself and only for the current stage. A different human must approve it.",
      }),
      Object.freeze({
        title: "Register evidence",
        lane: "Assignee",
        copy:
          "Artifact metadata must match an active assignment when submitted by an agent and must use a safe relative locator.",
      }),
      Object.freeze({
        title: "Propose transition",
        lane: "Agent or human",
        copy:
          "The proposal names current-stage evidence and captures the policy gate without changing lifecycle state.",
      }),
      Object.freeze({
        title: "Check independence",
        lane: "Policy boundary",
        copy:
          "The proposer cannot approve the same transition, and one actor cannot satisfy multiple required approvals.",
      }),
      Object.freeze({
        title: "Cover named roles",
        lane: "Human gate",
        copy:
          "Design requires a technical reviewer. Release requires distinct release-manager and risk-owner approvals.",
      }),
      Object.freeze({
        title: "Record decision",
        lane: "Lifecycle core",
        copy:
          "The completed gate and stage change are written in one transaction. No external delivery action follows.",
      }),
    ]),
  }),
  persistence: Object.freeze({
    eyebrow: "Persistence flow",
    title: "Every mutation is recoverable and hash-linked",
    summary:
      "A project lock, complete-chain verification, prepared transaction, exclusive event append, and atomic state replacement form one local commit.",
    steps: Object.freeze([
      Object.freeze({
        title: "Acquire project lock",
        lane: "Repository",
        copy:
          "A POSIX advisory lock serializes initialization, verified reads, recovery, and mutation within the supported local boundary.",
      }),
      Object.freeze({
        title: "Recover pending pair",
        lane: "Repository",
        copy:
          "If a valid prepared transaction exists, the repository completes that exact event and state pair before continuing.",
      }),
      Object.freeze({
        title: "Verify current history",
        lane: "Audit",
        copy:
          "The full event directory is checked for sequence, filenames, hashes, project identity, event count, and final state digest.",
      }),
      Object.freeze({
        title: "Mutate a copy",
        lane: "Application service",
        copy:
          "Domain logic runs against a deep copy, so a failed validation or authorization check writes no durable change.",
      }),
      Object.freeze({
        title: "Prepare next pair",
        lane: "Repository",
        copy:
          "The canonical next event and state snapshot are atomically written to the pending transaction file.",
      }),
      Object.freeze({
        title: "Append and replace",
        lane: "Repository",
        copy:
          "The event file is created exclusively and flushed before state.json is atomically replaced and the directory is flushed.",
      }),
      Object.freeze({
        title: "Remove pending marker",
        lane: "Repository",
        copy:
          "The completed pending file is removed only after the event and state are durable, making retry idempotent.",
      }),
    ]),
  }),
});

const scenarioButtons = Array.from(
  document.querySelectorAll("[data-scenario]"),
);
const scenarioEyebrow = document.querySelector("#scenario-eyebrow");
const scenarioTitle = document.querySelector("#scenario-title");
const scenarioSummary = document.querySelector("#scenario-summary");
const stepList = document.querySelector("#architecture-steps");
const stepPosition = document.querySelector("#step-position");
const stepTitle = document.querySelector("#step-title");
const stepCopy = document.querySelector("#step-copy");
const previousButton = document.querySelector("#previous-step");
const playButton = document.querySelector("#play-flow");
const nextButton = document.querySelector("#next-step");

let activeScenario = "lifecycle";
let activeStep = 0;
let timerId = null;

function stopPlayback() {
  if (timerId !== null) {
    window.clearInterval(timerId);
    timerId = null;
  }
  if (playButton) {
    playButton.textContent = "Play";
    playButton.setAttribute("aria-pressed", "false");
  }
}

function selectStep(index) {
  const scenario = scenarios[activeScenario];
  activeStep = Math.max(0, Math.min(index, scenario.steps.length - 1));
  render();
}

function createStepButton(step, index) {
  const item = document.createElement("li");
  const button = document.createElement("button");
  const number = document.createElement("span");
  const label = document.createElement("strong");
  const lane = document.createElement("small");

  button.type = "button";
  button.className = "architecture-step";
  number.textContent = String(index + 1);
  label.textContent = step.title;
  lane.textContent = step.lane;
  button.append(number, label, lane);
  button.addEventListener("click", () => {
    stopPlayback();
    selectStep(index);
  });

  if (index < activeStep) {
    button.classList.add("complete");
  }
  if (index === activeStep) {
    button.classList.add("active");
    button.setAttribute("aria-current", "step");
  }

  item.append(button);
  return item;
}

function render() {
  const scenario = scenarios[activeScenario];
  const step = scenario.steps[activeStep];
  if (
    !scenarioEyebrow ||
    !scenarioTitle ||
    !scenarioSummary ||
    !stepList ||
    !stepPosition ||
    !stepTitle ||
    !stepCopy ||
    !previousButton ||
    !nextButton
  ) {
    return;
  }

  scenarioEyebrow.textContent = scenario.eyebrow;
  scenarioTitle.textContent = scenario.title;
  scenarioSummary.textContent = scenario.summary;
  stepList.replaceChildren(
    ...scenario.steps.map((candidate, index) =>
      createStepButton(candidate, index),
    ),
  );
  stepPosition.textContent =
    `Step ${activeStep + 1} of ${scenario.steps.length} · ${step.lane}`;
  stepTitle.textContent = step.title;
  stepCopy.textContent = step.copy;
  previousButton.disabled = activeStep === 0;
  nextButton.disabled = activeStep === scenario.steps.length - 1;
}

function chooseScenario(name) {
  if (!Object.hasOwn(scenarios, name)) {
    return;
  }
  stopPlayback();
  activeScenario = name;
  activeStep = 0;
  scenarioButtons.forEach((button) => {
    const selected = button.dataset.scenario === name;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  render();
}

scenarioButtons.forEach((button) => {
  button.addEventListener("click", () => {
    chooseScenario(button.dataset.scenario || "");
  });
});

if (previousButton) {
  previousButton.addEventListener("click", () => {
    stopPlayback();
    selectStep(activeStep - 1);
  });
}

if (nextButton) {
  nextButton.addEventListener("click", () => {
    stopPlayback();
    selectStep(activeStep + 1);
  });
}

if (playButton) {
  const reducedMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) {
    playButton.disabled = true;
    playButton.textContent = "Auto-play off";
  } else {
    playButton.addEventListener("click", () => {
      if (timerId !== null) {
        stopPlayback();
        return;
      }
      playButton.textContent = "Pause";
      playButton.setAttribute("aria-pressed", "true");
      timerId = window.setInterval(() => {
        const lastIndex = scenarios[activeScenario].steps.length - 1;
        if (activeStep >= lastIndex) {
          stopPlayback();
          return;
        }
        activeStep += 1;
        render();
      }, 1400);
    });
  }
}

render();
