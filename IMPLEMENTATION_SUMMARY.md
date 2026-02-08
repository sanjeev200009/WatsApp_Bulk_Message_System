# Implementation Summary: Experience-Level Targeting for WhatsApp Job Campaigns

## Overview
Successfully implemented experience-level targeting system that allows sending targeted WhatsApp job alerts to candidates based on their experience level (Junior, Mid, Senior) using Brevo list segmentation.

## Changes Made

### 1. Configuration Layer (`src/config.py`)
**Added:**
- `EXPERIENCE_LIST_MAP`: JSON mapping of experience levels to Brevo list IDs
- `JOB_CAMPAIGN_ID`: Unique campaign identifier for duplicate prevention
- `TEMPLATE_NAME_JUNIOR/MID/SENIOR`: Optional level-specific templates
- `get_experience_list_map()`: Parses JSON mapping
- `get_template_name_for_level()`: Returns appropriate template per level
- Updated validation to check campaign ID in production

**Example:**
```python
EXPERIENCE_LIST_MAP='{"junior":123, "mid":456, "senior":789}'
JOB_CAMPAIGN_ID='2026-02-07-backend-eng-001'
```

### 2. Database Layer (`src/database.py`)
**Schema Changes:**
```sql
CREATE TABLE send_history (
    phone TEXT NOT NULL,
    campaign_key TEXT NOT NULL,      -- Changed from template_name
    experience_level TEXT,            -- NEW
    list_id INTEGER,                  -- NEW
    sent_at DATETIME NOT NULL,
    status TEXT NOT NULL,
    wamid TEXT,
    error TEXT,
    UNIQUE(phone, campaign_key)       -- Never repeat per campaign
)
```

**Method Updates:**
- `get_eligible_recipients()`: Now accepts `list_id`, `campaign_key`, `experience_level`
- `was_sent_before()`: Uses `campaign_key` instead of `template_name`
- `record_send()`: Stores `campaign_key`, `experience_level`, `list_id`
- `create_tables_if_dev()`: Updated schema with new columns

**Campaign Key Format:**
```
campaign_key = "{campaign_id}:{template_name}"
Example: "2026-02-07-job-003:job_alert_senior"
```

### 3. WhatsApp Client (`src/whatsapp_client.py`)
**Added Support for Template Variables:**
```python
send_template_message(
    to_phone="1234567890",
    template_name="job_alert",
    body_variables={
        'job_title': 'Senior Backend Engineer',
        'company': 'TechCorp',
        'location': 'Remote',
        'apply_link': 'https://apply.here'
    }
)
```

Variables are sent in order: `job_title`, `company`, `location`, `apply_link`

### 4. Main CLI (`src/main.py`)

#### New CLI Arguments

**Send Command:**
```bash
--experience {junior|mid|senior|all}  # Target specific level
--campaign-id "YYYY-MM-DD-job-###"    # Override JOB_CAMPAIGN_ID
--job-title "Job Title"               # Template variable
--company "Company Name"              # Template variable
--location "Location"                 # Template variable
--apply-link "https://..."           # Template variable
```

**Dry-Run Command:**
```bash
--experience {junior|mid|senior|all}  # Preview specific level
--campaign-id "campaign-id"           # Check duplicates for campaign
```

#### Updated Logic
- **cmd_send()**: Iterates through experience levels, fetches from specific lists
- **cmd_dry_run()**: Shows eligible recipients per experience level
- Both maintain rate limiting and error spike protection

### 5. Documentation

**Updated Files:**
- `README.md`: Comprehensive documentation with examples
- `.env.example`: Added new configuration fields
- `.env.job-campaign-example`: Example configuration for job campaigns

## Usage Flow

### Step 1: Setup Brevo Lists
```
1. Create lists in Brevo:
   - "Junior Developers" (ID: 123)
   - "Mid Developers" (ID: 456)
   - "Senior Developers" (ID: 789)
   
2. Add contacts to appropriate lists
```

### Step 2: Configure .env
```ini
EXPERIENCE_LIST_MAP={"junior":123, "mid":456, "senior":789}
JOB_CAMPAIGN_ID=2026-02-07-backend-eng-001
TEMPLATE_NAME=job_alert
```

### Step 3: Validate
```bash
python -m src.main validate
```

### Step 4: Dry Run
```bash
# Preview all levels
python -m src.main dry-run --campaign-id "2026-02-07-backend-eng-001"

# Preview senior only
python -m src.main dry-run --experience senior --campaign-id "2026-02-07-backend-eng-001"
```

### Step 5: Send Campaign
```bash
# Send to all levels
python -m src.main send --confirm \
  --campaign-id "2026-02-07-backend-eng-001" \
  --job-title "Backend Engineer" \
  --company "TechCorp" \
  --location "Remote" \
  --apply-link "https://jobs.techcorp.com/apply/123"

# Send to senior only
python -m src.main send --confirm \
  --experience senior \
  --campaign-id "2026-02-07-senior-backend-001" \
  --job-title "Senior Backend Engineer" \
  --company "TechCorp" \
  --location "San Francisco, CA" \
  --apply-link "https://jobs.techcorp.com/apply/456"
```

## Key Features

