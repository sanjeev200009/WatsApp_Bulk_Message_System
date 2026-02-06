import argparse
import sys
import time
import json
from typing import List
from .config import settings
from .database import db
from .whatsapp_client import wa_client
from .rate_limiter import limiter
from .logger import logger, result_logger
from .validators import validate_phone, mask_phone

def should_retry_error(error: Exception, http_code: int = None) -> bool:
    """
    Categorize errors into retryable vs non-retryable.
    Returns True if error should be retried, False otherwise.
    """
    # Never retry these HTTP codes
    non_retry_codes = {400, 401, 403, 404, 422}  # Bad request, unauthorized, forbidden, not found, unprocessable
    if http_code in non_retry_codes:
        return False
    
    # Always retry these
    retry_codes = {500, 502, 503, 504}  # Server errors
    if http_code in retry_codes:
        return True
    
    # Check error message for specific patterns
    error_str = str(error).lower()
    
    # Never retry
    non_retry_patterns = [
        'template not found',
        'permission denied',
        'invalid recipient',
        'policy violation',
        'compliance',
        'unauthorized',
        'forbidden'
    ]
    
    for pattern in non_retry_patterns:
        if pattern in error_str:
            return False
    
    # Retry patterns (timeouts, connection issues)
    retry_patterns = [
        'timeout',
        'connection',
        'network',
        'temporarily unavailable'
    ]
    
    for pattern in retry_patterns:
        if pattern in error_str:
            return True
    
    # Default: don't retry unknown errors
    return False

def cmd_validate():
    """
    Validate configuration and connectivity.
    """
    print("Validating environment...")
    
    # 1. Validate required env vars
    missing = settings.validate_required_fields()
    if missing:
        print(f"❌ Configuration issues: {', '.join(missing)}")
        print("Please check your .env file and ensure all required variables are set.")
        return False
        
    # 2. Check WhatsApp API connection
    print("Checking WhatsApp API connection...")
    if wa_client.verify_connection():
        print("✅ WhatsApp API connected")
    else:
        print("❌ WhatsApp API connection failed")
        return False
        
    # 3. Check Database (Brevo)
    print("Checking Brevo connection...")
    if db.verify_connection():
        print("✅ Brevo API connected")
    else:
        print("❌ Brevo connection failed")
        return False
        
    print("✅ Validation successful")
    print(f"   Environment: {settings.ENV}")
    print(f"   Template: {settings.TEMPLATE_NAME} ({settings.LANGUAGE_CODE})")
    print(f"   Image: {settings.IMAGE_URL}")
    print(f"   Daily limit: {settings.DAILY_LIMIT}")
    print(f"   Send delay: {settings.SEND_DELAY_SECONDS}s")
    return True

def cmd_dry_run(limit: int = None):
    """
    Show eligible recipients without sending.
    """
    print("Running dry-run...")
    
    try:
        users = db.get_eligible_recipients(limit=limit)
        print(f"Found {len(users)} eligible recipients")
        
        print("\nSample recipients:")
        for i, user in enumerate(users[:5]):
            masked = mask_phone(user.get('phone', ''))
            print(f"  {i+1}. ID: {user.get('id')}, Phone: {masked}, Last Sent: {user.get('last_sent_at')}")
            
        if len(users) > 5:
            print(f"  ... and {len(users) - 5} more")
            
        print(f"\nWould send max {min(len(users), settings.DAILY_LIMIT)} messages")
        
    except Exception as e:
        print(f"❌ Error during dry-run: {e}")
        logger.exception("Dry run failed")

def cmd_simulate_send(limit: int = None):
    """
    Simulate sending by showing what payloads would be sent (no API calls).
    """
    print("Simulating send operation...")
    
    try:
        users = db.get_eligible_recipients(limit=limit or 5)  # Default to 5 for simulation
        print(f"Found {len(users)} eligible recipients")
        
        print("\nSimulated payloads:")
        for i, user in enumerate(users[:3]):  # Show first 3
            phone = user.get('phone')
            user_id = user.get('id')
            
            try:
                clean_phone = validate_phone(phone)
                payload = {
                    "messaging_product": "whatsapp",
                    "to": clean_phone,
                    "type": "template",
                    "template": {
                        "name": settings.TEMPLATE_NAME,
                        "language": {
                            "code": settings.LANGUAGE_CODE
                        }
                    }
                }
                print(f"  {i+1}. User {user_id} ({mask_phone(clean_phone)}):")
                print(f"     URL: {settings.api_base_url}/{settings.PHONE_NUMBER_ID}/messages")
                print(f"     Payload: {json.dumps(payload, indent=8)}")
                print()
            except ValueError as e:
                print(f"  {i+1}. User {user_id}: SKIP - {e}")
        
        print(f"\nSimulation complete. Would attempt {len(users)} messages.")
        
    except Exception as e:
        print(f"❌ Error during simulation: {e}")
        logger.exception("Simulation failed")

