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

def cmd_dry_run(limit: int = None, experience: str = None, campaign_id: str = None, category: str = None):
    """
    Show eligible recipients without sending (supports experience-level filtering).
    """
    print("Running dry-run...")
    
    effective_campaign_id = campaign_id or settings.JOB_CAMPAIGN_ID
    
    if not effective_campaign_id:
        print("❌ Error: Campaign ID is required. Please provide it via --campaign-id or in .env.")
        print("💡 Tip: Use the same ID to finish a list tomorrow, or a new ID for a new job.")
        return
    
    print(f"🆔 Running with Campaign ID: {effective_campaign_id}")
    
    # Get targeting mapping (via Category Folder or Env Map)
    if category:
        print(f"📂 Identifying lists in category folder: {category}...")
        experience_map = db.get_lists_by_folder_name(category)
        if not experience_map:
            print(f"❌ Error: Could not find lists for category '{category}'")
            return
        
        if experience and experience.lower() != 'all':
            # Case-insensitive match for specific list
            match = next((k for k in experience_map.keys() if k.lower() == experience.lower()), None)
            if match:
                target_levels = [match]
            else:
                print(f"❌ Error: List '{experience}' not found in folder '{category}'")
                print(f"Available lists: {', '.join(experience_map.keys())}")
                return
        else:
            target_levels = list(experience_map.keys())
        
        print(f"🎯 Targeting lists: {', '.join(target_levels)}\n")
    else:
        experience_map = settings.get_experience_list_map()
        if experience_map:
            if experience and experience.lower() != 'all':
                target_levels = [experience.lower()]
            else:
                target_levels = list(experience_map.keys())
            print(f"🎯 Targeting experience levels (env): {', '.join(target_levels)}\n")
        else:
            target_levels = [None]
    
    overall_limit = limit if limit else settings.DAILY_LIMIT
    total_eligible = 0
    
    for level_name in target_levels:
        if level_name:
            list_id = experience_map.get(level_name)
            template_name = settings.get_template_name_for_level(level_name)
            campaign_key = f"{effective_campaign_id}:{template_name}" if effective_campaign_id else template_name
            print(f"📊 List: {level_name} (ID: {list_id}, Template: {template_name})")
        else:
            list_id = None
            template_name = settings.TEMPLATE_NAME
            campaign_key = effective_campaign_id or template_name
            print(f"📊 Default targeting")
        
        try:
            users = db.get_eligible_recipients(
                limit=overall_limit,
                list_id=list_id,
                campaign_key=campaign_key,
                experience_level=level_name
            )
            print(f"   Found {len(users)} eligible recipients")
            total_eligible += len(users)
            
            if users:
                display_count = min(len(users), 5)
                print(f"   Sample recipients (showing {display_count} of {len(users)}):")
                for i, user in enumerate(users[:5]):
                    masked = mask_phone(user.get('phone', ''))
                    print(f"      {i+1}. ID: {user.get('id')}, Phone: {masked}, Name: {user.get('experience_level', 'N/A')}")
                
                if len(users) > 5:
                    print(f"      ... and {len(users) - 5} others in this list\n")
                else:
                    print()
            else:
                print("   No eligible candidates in this list.\n")
                
        except Exception as e:
            print(f"   ❌ Error fetching {level_name or 'default'}: {e}")
            logger.exception(f"Dry run failed for {level_name}")
    
    print(f"📈 Total: {total_eligible} eligible recipients across all targeted lists")
    print(f"   Would send max {min(total_eligible, settings.DAILY_LIMIT)} messages (daily limit: {settings.DAILY_LIMIT})")

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

