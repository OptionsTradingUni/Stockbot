import asyncio
import random
from telethon import TelegramClient, events # Removed Button import
from telethon.sessions import StringSession
from datetime import datetime, timedelta
import pytz

# --- !! 1. PASTE YOUR KEYS AND SESSION STRING HERE !! ---
API_ID = 3848094
API_HASH = 'b5be7dd84556db235436187271576566'
SESSION_STRING_1 = '1BJWap1wBu0GxCLqqw-IpLrWSgqSG0Op2aSqmtv5xd0M7t6yrkN3EHMXQFF-YFSkC9wv1mynqGvUNp57jlRfefcEmp_jWQsFNUsRCvyOsnqWjcytjKGlX_w6SCSCxJcNVF6OuI1JyCJgmxgEyETcnLndbz7TAz0ZmtYMDKVDFBVEZ7Rbgs68mqf9wwVRQbrlQpz58Wsq4tEpe8vJPZFOn9BNWqxrPIxp6Gcw6z30OvBH8IyZjG0sjm1mGOxyI906Di5Tyq0WKLNGoeKaXSoWJTNno5L6CaAQm6M3x0Jc1bGaBPdFJ5DBbaddP8pRL6-S6PcS63ESQ5xwB3SU80iL1H8rzREWVhds=' # Your Session String

# --- !! 2. SET YOUR TIMEZONE !! ---
MENTOR_TIMEZONE = "Africa/Lagos"
US_TIMEZONE = "America/New_York"

# --- !! 3. PASTE YOUR PAYMENT INFO HERE !! ---
PAYMENT_LINK = "https://commerce.coinbase.com/checkout/YOUR-ID-HERE" # Example
BTC_ADDRESSES = ["bc1qYourFirstAddressGoesHere"]

# --- Your Sales Message (sent when they say "No") ---
SALES_MESSAGE = """The membership is $50 to join.
Inside, you’ll get:
📈 Daily trade alerts (with entry, stop-loss, and take-profit levels)
📊 Market analysis & chart breakdowns
🤝 Direct support and updates from me
✅ Everything explained clearly so even beginners can follow

Once you’re in, I’ll send your first alert and onboarding checklist right away.
"""
# --- End of Configuration ---

client = TelegramClient(StringSession(SESSION_STRING_1), API_ID, API_HASH)
user_states = {}

# --- get_wait_message function ---
def get_wait_message():
    try:
        mentor_tz = pytz.timezone(MENTOR_TIMEZONE)
        us_tz = pytz.timezone(US_TIMEZONE)
        now_mentor = datetime.now(mentor_tz)
        hour = now_mentor.hour
        minute = now_mentor.minute
        inactive = (hour == 1 and minute >= 30) or (1 < hour < 8)
        if inactive:
            reply_time_mentor = now_mentor.replace(hour=8, minute=0, second=0, microsecond=0)
            if now_mentor.time() >= datetime.min.replace(hour=8).time():
                 reply_time_mentor += timedelta(days=1)
            reply_time_us = reply_time_mentor.astimezone(us_tz)
            mentor_time_str = reply_time_mentor.strftime("%-I:%M %p %Z")
            us_time_str = reply_time_us.strftime("%-I:%M %p %Z")
            return (
                "No problem. You've been added to the mentor's queue.\n\n"
                "Please note: The team is currently handling **peak message volume**. "
                "A mentor will personally reply to you around **"
                f"{mentor_time_str}** (approximately **{us_time_str}**).\n\n"
                "Thank you for your patience!\n\n"
                "_(Type **`main menu`** to restart)_"
            )
        else: # Active time
            return (
                "No problem. You've been added to the mentor's queue.\n\n"
                "The mentor is active but currently handling **high message volume**. "
                "They will reply to you here personally as soon as they are free. Thank you!\n\n"
                "_(Type **`main menu`** to restart)_"
            )
    except Exception as e:
        print(f"Error in get_wait_message: {e}")
        return (
            "No problem. You've been added to the mentor's queue. "
            "They will reply soon. (Type **`main menu`** to restart)"
        )