def cmd_send(limit: int = None, dry_run: bool = False, confirm: bool = False):
    """
    Execute message sending loop.
    """
    # Preflight checks
    if not cmd_validate():
        print("❌ Validation failed. Aborting send.")
        return
    
    # Require confirmation in production
    if settings.is_prod_env and not confirm:
        print("❌ Production environment requires --confirm flag")
        print("Use: python -m src.main send --confirm")
        return
        
    # Create tables if we are in dev mode (sqlite)
    db.create_tables_if_dev()
    
    # Determine effective limit
    run_limit = limit if limit else settings.DAILY_LIMIT
    
    logger.info(f"Starting batch send. Environment: {settings.ENV}, Run limit: {run_limit}")
    
    try:
        users = db.get_eligible_recipients(limit=run_limit * 2) # Fetch extra in case some fail validation
    except Exception as e:
        logger.critical(f"Failed to fetch recipients: {e}")
        return

    logger.info(f"Fetched {len(users)} potential recipients")
    
    count_success = 0
    count_failed = 0
    count_skipped = 0
    
    for user in users:
        # Check error spike stop
        if limiter.should_stop_due_to_errors():
            logger.error(f"❌ Stopping due to {limiter.consecutive_failures} consecutive failures (error spike detected)")
            break
            
        # Check global stopping conditions
        if count_success >= run_limit:
            logger.info("Run limit reached. Stopping.")
            break
            
        if not limiter.can_send(user['id']):
            if limiter.sent_count >= limiter.daily_limit:
                logger.warning("Daily limit reached (global). Stopping.")
                break
            count_skipped += 1
            continue
            
        phone = user.get('phone')
        user_id = user.get('id')
        
        # Validate phone
        try:
            clean_phone = validate_phone(phone)
        except ValueError as e:
            logger.warning(f"Skipping user {user_id}: Invalid phone {mask_phone(phone)} - {e}")
            result_logger.log_result(user_id, phone, "skipped", f"Invalid phone: {e}")
            count_skipped += 1
            continue

        # Enforce rate limit delay
        limiter.wait_for_slot()
        
        # Send Message
        try:
            logger.info(f"Sending to user {user_id} ({mask_phone(clean_phone)})...")
            
            response = wa_client.send_template_message(to_phone=clean_phone)
            
            wa_message_id = response.get('messages', [{}])[0].get('id')
            
            # Record success
            limiter.record_success(user_id)
            db.update_last_sent(user_id)
            result_logger.log_result(user_id, clean_phone, "success", wa_message_id=wa_message_id, http_code=200)
            
            logger.info(f"✅ Sent to {user_id}. WA ID: {wa_message_id}")
            count_success += 1
            
        except Exception as e:
            # Extract status code if available
            code = getattr(getattr(e, 'response', None), 'status_code', None)
            
            # Determine if this should be retried
            retryable = should_retry_error(e, code)
            
            logger.error(f"❌ Failed to send to {user_id}: {e} (retryable: {retryable})")
            limiter.record_failure()
            
            result_logger.log_result(user_id, clean_phone, "failed", error=str(e), http_code=code)
            count_failed += 1
            
    # Log final summary
    logger.info(f"Batch completed. Success: {count_success}, Failed: {count_failed}, Skipped: {count_skipped}")
    
    # Generate and log daily summary
    result_logger.log_daily_summary()


def main():
    parser = argparse.ArgumentParser(description="WhatsApp Job Alerts CLI")
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Send Command
    send_parser = subparsers.add_parser('send', help='Send messages to eligible users')
    send_parser.add_argument('--limit', type=int, help='Limit number of messages for this run')
    send_parser.add_argument('--confirm', action='store_true', help='Confirm sending (required in production)')
    
    # Dry Run Command
    dry_parser = subparsers.add_parser('dry-run', help='Preview eligible recipients')
    dry_parser.add_argument('--limit', type=int, help='Limit number of recipients to preview')
    
    # Simulate Send Command
    sim_parser = subparsers.add_parser('simulate-send', help='Simulate sending (show payloads, no API calls)')
    sim_parser.add_argument('--limit', type=int, help='Limit number of payloads to show')
    
    # Validate Command
    subparsers.add_parser('validate', help='Validate configuration')
    
    # Daily Summary Command
    subparsers.add_parser('daily-summary', help='Show daily summary')

    args = parser.parse_args()
    
    if args.command == 'validate':
        cmd_validate()
    elif args.command == 'dry-run':
        cmd_dry_run(limit=args.limit)
    elif args.command == 'simulate-send':
        cmd_simulate_send(limit=args.limit)
    elif args.command == 'send':
        cmd_send(limit=args.limit, confirm=args.confirm)
    elif args.command == 'daily-summary':
        result_logger.log_daily_summary()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
