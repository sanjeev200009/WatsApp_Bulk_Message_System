# Quick Start Guide: WhatsApp Job Campaign CLI

## 🚀 Setting Up Your First Job Campaign

### Step 1: Organize Contacts in Brevo

1. **Login to Brevo** (app.brevo.com)

2. **Create Experience-Level Lists**:
   - Go to **Contacts** → **Lists** → **Create a new list**
   - Create three lists:
     - "Junior Developers"
     - "Mid-Level Developers"
     - "Senior Developers"

3. **Get List IDs**:
   - Click on each list
   - Check the URL: `https://app.brevo.com/list/list-id-XXXXX`
   - Note down the numbers:
     - Junior: `123` (example)
     - Mid: `456` (example)
     - Senior: `789` (example)

4. **Add Contacts**:
   - Import or manually add candidates to appropriate lists
   - Ensure each contact has a phone number in the `WHATSAPP` or `SMS` attribute

### Step 2: Configure .env

Open `.env` and add:

```ini
# Experience targeting
EXPERIENCE_LIST_MAP={"junior":123, "mid":456, "senior":789}

# Campaign ID (change for each new job)
JOB_CAMPAIGN_ID=2026-02-07-backend-eng-001

# Templates (optional - use different per level)
TEMPLATE_NAME=job_alert
TEMPLATE_NAME_SENIOR=job_alert_senior
```

### Step 3: Validate Configuration

```bash
python -m src.main validate
```

**Expected Output:**
```
✅ WhatsApp API connected
✅ Brevo API connected
✅ Validation successful
```

### Step 4: Preview Recipients (Dry Run)

#### Preview all experience levels:
```bash
python -m src.main dry-run --campaign-id "2026-02-07-backend-eng-001"
```

**Output:**
```
🎯 Targeting experience levels: junior, mid, senior

📊 JUNIOR Level (List ID: 123, Template: job_alert)
   Found 45 eligible recipients
   Sample recipients:
      1. ID: 12345, Phone: +1...8901, Level: junior
      ...

📊 MID Level (List ID: 456, Template: job_alert)
   Found 38 eligible recipients
   ...

📊 SENIOR Level (List ID: 789, Template: job_alert_senior)
   Found 27 eligible recipients
   ...

📈 Total: 110 eligible recipients across all levels
   Would send max 100 messages (daily limit: 100)
```

#### Preview only senior candidates:
```bash
python -m src.main dry-run --experience senior --campaign-id "2026-02-07-backend-eng-001"
```

### Step 5: Send Your First Campaign

#### 🎯 Send to All Experience Levels

```bash
python -m src.main send --confirm \
  --campaign-id "2026-02-07-backend-eng-001" \
  --job-title "Backend Engineer" \
  --company "TechCorp Inc" \
  --location "Remote (US Only)" \
  --apply-link "https://jobs.techcorp.com/apply/be-001"
```

**What happens:**
1. Fetches contacts from junior list (123)
2. Sends to eligible junior candidates
3. Fetches contacts from mid list (456)
4. Sends to eligible mid candidates
5. Fetches contacts from senior list (789)
6. Sends to eligible senior candidates
7. Stops when daily limit (100) reached

#### 🎯 Send to Senior Only

```bash
python -m src.main send --confirm \
  --experience senior \
  --campaign-id "2026-02-07-senior-backend-001" \
  --job-title "Senior Backend Engineer" \
  --company "TechCorp Inc" \
  --location "San Francisco, CA" \
  --apply-link "https://jobs.techcorp.com/apply/sbe-001"
```

**What happens:**
1. Fetches ONLY from senior list (789)
2. Uses `job_alert_senior` template (if configured)
3. Sends to eligible senior candidates
4. Junior and mid lists are NOT contacted

#### 🎯 Send Two Different Jobs

**Senior Role:**
```bash
python -m src.main send --confirm \
  --experience senior \
  --campaign-id "2026-02-07-staff-engineer-001" \
  --job-title "Staff Engineer" \
  --company "BigTech" \
  --location "Seattle, WA" \
  --apply-link "https://bigtech.com/careers/staff-eng"
```

**Junior Role:**
```bash
python -m src.main send --confirm \
  --experience junior \
  --campaign-id "2026-02-07-junior-dev-001" \
  --job-title "Junior Developer" \
  --company "Startup XYZ" \
  --location "Austin, TX" \
  --apply-link "https://startup.xyz/jobs/junior-dev"
```

### Step 6: View Results

```bash
python -m src.main daily-summary
```

**Check Logs:**
- `logs/whatsapp_marketing.log` - Detailed execution log
- `logs/send_results.jsonl` - Structured send results
- `send_history.db` - SQLite database with all send history

## 📊 Common Scenarios

### Scenario 1: Weekly Job Newsletter

**Send Every Monday:**
```bash
# Week 1
python -m src.main send --confirm \
  --campaign-id "2026-02-07-weekly-newsletter" \
  --job-title "This Week's Top Jobs" \
  --company "JobBoard Pro" \
  --location "Various" \
  --apply-link "https://jobboard.pro/weekly/2026-02-07"

# Week 2 (new campaign ID)
python -m src.main send --confirm \
  --campaign-id "2026-02-14-weekly-newsletter" \
  --job-title "This Week's Top Jobs" \
  --company "JobBoard Pro" \
  --location "Various" \
  --apply-link "https://jobboard.pro/weekly/2026-02-14"
```