# --- delete_previous_messages function ---
async def delete_previous_messages(sender_id, current_message_id):
    print(f"--- Attempting to delete previous bot messages for {sender_id} ---")
    messages_to_delete = []
    try:
        async for message in client.iter_messages(sender_id, limit=15):
            if message.out and message.id != current_message_id:
                messages_to_delete.append(message.id)
        if messages_to_delete:
            print(f"--- Deleting messages: {messages_to_delete} for {sender_id} ---")
            await client.delete_messages(sender_id, messages_to_delete, revoke=True)
            print(f"--- Deletion attempt complete for {sender_id} ---")
        else: print(f"--- No recent bot messages found to delete for {sender_id} ---")
    except Exception as e: print(f"--- WARNING: Failed during message deletion for {sender_id}: {e} ---")

# ===================================================================
# --- WELCOME MESSAGE HANDLER (Text Only) ---
# ===================================================================
async def send_welcome_message(sender_id, message_to_reply):
    """Sends the initial welcome message with text commands."""
    user_states[sender_id] = "AWAITING_CHOICE"
    welcome_text = (
        "👋 Hello! You've reached out to a mentor at **Options Trading University**.\n\n"
        "This is an automated assistant due to very high message volume.\n\n"
        "Please type one of the following commands:\n\n"
        "▶️ To continue with the assistant, type: **`continue`**\n"
        "👤 To wait for a human mentor, type: **`wait`**"
    )
    await message_to_reply.reply(welcome_text)
    print(f"New conversation with {sender_id}. Sent initial choice (text only).")

# ===================================================================
# --- FALLBACK (ERROR) MESSAGE HANDLER (Text Only) ---
# ===================================================================
async def send_fallback_message(sender_id, state, message_to_reply):
    """Sends a clearer 'I don't understand' message and re-prompts (text only)."""
    print(f"--- DEBUG: Entering fallback for User {sender_id} in state: {state} ---")
    base_text = "Sorry, I'm an automated assistant and didn't understand that."

    if state == "AWAITING_CHOICE":
        base_text = (
            "Sorry, I didn't understand. Please type one of the following commands:\n\n"
            "▶️ To continue with the assistant, type: **`continue`**\n"
            "👤 To wait for a human mentor, type: **`wait`**"
        )
    elif state == "AWAITING_PREMIUM_Q":
        base_text = (
             "Sorry, I didn't understand. Have you already paid for the premium membership?\n\n"
             "Please type one of the following:\n\n"
             "✅ If yes, type: **`yes`**\n"
             "❌ If no, type: **`no`**"
        )
    elif state == "AWAITING_PAY_METHOD":
        base_text = (
            "Sorry, I didn't catch that. How would you like to pay?\n\n"
            "Please type one of the following:\n\n"
            "💳 To pay using the secure link, type: **`card`**\n"
            "₿ To pay with Bitcoin, type: **`bitcoin`**\n"
            "👤 To wait for the mentor, type: **`wait`**"
        )
    elif state == "SENT_CARD_LINK":
        base_text = "Did you complete the payment using the link? Please type **`paid`** if you have finished."
    elif state == "SENT_BTC_ADDRESS":
        base_text = "After sending the Bitcoin, please type **`paid`** or **`sent`**."
    elif state in ["MENTOR_QUEUE", "PAID_PENDING_VERIFY", "BTC_PENDING_VERIFY"]:
        base_text = get_wait_message()
    else:
        base_text = "Sorry, I'm having trouble understanding. Putting you in the queue for a mentor."
        user_states[sender_id] = "MENTOR_QUEUE"
        base_text += "\n\n" + get_wait_message()

    try:
        await message_to_reply.reply(base_text)
        print(f"--- DEBUG: Fallback reply sent successfully (text only)")
    except Exception as e:
        print(f"--- ERROR: Failed to send fallback reply: {e} ---")
        try: await client.send_message(sender_id, base_text)
        except Exception as e2: print(f"--- FATAL ERROR: Could not send fallback message at all: {e2} ---")


