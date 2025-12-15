# Configurable Intelligence Reports - Implementation Guide

## Overview

OutPace Intelligence now supports **fully configurable** intelligence report generation with custom Perplexity prompts and schedules per tenant.

---

## Features

✅ **Custom Prompt Templates** - Define structured reports with your own format
✅ **Variable Substitution** - Dynamic insertion of company data
✅ **Flexible Scheduling** - Cron expressions for custom timing
✅ **Per-Tenant Configuration** - Each client gets their own setup
✅ **Template Variables** - Automatic replacement of placeholders

---

## Template Variables

Use these placeholders in your prompts - they'll be automatically replaced:

| Variable | Description | Example |
|----------|-------------|---------|
| `{{COMPANY_NAME}}` | Tenant name | "Enchandia" |
| `{{LOOKBACK_DAYS}}` | Days to look back | "14" |
| `{{DEADLINE_WINDOW}}` | Future deadline window | "120" |
| `{{COMPETITORS}}` | Comma-separated list | "Corvus Energy, Shift Clean Energy" |
| `{{INTEREST_AREAS}}` | Areas of interest | "Maritime electrification, Port infrastructure" |
| `{{NAICS_CODES}}` | NAICS codes | "335911, 336611" |
| `{{KEYWORDS}}` | Search keywords | "maritime battery, hybrid ferry" |
| `{{CURRENT_DATE}}` | Today's date | "2025-01-21" |

---

## Cron Schedule Format

Schedule intelligence reports using standard cron expressions:

```
minute hour day month day_of_week
```

### Examples:

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Daily 2 AM UTC | `0 2 * * *` | Default |
| Daily 6 AM UTC | `0 6 * * *` | Morning reports |
| Monday 9 AM | `0 9 * * 1` | Weekly on Monday |
| 1st of month | `0 3 1 * *` | Monthly reports |
| Twice daily | `0 6,18 * * *` | 6 AM and 6 PM |
| Every 6 hours | `0 */6 * * *` | Round the clock |

---

## API Usage

### 1. Update Intelligence Configuration

**Endpoint:** `PUT /api/config/tenants/{tenant_id}/intelligence-config`

**Example Request:**

```json
{
  "enabled": true,
  "perplexity_prompt_template": "Your full prompt here with {{COMPANY_NAME}} variables...",
  "schedule_cron": "0 6 * * *",
  "lookback_days": 14,
  "deadline_window_days": 120,
  "target_sources": [
    "site:maritime.dot.gov",
    "site:grants.gov",
    "site:sam.gov"
  ],
  "report_sections": [
    "executive_summary",
    "top_actions",
    "opportunities",
    "policy_regulation",
    "defense_signals",
    "sled_by_state",
    "competitor_moves"
  ],
  "scoring_weights": {
    "relevance": 25,
    "amount": 20,
    "timeline": 15,
    "win_probability": 15,
    "strategic_fit": 15,
    "partner_potential": 10
  }
}
```

**Response:**

```json
{
  "status": "success",
  "message": "Intelligence configuration updated",
  "config": { ... }
}
```

---

### 2. Get Current Configuration

**Endpoint:** `GET /api/config/tenants/{tenant_id}/intelligence-config`

**Response:**

```json
{
  "tenant_id": "abc123",
  "tenant_name": "Enchandia",
  "intelligence_config": {
    "enabled": true,
    "perplexity_prompt_template": "...",
    "schedule_cron": "0 6 * * *",
    "lookback_days": 14,
    ...
  }
}
```

---

## Example: Enchandia Intelligence Report

Here's how to set up the sample prompt you provided:

