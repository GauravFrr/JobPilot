# Antigravity Rules for JobPilot

## Mandatory Context Reading before Tasks

- **MANDATORY CONTEXT READ FIRST**: Every time the user assigns a task, before making any changes, running any terminal commands, or generating code, you MUST first read all relevant design documents, modules specs, plans, and instructions in the `docs/` folder (such as `docs/19-coding-rules-and-project-structure.md`, `docs/18-implementation-plan.md`, `docs/10-telegram-bot.md`, `docs/17-backend-schema.md`) and the workspace `AGENT.md` file. 
- You must always cross-reference instructions, variables, paths, and behavioral rules with the original docs rather than proceeding from memory or making assumptions.

## Test and Debug Data Integrity and Disclosure

- **DISCLOSE DATA MODIFICATIONS IMMEDIATELY**: Any test, mock, or debugging action that manually adds, modifies, or deletes data in the database (including `jobs_raw`, `job_scores`, `applications`, `contacts`, `resume_versions`, or any other table) MUST be explicitly disclosed to the user in the same message reporting the results of that action.
- **NO SILENT DATA MANIPULATION**: Never inject fictional or modified data (such as mock contact details, emails, or custom descriptions) into real, live-scraped database rows without prior user consent and immediate, clear disclosure.
- **ISOLATION OF TEST DATA**: All test data manipulation must leverage the existing `is_test = True` flag pattern to keep mock pipeline runs strictly isolated from real output, avoiding undisclosed side effects.
