# WhatsApp Job Campaign CLI

A production-ready Python CLI application for sending **targeted WhatsApp job alerts** to candidates based on experience level. Uses WhatsApp Cloud API and Brevo (Sendinblue) for contact management with experience-level list segmentation.

## 🎯 Features

- **Experience-Level Targeting**: Send different job ads to junior, mid, and senior candidates
- **Brevo List Integration**: Organize contacts by experience level using Brevo lists
- **Campaign Tracking**: Never-repeat protection per job campaign using SQLite
- **Template Personalization**: Support for job variables (title, company, location, apply link)
- **WhatsApp Cloud API**: Official Meta WhatsApp Business API with image templates
- **Rate Limited**: Configurable daily limits and inter-message delays
- **Compliance First**: Respects opt-out preferences and blacklist status
- **Comprehensive Logging**: Structured logs for auditing and debugging

## 📋 Prerequisites

- Python 3.9+
- Meta Business Account with WhatsApp Cloud API enabled
- **Brevo Account**: API Key v3 required
- **Approved Marketing Templates**: Create templates in Meta Business Manager
- **Brevo Lists**: Set up separate lists for each experience level (Junior, Mid, Senior)

## 🚀 Installation

### 1. Clone and setup virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and configure:
```bash
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac
```

## ⚙️ Configuration Guide

### Required Settings

#### Environment
```ini
ENV=test  # or 'prod' for production
```

#### WhatsApp Cloud API
```ini
PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_TOKEN=your_access_token
WA_API_VERSION=v21.0
```

#### Brevo (Contact Database)
```ini
BREVO_API_KEY=xkeysib-your-api-key-here
BREVO_PHONE_ATTRIBUTE=SMS  # Attribute containing phone number
BREVO_OPT_OUT_ATTRIBUTE=OPT_OUT
```

#### Experience-Level Targeting (Job Campaigns)
```ini
# Map experience levels to Brevo list IDs
EXPERIENCE_LIST_MAP={"junior":123, "mid":456, "senior":789}

# Unique campaign ID to prevent duplicate sends
JOB_CAMPAIGN_ID=2026-02-07-senior-backend-001
```

> **How to get List IDs**: In Brevo, go to Contacts → Lists. Click on each list and the ID will be in the URL.

#### Templates
```ini
# Default template (used if level-specific templates not set)
TEMPLATE_NAME=job_alert_template

# Optional: Different templates per level
TEMPLATE_NAME_JUNIOR=job_alert_junior
TEMPLATE_NAME_MID=job_alert_mid
TEMPLATE_NAME_SENIOR=job_alert_senior

LANGUAGE_CODE=en
IMAGE_URL=https://example.com/job-header.jpg
```

#### Rate Limiting
```ini
DAILY_LIMIT=100
SEND_DELAY_SECONDS=5
MAX_RETRIES=2
```

## 📖 Usage

### 1. Validate Environment
Check if credentials and connections are working:
```bash
python -m src.main validate
```

### 2. Dry Run
Preview who would receive messages without sending:

```bash
# Preview all experience levels
python -m src.main dry-run --campaign-id "2026-02-07-job-003"

# Preview only senior candidates
python -m src.main dry-run --experience senior --campaign-id "2026-02-07-job-003"

# Limit preview
python -m src.main dry-run --experience junior --limit 10
```

### 3. Send Job Campaign

#### Send to all experience levels
```bash
python -m src.main send \
  --confirm \
  --campaign-id "2026-02-07-backend-eng-001" \
  --job-title "Backend Engineer" \
  --company "TechCorp" \
  --location "Remote" \
  --apply-link "https://jobs.techcorp.com/apply/123"
```

#### Send to senior level only
```bash
python -m src.main send \
  --confirm \
  --experience senior \
  --campaign-id "2026-02-07-senior-backend-001" \
  --job-title "Senior Backend Engineer" \
  --company "TechCorp" \
  --location "San Francisco, CA" \
  --apply-link "https://jobs.techcorp.com/apply/456"
```

#### Send to junior and mid levels
```bash
# Run for junior
python -m src.main send --confirm --experience junior \
  --campaign-id "2026-02-07-junior-dev-001" \
  --job-title "Junior Developer" \
  --company "StartupXYZ" \
  --location "New York" \
  --apply-link "https://startup.xyz/careers/junior"

# Then run for mid
python -m src.main send --confirm --experience mid \
  --campaign-id "2026-02-07-mid-dev-001" \
  --job-title "Mid-Level Developer" \
  --company "StartupXYZ" \
  --location "New York" \
  --apply-link "https://startup.xyz/careers/mid"
```

#### Limit messages sent
```bash
python -m src.main send --confirm \
  --experience all \
  --limit 50 \
  --campaign-id "2026-02-07-job-001" \
  --job-title "Full Stack Developer" \
  --company "WebCo" \
  --location "Remote" \
  --apply-link "https://webco.com/apply"
```

### 4. Daily Summary
View statistics for today's sends:
```bash
python -m src.main daily-summary
```

## 🎯 How Experience-Level Targeting Works

### Campaign Key Structure
Each send is tracked using a `campaign_key`:
```
campaign_key = "{campaign_id}:{template_name}"
```