### 1. Never-Repeat Protection
- Each `(phone, campaign_key)` can only receive ONE message
- Different campaigns can send to same phone
- Example:
  - Campaign A: `2026-02-07-job-001:job_alert_junior` ✅
  - Campaign B: `2026-02-08-job-002:job_alert_junior` ✅ (different campaign)
  - Campaign A again: ❌ (already sent)

### 2. Experience-Level Targeting
- Fetches contacts ONLY from specified Brevo list
- List membership = consent gate
- Can target one level or all levels in a single run

### 3. Template Personalization
- Supports 4 body variables: job_title, company, location, apply_link
- Variables inserted in order into WhatsApp template
- Can use same template for all levels or different templates per level

### 4. Production Safety
- Requires `--confirm` flag in production
- Requires `JOB_CAMPAIGN_ID` in production
- Rate limiting across all levels combined
- Error spike detection stops campaign

### 5. Comprehensive Logging
- Campaign key logged with every send
- Experience level tracked
- List ID recorded
- Full audit trail in send_history.db

## Example Scenarios

### Scenario 1: Send Same Job to All Levels
```bash
python -m src.main send --confirm \
  --experience all \
  --campaign-id "2026-02-07-fullstack-001" \
  --job-title "Full Stack Developer" \
  --company "WebCo" \
  --location "Remote" \
  --apply-link "https://webco.com/apply"
```

**Result:**
- Sends to junior list (ID: 123)
- Then to mid list (ID: 456)
- Then to senior list (ID: 789)
- Total limited by DAILY_LIMIT across all levels

### Scenario 2: Send Different Jobs to Different Levels
```bash
# Senior role
python -m src.main send --confirm \
  --experience senior \
  --campaign-id "2026-02-07-senior-arch-001" \
  --job-title "Senior Software Architect" \
  --company "BigTech" \
  --location "Seattle, WA" \
  --apply-link "https://bigtech.com/senior"

# Junior role (separate campaign)
python -m src.main send --confirm \
  --experience junior \
  --campaign-id "2026-02-07-junior-dev-001" \
  --job-title "Junior Developer" \
  --company "Startup" \
  --location "Austin, TX" \
  --apply-link "https://startup.com/junior"
```

**Result:**
- Senior candidates get senior job
- Junior candidates get junior job
- No overlap, tracked separately by campaign_key

### Scenario 3: Resend Same Job to New Candidates
```bash
# First send (February 7)
python -m src.main send --confirm \
  --campaign-id "2026-02-07-backend-001" \
  --job-title "Backend Engineer" \
  ... other params ...

# Add new candidates to Brevo lists

# Second send (February 14) - NEW campaign ID
python -m src.main send --confirm \
  --campaign-id "2026-02-14-backend-001" \  # Different ID
  --job-title "Backend Engineer" \
  ... same job params ...
```

**Result:**
- Old candidates won't receive (already got 2026-02-07 campaign)
- New candidates will receive (haven't received 2026-02-14 campaign)
- Different campaign_key allows resending

## Database Tracking

**send_history Table Example:**
```
| phone        | campaign_key                      | experience_level | list_id | status  |
|--------------|-----------------------------------|------------------|---------|---------|
| +1234567890  | 2026-02-07-job-003:job_alert_senior | senior         | 789     | success |
| +9876543210  | 2026-02-07-job-003:job_alert_junior | junior         | 123     | success |
| +5555555555  | 2026-02-08-job-005:job_alert_mid    | mid            | 456     | success |
```

## Backward Compatibility

- If `EXPERIENCE_LIST_MAP` not set: works in legacy mode
- Falls back to `BREVO_LIST_ID` if no experience mapping
- `campaign_key` defaults to `template_name` if no `JOB_CAMPAIGN_ID`
- Existing send_history database auto-migrates on first run

## Testing

All features have been implemented and validated:
- ✅ Configuration parsing
- ✅ Database schema updated
- ✅ Campaign key generation
- ✅ Experience-level filtering
- ✅ Template variables support
- ✅ CLI argument parsing
- ✅ Backward compatibility
- ✅ Production safeguards

## Next Steps for User

1. **Update .env** with experience list mapping
2. **Set JOB_CAMPAIGN_ID** for first campaign
3. **Run validate** to check configuration
4. **Run dry-run** to preview recipients
5. **Execute send** with --confirm flag
6. **Monitor logs** for results

## Files Modified

- `src/config.py` - Experience mapping, campaign ID
- `src/database.py` - Campaign key tracking, list targeting
- `src/whatsapp_client.py` - Template variables
- `src/main.py` - CLI args, experience iteration
- `README.md` - Complete documentation
- `.env.example` - New configuration fields
- `.env.job-campaign-example` - Example setup (NEW)
- `IMPLEMENTATION_SUMMARY.md` - This file (NEW)

## Success Metrics

- Never-repeat protection: ✅ Per campaign_key
- Experience targeting: ✅ Via Brevo lists
- Template personalization: ✅ 4 job variables
- Rate limiting: ✅ Preserved across levels
- Production safety: ✅ Requires --confirm + campaign ID
- Comprehensive logging: ✅ Campaign tracking in SQLite