def cmd_send(limit: int = None, confirm: bool = False, 
             experience: str = None, campaign_id: str = None,
             category: str = None,
             job_title: str = None, company: str = None, 
             location: str = None, apply_link: str = None):
    """
    Execute message sending loop with experience-level targeting.
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
    
    effective_campaign_id = campaign_id or settings.JOB_CAMPAIGN_ID
    
    if not effective_campaign_id:
        print("❌ Error: Campaign ID is required for sending. Provide it via --campaign-id or set JOB_CAMPAIGN_ID in .env.")
        print("💡 This ID prevents duplicate messages to the same candidate for this job.")
        return
    
    print(f"🆔 Using Campaign ID: {effective_campaign_id}")
    
    # Get targeting mapping (via Category Folder or Env Map)
    if category:
        print(f"📂 Targeting category folder: {category}...")
        experience_map = db.get_lists_by_folder_name(category)
        if not experience_map:
            print(f"❌ Error: Could not find lists for category '{category}'")
            return
            
        if experience and experience.lower() != 'all':
            # Case-insensitive match for specific list
            match = next((k for k in experience_map.keys() if k.lower() == experience.lower()), None)
            if match:
                target_levels = [match]
            else:
                print(f"❌ Error: List '{experience}' not found in folder '{category}'")
                print(f"Available lists: {', '.join(experience_map.keys())}")
                return
        else:
            target_levels = list(experience_map.keys())
        
        print(f"🎯 Targeting lists: {', '.join(target_levels)}")
    else:
        experience_map = settings.get_experience_list_map()
        if experience_map:
            if experience and experience.lower() != 'all':
                target_levels = [experience.lower()]
            else:
                target_levels = list(experience_map.keys())
            print(f"🎯 Targeting experience levels (env): {', '.join(target_levels)}")
        else:
            target_levels = [None]
    
    # Determine effective limit per level or total
    run_limit = limit if limit else settings.DAILY_LIMIT
    
    # Build job variables if provided
    body_variables = None
    if any([job_title, company, location, apply_link]):
        body_variables = {}
        if job_title:
            body_variables['job_title'] = job_title
        if company:
            body_variables['company'] = company
        if location:
            body_variables['location'] = location
        if apply_link:
            body_variables['apply_link'] = apply_link
        if category:
            body_variables['category'] = category
        print(f"📝 Job variables: {', '.join(f'{k}={v}' for k, v in body_variables.items())}")
    
    logger.info(f"Starting batch send. Environment: {settings.ENV}, Run limit: {run_limit}, Campaign: {effective_campaign_id}")
    
    count_success = 0
    count_failed = 0
    count_skipped = 0
    
    # Process each list targeted
    for level_name in target_levels:
        if count_success >= run_limit:
            print("✅ Global run limit reached across all lists")
            break
            
        remaining_limit = run_limit - count_success
        
        if level_name:
            list_id = experience_map.get(level_name)
            template_name = settings.get_template_name_for_level(level_name)
            campaign_key = f"{effective_campaign_id}:{template_name}"
            
            print(f"\n📊 Processing List: {level_name} (ID: {list_id}, Template: {template_name})")
            logger.info(f"Fetching recipients from list '{level_name}' (ID: {list_id})")
        else:
            # Legacy/Generic mode
            list_id = None
            template_name = settings.TEMPLATE_NAME
            campaign_key = effective_campaign_id or template_name
            print(f"\n📊 Processing default batch (Template: {template_name})")
        
        try:
            users = db.get_eligible_recipients(
                limit=remaining_limit * 2,  # Fetch extra in case some fail validation
                list_id=list_id,
                campaign_key=campaign_key,
                experience_level=level_name
            )
        except Exception as e:
            logger.critical(f"Failed to fetch recipients for {level_name or 'default'}: {e}")
            continue

        print(f"   Found: {len(users)} eligible recipients")
        logger.info(f"Fetched {len(users)} eligible recipients for {level_name or 'default'}")
        
        level_success = 0
        
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
            user_level = user.get('experience_level', level)
            user_list_id = user.get('list_id', list_id)
            
            # Validate phone (already validated but safety check)
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
                logger.info(f"Sending to user {user_id} ({mask_phone(clean_phone)}) [{user_level or 'default'}]...")
                
                # Prepare message variables
                user_vars = body_variables.copy() if body_variables else {}
                
                # Auto-inject context for "One Template" strategy
                if 'category' not in user_vars:
                    user_vars['category'] = category or "General"
                
                if 'experience' not in user_vars:
                    # Professional capitalization (Mid-Senior -> Mid-Senior)
                    if user_level:
                        display_level = " ".join([w.capitalize() for w in str(user_level).split()])
                    else:
                        display_level = "Qualified"
                    user_vars['experience'] = display_level

                response, status = wa_client.send_template_message(
                    to_phone=clean_phone,
                    template_name=template_name,
                    body_variables=user_vars
                )
                
                wa_message_id = response.get('messages', [{}])[0].get('id')
                
                # Record success with campaign_key
                limiter.record_success(user_id)
                db.record_send(clean_phone, campaign_key, 'success', 
                             experience_level=user_level, list_id=user_list_id, wamid=wa_message_id)
                result_logger.log_result(user_id, clean_phone, "success", wa_message_id=wa_message_id, http_code=200)
                
                logger.info(f"✅ Sent to {user_id}. WA ID: {wa_message_id}")
                count_success += 1
                level_success += 1
                
            except Exception as e:
                # Extract status code if available
                code = getattr(getattr(e, 'response', None), 'status_code', None)
                
                # Determine if this should be retried
                retryable = should_retry_error(e, code)
                
                logger.error(f"❌ Failed to send to {user_id}: {e} (retryable: {retryable})")
                limiter.record_failure()
                
                # Record failure with campaign_key
                db.record_send(clean_phone, campaign_key, 'failed',
                             experience_level=user_level, list_id=user_list_id, error=str(e))
                result_logger.log_result(user_id, clean_phone, "failed", error=str(e), http_code=code)
                count_failed += 1
        
        if level:
            print(f"   ✅ Sent {level_success} messages to {level.upper()} level")
            
    # Log final summary
    logger.info(f"Batch completed. Success: {count_success}, Failed: {count_failed}, Skipped: {count_skipped}")
    print(f"\n📈 Final Summary: ✅ {count_success} sent | ❌ {count_failed} failed | ⏭️ {count_skipped} skipped")
    
    # Generate and log daily summary
    result_logger.log_daily_summary()


def main():
    parser = argparse.ArgumentParser(description="WhatsApp Job Alerts CLI")
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Send Command
    send_parser = subparsers.add_parser('send', help='Send messages to eligible users')
    send_parser.add_argument('--limit', type=int, help='Limit number of messages for this run')
    send_parser.add_argument('--confirm', action='store_true', help='Confirm sending (required in production)')
    send_parser.add_argument('--experience', choices=['junior', 'mid', 'senior', 'executive', 'all'], 
                           help='Target specific experience level (default: all)')
    send_parser.add_argument('--campaign-id', type=str, help='Campaign ID for this job (overrides JOB_CAMPAIGN_ID)')
    send_parser.add_argument('--category', type=str, help='Target category/folder name in Brevo')
    send_parser.add_argument('--job-title', type=str, help='Job title variable for template')
    send_parser.add_argument('--company', type=str, help='Company name variable for template')
    send_parser.add_argument('--location', type=str, help='Location variable for template')
    send_parser.add_argument('--apply-link', type=str, help='Application link variable for template')
    
    # Dry Run Command
    dry_parser = subparsers.add_parser('dry-run', help='Preview eligible recipients')
    dry_parser.add_argument('--limit', type=int, help='Limit number of recipients to preview')
    dry_parser.add_argument('--experience', choices=['junior', 'mid', 'senior', 'executive', 'all'], 
                          help='Target specific experience level (default: all)')
    dry_parser.add_argument('--campaign-id', type=str, help='Campaign ID to check for duplicates')
    dry_parser.add_argument('--category', type=str, help='Target category/folder name in Brevo')
    
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
        cmd_dry_run(limit=args.limit, experience=args.experience, campaign_id=args.campaign_id, category=args.category)
    elif args.command == 'simulate-send':
        cmd_simulate_send(limit=args.limit)
    elif args.command == 'send':
        cmd_send(limit=args.limit, confirm=args.confirm, 
                experience=args.experience, campaign_id=args.campaign_id,
                category=args.category,
                job_title=args.job_title, company=args.company, 
                location=args.location, apply_link=args.apply_link)
    elif args.command == 'daily-summary':
        result_logger.log_daily_summary()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