# ===================================================================
# --- TEXT HANDLER (CORRECTED DECORATOR) ---
# ===================================================================
@client.on(events.NewMessage(incoming=True)) # <-- CORRECTED LINE (Removed private=True)
async def handle_new_dm(event):
    """Handles ALL new incoming text messages."""
    # Check for private inside
    if not event.is_private:
        return
    if event.message.out:
        return

    sender_id = event.sender_id
    text = event.text.lower().strip().replace('`', '')

    current_state = user_states.get(sender_id)

    if text == '/start' or current_state is None:
        if text == '/start' and current_state:
            print(f"User {sender_id} sent /start. Resetting state.")
            await delete_previous_messages(sender_id, event.message.id)
        await send_welcome_message(sender_id, event.message)
        return

    if text == "main menu" and current_state in ["MENTOR_QUEUE", "PAID_PENDING_VERIFY", "BTC_PENDING_VERIFY"]:
        print(f"User {sender_id} requested main menu from state {current_state}.")
        await delete_previous_messages(sender_id, event.message.id)
        await send_welcome_message(sender_id, event.message)
        return

    intent = None
    if current_state == "AWAITING_CHOICE":
        if text == "continue": intent = b'continue_bot'
        elif text == "wait": intent = b'wait_mentor'
    elif current_state == "AWAITING_PREMIUM_Q":
        if text == "yes": intent = b'paid_yes'
        elif text == "no": intent = b'paid_no'
    elif current_state == "AWAITING_PAY_METHOD":
        if text == "card": intent = b'pay_card'
        elif text == "bitcoin": intent = b'pay_btc'
        elif text == "wait": intent = b'wait_mentor_payment'
    elif current_state == "SENT_CARD_LINK":
        if text == "paid": intent = b'paid_card_confirm'
    elif current_state == "SENT_BTC_ADDRESS":
        if text == "paid" or text == "sent": intent = b'btc_sent'

    if intent:
        await process_intent(sender_id, intent, event.message)
    elif current_state in ["MENTOR_QUEUE", "PAID_PENDING_VERIFY", "BTC_PENDING_VERIFY"]:
        print(f"User {sender_id} sent text '{text}' while in queue state {current_state}. Sending wait message.")
        await event.reply(get_wait_message())
    else:
        print(f"User {sender_id} sent unrecognized text '{text}' in state {current_state}. Generic fallback.")
        await send_fallback_message(sender_id, current_state, event.message)

