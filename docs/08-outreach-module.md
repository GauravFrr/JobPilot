# JobPilot — Outreach Module

## Why This Module Exists

Finding a contact (doc 07) is only valuable if it leads to an actual message. This module turns a discovered contact into a ready-to-send draft, but stops short of sending — outreach is the one place in this system where full automation is deliberately rejected even though it would be technically easy to build.

## Why Outreach Stays Human-in-Loop (Always, No Exceptions)

Unlike applications (which are often screened by ATS software first, so an imperfect submission is low-stakes) outreach is a direct message to a real person who will judge it as a first impression of Gaurav. Reasons this stays manual-send regardless of tier:
- Wrong name/title/context in an auto-sent message is far more damaging than a skipped application — it burns a real relationship-building opportunity, and recruiters talk to each other about spammy outreach.
- A message that reads as obviously bot-generated undermines the entire point of contact-finding, which is to seem more personal and considered than a blind application.
- Volume doesn't help here the way it helps applications — 5 well-considered outreach messages a week outperform 50 generic ones.

## Flow

1. When a `contacts` record exists for a job (any confidence level `>= inferred`), the job card gets a **"Message Contact"** action.
2. Tapping it calls the drafting step: Claude generates a short, personalized connection request or email draft using:
   - The contact's name/title.
   - The specific role and company.
   - One or two genuinely relevant details from Gaurav's tailored resume for that job (e.g., "noticed you're hiring for RAG-focused backend work — I recently took retrieval recall from 23% to 84% on a similar pipeline").
   - Channel-appropriate format: LinkedIn connection note (short, ~300 char limit) vs. email (slightly longer, includes tailored resume as attachment reference).
3. Draft is shown to Gaurav for edit — never auto-sent. Uses the same `message_compose`-style variant pattern already used for his other outreach drafting (e.g., offering 1–2 tone variants: "Direct/confident" vs. "Warm/curious" where it's genuinely ambiguous which fits better).
4. Gaurav copies/sends manually via LinkedIn or his email client. JobPilot logs that a draft was generated and (optionally, if Gaurav marks it) that it was sent — for tracking response rates over time.

## Output Schema (`outreach_drafts` table)

```
id, job_id, contact_id, channel ('linkedin'|'email'), draft_text,
  generated_at, sent (boolean, manually marked), sent_at
```

## Tracking & Feedback Loop

- Dashboard shows a simple outreach log: which contacts were messaged, for which roles, and (if Gaurav updates status manually) whether it led to a response/interview.
- This data isn't used to auto-improve outreach copy in v1 — that's a plausible v2 feature (e.g., noticing which draft style gets better response rates) but requires enough volume to be meaningful first.

## Integration Point with Telegram

Telegram notifications for jobs with a found contact include a "Draft Message" inline button alongside the apply-confirm buttons — tapping it returns the draft text directly in the chat for Gaurav to copy, so outreach doesn't require opening the dashboard if he's moving fast from his phone.
