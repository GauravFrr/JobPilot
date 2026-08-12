# JobPilot — Database Schema (PostgreSQL + pgvector)

## Why This Structure

The schema is organized around the lifecycle of a single job posting (raw → matched → tailored → applied → contact → outreach) so each module (docs 03–08) owns a clear table or set of tables, and the pipeline status is always traceable end-to-end for any given job — this directly supports the audit-trail requirement from doc 06 and the transparency requirement from doc 07.

## Tables

### `jobs_raw`
```sql
id UUID PRIMARY KEY,
source TEXT NOT NULL,                  -- 'remoteok', 'linkedin', 'greenhouse:acme', etc.
source_tier CHAR(1) NOT NULL,          -- 'A' | 'B' | 'C' | 'D'
source_job_id TEXT,
source_url TEXT,
company TEXT NOT NULL,
title TEXT NOT NULL,
description_text TEXT NOT NULL,
location TEXT,
is_remote BOOLEAN,
posted_date DATE,
discovered_at TIMESTAMPTZ DEFAULT now(),
raw_payload JSONB,
status TEXT NOT NULL DEFAULT 'discovered',
  -- discovered | matched | discarded | tailored |
  -- ready_to_apply | applied | skipped | manual_lead | expired
UNIQUE (source, source_job_id)
```

### `resume_profile`
```sql
id UUID PRIMARY KEY,
version INT NOT NULL,
content_json JSONB NOT NULL,   -- structured: experience, projects, skills, target_roles
embedding VECTOR(768),         -- recomputed on edit
created_at TIMESTAMPTZ DEFAULT now(),
is_active BOOLEAN DEFAULT true
```

### `job_scores`
```sql
id UUID PRIMARY KEY,
job_id UUID REFERENCES jobs_raw(id),
resume_profile_version INT NOT NULL,
embedding_score FLOAT,
llm_rerank_score FLOAT,          -- nullable, only set if middle-band rerank ran
final_score FLOAT NOT NULL,
rationale TEXT,
scored_at TIMESTAMPTZ DEFAULT now()
```

### `resume_versions`
```sql
id UUID PRIMARY KEY,
job_id UUID REFERENCES jobs_raw(id),
content_json JSONB NOT NULL,     -- tailored bullets/sections actually used
pdf_path TEXT NOT NULL,
model_used TEXT,
generated_at TIMESTAMPTZ DEFAULT now()
```

### `applications`
```sql
id UUID PRIMARY KEY,
job_id UUID REFERENCES jobs_raw(id),
resume_version_id UUID REFERENCES resume_versions(id),
tier CHAR(1) NOT NULL,
method TEXT,                     -- 'api' | 'form' | 'email' | 'manual'
status TEXT NOT NULL,            -- ready_to_apply | applied | skipped | failed | manual_lead | expired
request_payload_snapshot JSONB,
result JSONB,                    -- response/error details
applied_at TIMESTAMPTZ,          -- set only when Gaurav taps Apply
created_at TIMESTAMPTZ DEFAULT now()
```

### `contacts`
```sql
id UUID PRIMARY KEY,
job_id UUID REFERENCES jobs_raw(id),
name TEXT,
title TEXT,
company TEXT,
linkedin_url TEXT,
email TEXT,
email_confidence TEXT,            -- 'verified' | 'inferred' | 'unverified'
website TEXT,
social_profiles JSONB,
evidence JSONB,                   -- [{field, snippet, source_url}, ...]
found_at TIMESTAMPTZ DEFAULT now()
```

### `outreach_drafts`
```sql
id UUID PRIMARY KEY,
job_id UUID REFERENCES jobs_raw(id),
contact_id UUID REFERENCES contacts(id),
channel TEXT,                     -- 'linkedin' | 'email'
draft_text TEXT NOT NULL,
generated_at TIMESTAMPTZ DEFAULT now(),
sent BOOLEAN DEFAULT false,
sent_at TIMESTAMPTZ
```

### `target_companies`
```sql
id UUID PRIMARY KEY,
name TEXT NOT NULL,
domain TEXT,
careers_url TEXT,
detected_ats TEXT,                -- 'greenhouse' | 'lever' | 'ashby' | null (true custom)
last_crawled_at TIMESTAMPTZ,
is_active BOOLEAN DEFAULT true
```

### `dork_queries`
```sql
id UUID PRIMARY KEY,
query_template TEXT NOT NULL,     -- e.g. 'site:boards.greenhouse.io "{role}" remote'
target_group TEXT,                -- 'ats' | 'tier_b_platforms' | 'career_pages'
role_keyword_source TEXT DEFAULT 'resume_profile.target_roles',
last_run_at TIMESTAMPTZ,
is_active BOOLEAN DEFAULT true,
created_at TIMESTAMPTZ DEFAULT now()
```

### `settings`
```sql
key TEXT PRIMARY KEY,
value JSONB NOT NULL
-- rows: min_match_score, daily_caps_by_platform, platform_toggles, default_answers, telegram_chat_id
```

### `source_health`
```sql
id UUID PRIMARY KEY,
source TEXT NOT NULL,
last_success_at TIMESTAMPTZ,
consecutive_failures INT DEFAULT 0,
last_error TEXT
```

## Indexing Notes

- `jobs_raw`: index on `status`, `source_tier`, `discovered_at` for board queries.
- `job_scores.embedding` and `resume_profile.embedding`: pgvector IVFFlat or HNSW index (HNSW preferred, matches MemoryOS's existing choice) for fast similarity search.
- `applications.status`: index for dashboard lane queries.

## Relationships Summary

`jobs_raw` is the spine — every other table hangs off `job_id`. This makes the job detail page (doc 09) a single set of joins rather than scattered lookups, and makes deleting/archiving a job's full trail (if ever needed) straightforward.