# ===================================================================
# --- MAIN LOGIC FOR ALL INTENTS (Text Only) ---
# ===================================================================
async def process_intent(sender_id, intent, message_object):
    """Handles the logic for ALL intents, sending text-only responses."""
    state = user_states.get(sender_id)

    async def respond(text):
        try: await message_object.reply(text)
        except Exception as e:
            print(f"--- ERROR: In respond() for {sender_id}: {e}. Attempting send_message ---")
            try: await client.send_message(sender_id, text)
            except Exception as e2: print(f"--- FATAL ERROR: Could not send process_intent message at all: {e2} ---")

    if intent == b'continue_bot' and (state == "AWAITING_CHOICE" or state is None):
        user_states[sender_id] = "AWAITING_PREMIUM_Q"
        response_text = (
             "Great! To help me direct you, have you already paid for the premium membership?\n\n"
             "Please type one of the following:\n\n"
             "✅ If yes, type: **`yes`**\n"
             "❌ If no, type: **`no`**"
        )
        await respond(response_text)
        print(f"User {sender_id}: Chose 'continue'. Asking Premium Q.")

    elif intent == b'wait_mentor' and (state == "AWAITING_CHOICE" or state is None):
        user_states[sender_id] = "MENTOR_QUEUE"
        await respond(get_wait_message())
        print(f"User {sender_id}: Chose 'wait'. Added to queue.")

    elif intent == b'paid_yes' and state == "AWAITING_PREMIUM_Q":
        user_states[sender_id] = "PAID_PENDING_VERIFY"
        wait_msg_parts = get_wait_message().split('\n\n', 1); time_info = wait_msg_parts[1] if len(wait_msg_parts) > 1 else "A mentor will reply ASAP."
        await respond(f"Great, thank you! 🙏\n\nI've marked you as pending verification...\n\n{time_info}\n\n_(Automated response...)_")
        print(f"User {sender_id}: Claimed 'yes' (paid). Marked for verification.")

    elif intent == b'paid_no' and state == "AWAITING_PREMIUM_Q":
        user_states[sender_id] = "AWAITING_PAY_METHOD"
        await respond("Understood. Here is the membership information:\n\n_(Automated response)_")
        await client.send_message(sender_id, SALES_MESSAGE)
        payment_options_text = (
            "How would you like to pay?\n\n"
            "Please type one of the following:\n\n"
            "💳 To pay using the secure link, type: **`card`**\n"
            "₿ To pay with Bitcoin, type: **`bitcoin`**\n"
            "👤 To wait for the mentor, type: **`wait`**\n\n"
            "_(Automated response)_"
        )
        await client.send_message(sender_id, payment_options_text)
        print(f"User {sender_id}: Claimed 'no' (not paid). Sent sales pitch & payment options.")

    elif intent == b'pay_card' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "SENT_CARD_LINK"
        response_text = (
            f"Perfect. You can use this secure link to pay.\n\n"
            f"**Payment Link:** {PAYMENT_LINK}\n\n"
            f"**Important:** After you have paid, please come back here and "
            f"type **`paid`** so a mentor can verify and add you.\n\n"
            f"_(Automated response)_"
        )
        await respond(response_text)
        print(f"User {sender_id}: Chose 'card'. Sent payment link.")

    elif intent == b'pay_btc' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "SENT_BTC_ADDRESS"
        address_to_send = random.choice(BTC_ADDRESSES)
        response_text = (
            f"Great. Please send **$50 USD** equivalent of Bitcoin (BTC) to the following address:\n\n"
            f"`{address_to_send}`\n\n"
            f"**IMPORTANT:** After you have sent the payment, "
            f"please type **`paid`** or **`sent`**.\n\n"
            f"_(Automated response)_"
        )
        await respond(response_text)
        print(f"User {sender_id}: Chose 'bitcoin'. Sent address.")

    elif intent == b'wait_mentor_payment' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "MENTOR_QUEUE"
        await respond(get_wait_message())
        print(f"User {sender_id}: Chose 'wait' instead of paying.")

    elif intent == b'btc_sent' and state == "SENT_BTC_ADDRESS":
        user_states[sender_id] = "BTC_PENDING_VERIFY"
        wait_msg_parts = get_wait_message().split('\n\n', 1); time_info = wait_msg_parts[1] if len(wait_msg_parts) > 1 else "A mentor will reply ASAP."
        await respond(f"Thank you! 🙏 Your payment has been marked as pending...\n\n{time_info}\n\n_(Automated response...)_")
        print(f"User {sender_id}: Confirmed 'paid'/'sent' for BTC. Marked for verification.")

    elif intent == b'paid_card_confirm' and state == "SENT_CARD_LINK":
        user_states[sender_id] = "PAID_PENDING_VERIFY"
        wait_msg_parts = get_wait_message().split('\n\n', 1); time_info = wait_msg_parts[1] if len(wait_msg_parts) > 1 else "A mentor will reply ASAP."
        await respond(f"Thank you! 🙏\n\nI've marked you as pending verification...\n\n{time_info}\n\n_(Automated response...)_")
        print(f"User {sender_id}: Confirmed 'paid' via card link. Marked for verification.")

    else:
        print(f"--- WARNING: Intent '{intent}' received in unexpected state '{state}' for user {sender_id}. Sending fallback. ---")
        await send_fallback_message(sender_id, state, message_object)

# ===================================================================
# --- SAFETY SWITCH ---
# ===================================================================
@client.on(events.NewMessage(outgoing=True)) # Correct - no 'private' here
async def handle_my_reply(event):
    """If YOU reply, the bot stops for that user."""
    if not event.is_private: # Check inside
        return
    user_id = event.chat_id
    if user_id in user_states:
        del user_states[user_id]
        print(f"Mentor (you) took over conversation with {user_id}. Automation stopped.")

# ===================================================================
# --- MAIN FUNCTION ---
# ===================================================================
async def main():
    print("Personal Assistant (StringSession, Text-Only) is starting...")
    await client.connect()
    if not await client.is_user_authorized():
        print("CRITICAL ERROR: SESSION STRING IS INVALID OR EXPIRED. Bot cannot start.")
        print("Please generate a new session string and update the script.")
        return

    print(f"Logged in as: {(await client.get_me()).first_name}")
    print("Personal Assistant is running. Waiting for new DMs...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    client.loop.run_until_complete(main())