### Scenario 2: Urgent Senior Hire

**Send to Senior Only with Limit:**
```bash
python -m src.main send --confirm \
  --experience senior \
  --limit 50 \
  --campaign-id "2026-02-07-urgent-cto-001" \
  --job-title "Chief Technology Officer" \
  --company "FastGrowth Inc" \
  --location "New York, NY" \
  --apply-link "https://fastgrowth.com/cto"
```

### Scenario 3: Same Job, Different Seniority Levels

**Backend Engineer - All Levels Welcome:**
```bash
# Configure different templates for different descriptions
# TEMPLATE_NAME_JUNIOR: "Join our team as you start your career..."
# TEMPLATE_NAME_MID: "Take your skills to the next level..."
# TEMPLATE_NAME_SENIOR: "Lead our engineering efforts..."

python -m src.main send --confirm \
  --experience all \
  --campaign-id "2026-02-07-backend-all-levels" \
  --job-title "Backend Engineer (All Levels)" \
  --company "ScaleCo" \
  --location "Remote" \
  --apply-link "https://scaleco.com/careers/backend"
```

## 🛠️ Troubleshooting

### Issue: "No eligible recipients found"

**Check:**
1. List IDs are correct in `EXPERIENCE_LIST_MAP`
2. Contacts are added to the lists in Brevo
3. Contacts have phone numbers in `BREVO_PHONE_ATTRIBUTE`
4. Campaign hasn't already been sent (check `send_history.db`)

**Solution:**
```bash
# Verify contacts in Brevo
# Check list membership
# Try with a new campaign-id
```

### Issue: "JOB_CAMPAIGN_ID required in production"

**Solution:**
Set in `.env`:
```ini
ENV=prod
JOB_CAMPAIGN_ID=2026-02-07-job-001
```

Or use CLI:
```bash
python -m src.main send --confirm --campaign-id "2026-02-07-job-001" ...
```

### Issue: "Template variables not showing in message"

**Check:**
1. WhatsApp template has body variables configured
2. Variables are in correct order: job_title, company, location, apply_link
3. Template is approved in Meta Business Manager

**Template Format:**
```
We have a new opportunity!

Position: {{1}}
Company: {{2}}
Location: {{3}}

Apply: {{4}}
```

### Issue: "Already sent to some candidates"

**This is normal!** The system prevents duplicate sends per campaign.

**To resend:**
- Use a **NEW** campaign ID
- Example: Change from `2026-02-07-job-001` to `2026-02-07-job-002`

## 📅 Best Practices

### 1. Campaign ID Naming Convention
```
Format: YYYY-MM-DD-job-description-number
Examples:
  2026-02-07-backend-eng-001
  2026-02-07-senior-frontend-001
  2026-02-14-junior-dev-weekly
```

### 2. Daily Limits
- **Start low**: Begin with 50-100 messages/day
- **Scale gradually**: Increase as your phone number tier increases
- **Monitor**: Check logs for delivery rates

### 3. Template Management
- **Same template**: Use `TEMPLATE_NAME` for all levels
- **Different templates**: Set `TEMPLATE_NAME_JUNIOR/MID/SENIOR` for targeted messaging
- **Always approve**: Templates must be approved in Meta Business Manager

### 4. List Hygiene
- **Remove opt-outs**: Brevo automatically tracks unsubscribes
- **Update regularly**: Add new candidates, archive old ones
- **Segment properly**: Ensure candidates are in correct experience lists

### 5. Testing
```bash
# Always dry-run first
python -m src.main dry-run --campaign-id "test-001"

# Start with small limit
python -m src.main send --confirm --limit 5 --campaign-id "test-001" ...

# Check results
python -m src.main daily-summary

# Scale up
python -m src.main send --confirm --limit 50 ...
```

## 🔄 Weekly Workflow

### Monday: Plan Campaigns
1. Review job openings
2. Create unique campaign IDs
3. Prepare job details (title, company, location, link)

### Tuesday: Test Run
```bash
# Dry run to preview
python -m src.main dry-run --campaign-id "2026-02-XX-job-name"

# Send to small test group if needed
python -m src.main send --confirm --limit 5 ...
```

### Wednesday-Friday: Execute Campaigns
```bash
# Send campaigns throughout the week
python -m src.main send --confirm --campaign-id "..." ...
```

### End of Week: Review
```bash
# Check daily summary
python -m src.main daily-summary

# Review logs
cat logs/send_results.jsonl | grep success | wc -l
```

## 📞 Support Checklist

Before asking for help:
- ✅ Run `python -m src.main validate`
- ✅ Check `.env` configuration
- ✅ Verify Brevo list IDs
- ✅ Review `logs/whatsapp_marketing.log`
- ✅ Check template approval in Meta
- ✅ Confirm phone numbers in Brevo contacts

## 🎉 Success!

You're now ready to run targeted WhatsApp job campaigns! 

**Next Steps:**
1. Set up your Brevo lists
2. Configure `.env`
3. Run `validate`
4. Execute your first `dry-run`
5. Send your first campaign with `--confirm`

Happy recruiting! 🚀