```python
import requests

# Your prompt template (excerpt)
prompt_template = \"\"\"
{{COMPANY_NAME}} — Washington Update — FED & SLED Opportunity Report

**INSTRUCTIONS TO AGENT**
- Role: Washington K Street + SLED Intelligence & BD Operator for {{COMPANY_NAME}}
- Window: last {{LOOKBACK_DAYS}} days; deadlines {{DEADLINE_WINDOW}} days
- Current date: {{CURRENT_DATE}}

**COMPANY CONTEXT**
- Company: {{COMPANY_NAME}}
- Competitors: {{COMPETITORS}}
- Keywords/NAICS: {{NAICS_CODES}}
- Interest Areas: {{INTEREST_AREAS}}

**OUTPUT SPEC**

## Washington Update — FED, SLED and International Opportunity Report
# {{COMPANY_NAME}}

### 1. Executive summary
...

### 2. Top actions
...

### 3. Opportunities
...

[Full template continues...]
\"\"\"

# Configure for Enchandia
config = {
    "enabled": True,
    "perplexity_prompt_template": prompt_template,
    "schedule_cron": "0 6 * * 1",  # Monday 6 AM
    "lookback_days": 14,
    "deadline_window_days": 120,
    "target_sources": [
        "site:maritime.dot.gov",
        "site:grants.gov",
        "site:sam.gov",
        "site:navy.mil"
    ]
}

# Update via API
response = requests.put(
    f"http://localhost:8001/api/config/tenants/{tenant_id}/intelligence-config",
    json=config,
    headers={"Authorization": f"Bearer {token}"}
)

print(response.json())
```

---

## How It Works

1. **Prompt Preparation:**
   - System reads your `perplexity_prompt_template`
   - Replaces all `{{VARIABLE}}` placeholders with actual data
   - Adds company context from tenant's `search_profile`

2. **Scheduled Execution:**
   - APScheduler runs based on `schedule_cron`
   - Queries Perplexity API with your custom prompt
   - Uses `sonar-pro` model with 4000 max tokens
   - Focuses on recent data (past week)

3. **Report Generation:**
   - Perplexity generates structured response
   - Includes citations and source URLs
   - Saved to `intelligence` collection
   - Title: "{Company} - Intelligence Report - YYYY-MM-DD"

4. **Access:**
   - Reports appear in tenant's Intelligence Feed
   - Full content with citations
   - Filterable and searchable

---

## Best Practices

### Prompt Design

1. **Be Specific:** Define exact output format (tables, bullets, sections)
2. **Request Sources:** Always ask for citations and links
3. **Set Context:** Include company info, competitors, and goals
4. **Use Structure:** Numbered sections help Perplexity organize
5. **Specify Dates:** Request absolute dates, not relative

### Schedule Selection

- **Daily (2-6 AM):** For time-sensitive opportunities
- **Weekly (Monday AM):** For comprehensive reviews
- **Monthly (1st):** For strategic updates
- **Twice daily:** For high-priority clients

### Testing

1. Start with a simple template and daily schedule
2. Review generated reports for quality
3. Refine prompt based on output
4. Adjust schedule based on client needs

---

## Troubleshooting

### Reports Not Generating

- Check `intelligence_config.enabled` is `true`
- Verify cron expression format (5 parts)
- Check Perplexity API key is configured
- Look for errors in `/api/admin/dashboard` sync logs

### Poor Quality Reports

- Add more specific instructions to prompt
- Include example output format
- Request structured data (tables, bullets)
- Specify "official sources" and "absolute dates"

### Schedule Not Working

- Validate cron expression: https://crontab.guru/
- Check server timezone (always UTC)
- Restart backend after config changes
- View scheduler logs for errors

---

## Migration Notes

### Existing Tenants

Existing tenants without `intelligence_config` will:
- Use default daily 2 AM schedule
- Generate simple competitor/interest area queries
- Continue working without changes

### Upgrade Path

1. Add `intelligence_config` to tenant document
2. Set `perplexity_prompt_template` with your custom prompt
3. Configure `schedule_cron` if needed
4. Enable with `enabled: true`
5. Next scheduled run will use new config

---

## Support

For issues or questions:
- Check backend logs: `tail -f /var/log/supervisor/backend.err.log`
- View sync logs: `GET /api/admin/dashboard`
- Manual trigger: `POST /api/admin/sync/{tenant_id}`
- Documentation: This file

---

**Last Updated:** 2025-01-21
**Version:** 1.0.0
