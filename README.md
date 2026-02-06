# WhatsApp Marketing CLI

A production-ready, standalone Python CLI application for sending WhatsApp Marketing template messages. Designed for controlled, compliant delivery to opt-in users using the official WhatsApp Cloud API.

## Features
- **Brevo Integration**: Reads contacts directly from your Brevo (Sendinblue) account.
- **Standalone CLI**: Simple checks and execution via command line.
- **WhatsApp Cloud API**: Uses official API with marketing templates and image headers.
- **Rate Limited**: strict daily limits and inter-message delays.
- **Compliance Focused**: Respects Brevo's blacklist status and custom attributes.

## Prerequisites
- Python 3.9+
- Meta Business Account with WhatsApp Cloud API enabled.
- **Brevo Account**: API Key v3 required.
- **Approved Marketing Template**: You must create a template in Meta Business Manager.

## Installation
1. **Clone and setup virtual environment**:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**:
   Copy `.env.example` to `.env` and fill in your details:
   ```bash
   cp .env.example .env
   ```

## Configuration Guide
Edit `.env`:

### WhatsApp
- `WA_ACCESS_TOKEN`: Permanent System User token.
- `WA_PHONE_NUMBER_ID`: From API Setup page.
- `TEMPLATE_NAME`: Must match exactly.

### Brevo (Database)
- `BREVO_API_KEY`: Get from [Brevo API Keys](https://app.brevo.com/settings/keys/api).
- `BREVO_LIST_ID`: (Optional) Put a List ID to restrict sending to just that list.
- `BREVO_PHONE_ATTRIBUTE`: The attribute name where phone is stored (default `SMS`).

### Application
- `DAILY_LIMIT`: Max messages to send per day (default 100).

### Template Requirements
Your WhatsApp template on Meta must:
- Be category **MARKETING**.
- Have a **Header** of type **Image**.
- Match the language code set in `TEMPLATE_LANGUAGE`.

## Usage

### 1. Validate Environment
Check if your credentials and database connection are working:
```bash
python -m src.main validate
```

### 2. Dry Run
See who would receive messages without actually sending them:
```bash
python -m src.main dry-run --limit 10
```

### 3. Send Messages
Start the sending process. This will run until the daily limit is reached or all users are processed.
```bash
python -m src.main send --limit 50
```

## Logs

- **Application Logs**: `logs/whatsapp_marketing.log` (General info/errors)
- **Result Logs**: `logs/send_results.jsonl` (Structured record of every attempt)

Format of Result Log:
```json
{"timestamp": "...", "user_id": "123", "phone": "1234567890", "status": "success", "wa_message_id": "...", "http_code": 200}
```

## Running Tests

```bash
pytest
```

## Maintenance & Compliance

- **Daily Limit**: Start low (e.g. 50-100) and increase slowly as your phone number tier increases.
- **Opt-Outs**: The system respects `is_opt_out` flag. Ensure you have a webhook or manual process updates this field in your database when users reply "STOP".
