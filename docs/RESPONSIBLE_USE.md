# Responsible use

## Intended use

AI-DLC Engine is intended for local evaluation of human-governed agent-assisted
delivery workflows using synthetic or low-sensitivity material.

Suitable experiments include:

- testing evidence requirements;
- studying separation between proposal and approval;
- reviewing role-based gates;
- exercising audit verification; and
- prototyping a policy vocabulary.

## Human responsibility

A lifecycle gate is not a substitute for judgment. Human approvers should:

- inspect the referenced evidence;
- verify artifact content against its digest when relevant;
- understand the proposed impact;
- disclose conflicts of interest;
- reject unclear or incomplete work; and
- avoid approving under time or automation pressure.

AI-DLC Engine records an asserted approval. It does not prove that the review was
competent, independent in the real world, or legally sufficient.

## Agent boundaries

Use agents only for proposal-oriented tasks. Do not wrap the CLI in a way that:

- labels an agent process as a human;
- grants an agent access to human credentials;
- automatically converts a proposal into an approval;
- performs a merge, deployment, or release after a stage change without a
  separate authorized system; or
- treats a generated artifact as verified evidence.

## Data handling

The local store is not encrypted and can include names, rationales, and artifact
metadata. Use synthetic identifiers and avoid:

- credentials and private keys;
- personal or regulated records;
- confidential source or designs;
- customer and incident data;
- production URLs; and
- proprietary evidence without authorization.

## Decision sensitivity

Do not rely on this alpha for safety-critical, medical, financial, employment,
legal, public-infrastructure, or other high-impact decisions. The project has
not been validated for those contexts.

## Misleading use

Do not represent:

- a release-stage record as proof that software was safely released;
- a valid hash chain as proof of author identity;
- passing tests as a security certification;
- policy conformance as legal compliance; or
- the static demo as a live production service.

## Monitoring for over-reliance

Evaluators should look for:

- approvals happening immediately after agent proposals;
- one person using multiple identifiers;
- generic evidence reused across stages;
- repeated risk acceptance without mitigation;
- disabled assignment scoping;
- unexplained audit verification failures; and
- external automation triggered solely by lifecycle stage.

## Reporting harm or misuse

Use the private security route for authority bypass, data exposure, or audit
integrity issues. Use governance and conduct routes for coercive approval,
misrepresentation, or harmful project use.