Examples:
- `2026-02-07-job-003:job_alert_senior`
- `2026-02-07-job-003:job_alert_junior`

### Never-Repeat Protection
The SQLite database tracks:
- `phone` + `campaign_key` = unique constraint
- A phone number can receive the same job ONCE per campaign_key
- Different campaigns (different campaign_id) can send to the same phone

### Workflow Example

**Scenario**: Sending a Senior Backend Engineer job ad

1. **Organize Contacts in Brevo**:
   - Create list "Senior Developers" (ID: 789)
   - Add candidates with senior experience to this list

2. **Configure** `.env`:
   ```ini
   EXPERIENCE_LIST_MAP={"senior":789}
   JOB_CAMPAIGN_ID=2026-02-07-senior-backend-001
   TEMPLATE_NAME_SENIOR=job_alert_senior
   ```

3. **Dry run** to preview:
   ```bash
   python -m src.main dry-run --experience senior
   ```

4. **Send** campaign:
   ```bash
   python -m src.main send --confirm --experience senior \
     --job-title "Senior Backend Engineer" \
     --company "TechCorp" \
     --location "Remote" \
     --apply-link "https://apply.here/123"
   ```

5. **Result**: Only candidates in list 789 who haven't received this campaign will get the message

## 📊 Template Variables

Your WhatsApp template should support these body variables (in order):
1. `{{1}}` - job_title
2. `{{2}}` - company
3. `{{3}}` - location
4. `{{4}}` - apply_link

**Example Template**:
```
We have a great opportunity for you!

Position: {{1}}
Company: {{2}}
Location: {{3}}

Apply now: {{4}}
```

## 📁 File Structure

```
Python CLI project/
├── src/
│   ├── main.py              # CLI entry point with job campaign support
│   ├── database.py          # Brevo integration + SQLite campaign tracking
│   ├── whatsapp_client.py   # WhatsApp API with template variables
│   ├── rate_limiter.py      # Rate limiting logic
│   ├── validators.py        # Phone validation
│   ├── logger.py            # Logging setup
│   └── config.py            # Configuration with experience mapping
├── tests/                   # Unit tests
├── logs/                    # Log files
│   ├── whatsapp_marketing.log
│   └── send_results.jsonl
├── send_history.db          # SQLite database (campaign tracking)
├── .env                     # Your configuration
├── .env.example             # Configuration template
└── requirements.txt         # Dependencies
```

## 🔐 Safety & Compliance

- ✅ **List membership = consent**: Only sends to contacts in targeted lists
- ✅ **Respects opt-out flags**: Checks `OPT_OUT` attribute and blacklist status
- ✅ **Never-repeat per campaign**: SQLite prevents duplicate sends per campaign_key
- ✅ **Rate limiting**: Configurable delays and daily limits
- ✅ **Production safeguards**: Requires `--confirm` flag in production
- ✅ **Comprehensive audit logs**: All sends tracked with campaign info

## 🐛 Troubleshooting

### Issue: "JOB_CAMPAIGN_ID required in production"
**Solution**: Set `JOB_CAMPAIGN_ID` in `.env` or use `--campaign-id` flag

### Issue: "Invalid EXPERIENCE_LIST_MAP format"
**Solution**: Use proper JSON format: `{"junior":123, "mid":456, "senior":789}`

### Issue: No eligible recipients found
**Checklist**:
1. Verify list IDs exist in Brevo
2. Check contacts are subscribed to the lists
3. Ensure phone numbers are in the correct attribute (BREVO_PHONE_ATTRIBUTE)
4. Check if campaign was already sent (campaign_key in send_history.db)

### Issue: Template variables not working
**Solution**: 
1. Verify template in Meta Business Manager has body variables
2. Ensure variables are in correct order
3. All 4 variables must be provided if template expects them

## 🧪 Testing

Run tests:
```bash
pytest
```

Run specific test:
```bash
pytest tests/test_database.py
```

## 📝 Logs

- **Application Logs**: `logs/whatsapp_marketing.log`  
  General application flow, errors, warnings

- **Result Logs**: `logs/send_results.jsonl`  
  Structured JSON records of every send attempt

**Example Result Log Entry**:
```json
{
  "timestamp": "2026-02-07T10:30:45",
  "user_id": "12345",
  "phone": "1234567890",
  "status": "success",
  "wa_message_id": "wamid.XXX",
  "http_code": 200
}
```

## 🔄 Workflow Summary

1. **Setup**: Configure `.env` with API keys and list mappings
2. **Validate**: Run `validate` to check connections
3. **Dry Run**: Preview recipients with `dry-run`
4. **Send**: Execute campaign with `send --confirm`
5. **Monitor**: Check logs and daily summary
6. **Repeat**: Use new campaign_id for next job

## 📞 Support

For issues or questions:
- Check logs in `logs/` directory
- Review `.env` configuration
- Verify Brevo list IDs and API connectivity
- Ensure WhatsApp templates are approved

## 🔒 Security Notes

- Never commit `.env` file (it contains API keys)
- Rotate API keys regularly
- Use `ENV=test` for testing
- Mask phone numbers in logs (automatic)
- Keep `send_history.db` backed up for compliance

---

**Built for compliance-first WhatsApp job marketing** 🚀
