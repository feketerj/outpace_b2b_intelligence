# Automated Reports Configuration Guide

## Overview

OutPace Intelligence supports **TWO types of automated reports** per client, each with independent scheduling:

---

## 1. HigherGov Opportunities (Contracts & Grants)

### Location: **Search Tab → Auto-Update Settings**

### Configuration:

**☑ Enable Auto-Update**
- Toggle on/off
- When ON: System polls HigherGov automatically

**Update Interval: [__24__] hours**
- How often to check for new opportunities
- Options: 1-168 hours
- Examples:
  - 1 hour = Real-time monitoring
  - 6 hours = 4 times daily
  - 12 hours = Twice daily
  - 24 hours = Daily (default)
  - 168 hours = Weekly

### What Happens:
```
Every X hours (your configured interval):
  1. Poll HigherGov using Search ID
  2. Fetch new contracts/grants
  3. Run each through Mistral scoring agent
  4. Add AI relevance summary
  5. Store in database
  6. Appear in client dashboard
```

### Example Configurations:

**High-Priority Client (Enchandia):**
- Auto-Update: ✓ ON
- Interval: 6 hours (4x daily)
- Result: Fresh opportunities every 6 hours

**Standard Client:**
- Auto-Update: ✓ ON
- Interval: 24 hours (daily)
- Result: Daily batch at consistent time

**On-Demand Client:**
- Auto-Update: ✗ OFF
- Result: Only updates when "Sync Now" button clicked

---

## 2. Intelligence Reports (Perplexity)

### Location: **Intelligence Tab → Report Schedule**

### Configuration:

**☑ Enable Automated Intelligence Reports**
- Toggle on/off
- When ON: Perplexity generates reports on schedule

**Schedule Presets:**
- ⚪ Daily at 2 AM UTC (`0 2 * * *`)
- ⚪ Daily at 6 AM UTC (`0 6 * * *`)
- ⚪ Weekly - Monday 9 AM (`0 9 * * 1`)
- ⚪ Twice Weekly - Mon & Thu 9 AM (`0 9 * * 1,4`)
- ⚪ Monthly - 1st at 3 AM (`0 3 1 * *`)
- ⚪ Every 6 Hours (`0 */6 * * *`)
- ⚪ Every 12 Hours (`0 */12 * * *`)
- ⚪ Custom Cron...

**OR Custom Cron Expression:**
- Manual input: `minute hour day month weekday`
- Example: `0 6 * * 1` = Monday 6 AM

### What Happens:
```
At scheduled time (e.g., Monday 6 AM):
  1. Read your custom Perplexity prompt template
  2. Replace variables ({{COMPANY_NAME}}, etc.)
  3. Query Perplexity API
  4. Generate Washington Update style report
  5. Store with citations
  6. Appear in Intelligence Feed
```

### Example Configurations:

**Enchandia (Washington Update):**
- Enabled: ✓ ON
- Schedule: Weekly - Monday 9 AM
- Prompt: Full Enchandia Washington Update template
- Result: Comprehensive report every Monday morning

**Real-Time Monitoring Client:**
- Enabled: ✓ ON
- Schedule: Every 6 Hours
- Prompt: Brief competitive update
- Result: 4 reports daily

**Monthly Strategic Client:**
- Enabled: ✓ ON
- Schedule: Monthly - 1st at 3 AM
- Prompt: In-depth market analysis
- Result: One comprehensive report per month

---

## Configuration Per Client Summary

### For Each Client You Configure:

**Search Tab (HigherGov Polling):**
```
Auto-Update: [ON/OFF]
Interval: [24] hours
↓
Polls contracts/grants every 24 hours
```

**Intelligence Tab (Perplexity Reports):**
```
Enabled: [ON/OFF]
Schedule: [Weekly - Monday 9 AM]
Prompt: [Your custom template]
↓
Generates report every Monday at 9 AM
```

**Both run independently and automatically!**

---

## UI Navigation

### To Configure Automated Reports:

1. **Login:** https://branding-fix.preview.emergentagent.com
2. **Sidebar:** Click "Tenants"
3. **Click "Configure"** on tenant
4. **Search Tab:**
   - Set HigherGov Search ID
   - Toggle "Enable Auto-Update"
   - Set update interval (hours)
5. **Intelligence Tab:**
   - Toggle "Enable Automated Intelligence Reports"
   - Select schedule preset OR enter custom cron
   - Paste your prompt template
6. **Save**

### Result:
- HigherGov: Polls every X hours
- Perplexity: Generates reports on schedule
- Both automated, no manual intervention needed

---

## Manual Overrides

### For Admin or Client User:

**Manual Sync Button** (on tenant cards):
- Immediately triggers both HigherGov + Perplexity
- Bypasses schedule
- Shows count of synced items

**Singular Opportunity Pull:**
- Enter specific opportunity ID
- Fetch one contract directly
- Useful for ad-hoc additions

---

## Scheduling Examples by Client Type

### High-Value Client (Enchandia):
- **HigherGov:** Every 6 hours (real-time monitoring)
- **Intelligence:** Weekly Monday 9 AM (comprehensive)

### Standard Client:
- **HigherGov:** Every 24 hours (daily batch)
- **Intelligence:** Twice weekly (Mon/Thu)

### Low-Touch Client:
- **HigherGov:** Every 48 hours
- **Intelligence:** Monthly

### On-Demand Client:
- **HigherGov:** OFF (manual only)
- **Intelligence:** OFF (manual only)

---

## Current Implementation Status

✅ **HigherGov Auto-Update:**
   - Toggle: Implemented
   - Interval: Implemented
   - Manual sync: Implemented
   - Search ID based: Implemented

✅ **Intelligence Auto-Reports:**
   - Toggle: Implemented
   - Schedule presets: Implemented
   - Custom cron: Implemented
   - Template variables: Implemented
   - APScheduler: Implemented

✅ **Both Visible in UI:** Intelligence tab has clear "Automated Intelligence Reports" header with schedule dropdown

---

## Testing

**Test Automated Setup:**
1. Configure Enchandia tenant
2. Intelligence tab → Enable, set "Weekly - Monday 9 AM"
3. Search tab → Enable auto-update, set 24 hours
4. Save
5. Check `/app/backend/INTELLIGENCE_CONFIG_GUIDE.md` for details

**Verify:**
- Backend logs show scheduler setup
- Database shows tenant config saved
- Next scheduled run calculated

---

**Both automated report systems are fully implemented and configurable per client!**
