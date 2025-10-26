import asyncio
import random
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from datetime import datetime, timedelta
import pytz

# --- !! 1. PASTE YOUR KEYS AND SESSION STRING HERE !! ---
API_ID = 3848094
API_HASH = 'b5be7dd84556db235436187271576566'

# <-- 2. YOUR SESSION STRING -->
SESSION_STRING_1 = '1BJWap1wBu0GxCLqqw-IpLrWSgqSG0Op2aSqmtv5xd0M7t6yrkN3EHMXQFF-YFSkC9wv1mynqGvUNp57jlRfefcEmp_jWQsFNUsRCvyOsnqWjcytjKGlX_w6SCSCxJcNVF6OuI1JyCJgmxgEyETcnLndbz7TAz0ZmtYMDKVDFBVEZ7Rbgs68mqf9wwVRQbrlQpz58Wsq4tEpe8vJPZFOn9BNWqxrPIxp6Gcw6z30OvBH8IyZjG0sjm1mGOxyI906Di5Tyq0WKLNGoeKaXSoWJTNno5L6CaAQm6M3x0Jc1bGaBPdFJ5DBbaddP8pRL6-S6PcS63ESQ5xwB3SU80iL1H8rzREWVhds='

# --- !! 2. SET YOUR TIMEZONE !! ---
MENTOR_TIMEZONE = "Africa/Lagos"
US_TIMEZONE = "America/New_York"

# --- !! 3. PASTE YOUR PAYMENT INFO HERE !! ---
# <-- Use Coinbase Commerce, BitPay, or another platform -->
PAYMENT_LINK = "https://commerce.coinbase.com/checkout/YOUR-ID-HERE" # Example
BTC_ADDRESSES = [
    "bc1qYourFirstAddressGoesHere",
]

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

# <-- Using StringSession for Railway -->
client = TelegramClient(StringSession(SESSION_STRING_1), API_ID, API_HASH)

# This dictionary will keep track of where each user is in the conversation.
user_states = {}

def get_wait_message():
    """
    Checks the mentor's local time and generates a professional
    wait message with correct time expectations and 'main menu' hint.
    """
    try:
        mentor_tz = pytz.timezone(MENTOR_TIMEZONE)
        us_tz = pytz.timezone(US_TIMEZONE)
        now_mentor = datetime.now(mentor_tz)
        hour = now_mentor.hour
        minute = now_mentor.minute

        # Determine if it's inactive time
        inactive = (hour == 1 and minute >= 30) or (1 < hour < 8)

        if inactive:
            # Calculate next 8 AM WAT
            reply_time_mentor = now_mentor.replace(hour=8, minute=0, second=0, microsecond=0)
            if now_mentor.time() >= datetime.min.replace(hour=8).time(): # Check if current time is past 8 AM
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
        # Fallback wait message
        return (
            "No problem. You've been added to the mentor's queue. "
            "They will reply soon. (Type **`main menu`** to restart)"
        )

# ===================================================================
# --- FUNCTION TO DELETE MESSAGES ---
# ===================================================================
async def delete_previous_messages(sender_id, current_message_id):
    """Attempts to delete the bot's last few messages in the chat."""
    print(f"--- Attempting to delete previous bot messages for {sender_id} ---")
    messages_to_delete = []
    try:
        # Fetch recent messages
        async for message in client.iter_messages(sender_id, limit=15): # Increased limit slightly
            # Delete outgoing messages older than the trigger message
            if message.out and message.id != current_message_id:
                messages_to_delete.append(message.id)

        if messages_to_delete:
            print(f"--- Deleting messages: {messages_to_delete} for {sender_id} ---")
            await client.delete_messages(sender_id, messages_to_delete, revoke=True)
            print(f"--- Deletion attempt complete for {sender_id} ---")
        else:
            print(f"--- No recent bot messages found to delete for {sender_id} ---")
    except Exception as e:
        print(f"--- WARNING: Failed during message deletion for {sender_id}: {e} ---")

# ===================================================================
# --- WELCOME MESSAGE HANDLER ---
# ===================================================================
async def send_welcome_message(sender_id, message_to_reply):
    """Sends the initial welcome message with clear text options."""
    user_states[sender_id] = "AWAITING_CHOICE"
    welcome_text = (
        "👋 Hello! You've reached out to a mentor at **Options Trading University**.\n\n"
        "This is an automated assistant due to very high message volume.\n\n"
        "Please choose one of the following options (click the button or type the text command):\n\n"
        "1. Continue with the assistant: Type **`continue`**\n"
        "2. Wait for a human mentor: Type **`wait`**"
    )
    # Use reply to keep context
    await message_to_reply.reply(
        welcome_text,
        buttons=[
            Button.inline("1. Continue with Assistant", b'continue_bot'),
            Button.inline("2. Wait for Mentor", b'wait_mentor')
        ]
    )
    print(f"New conversation with {sender_id}. Sent initial choice.")

# ===================================================================
# --- FALLBACK (ERROR) MESSAGE HANDLER ---
# ===================================================================
async def send_fallback_message(sender_id, state, message_to_reply):
    """Sends a clearer 'I don't understand' message and re-prompts."""
    print(f"--- DEBUG: Entering fallback for User {sender_id} in state: {state} ---")
    base_text = "Sorry, I'm an automated assistant and didn't understand that."
    buttons_to_send = []

    if state == "AWAITING_CHOICE":
        base_text = (
            "Sorry, I didn't understand. Please choose one of the options below "
            "(click the button or type the command):\n\n"
            "1. Continue with the assistant: Type **`continue`**\n"
            "2. Wait for a human mentor: Type **`wait`**"
        )
        buttons_to_send = [
            Button.inline("1. Continue with Assistant", b'continue_bot'),
            Button.inline("2. Wait for Mentor", b'wait_mentor')
        ]
    elif state == "AWAITING_PREMIUM_Q":
        base_text = (
             "Sorry, I didn't understand. Have you already paid for the premium membership?\n\n"
             "Please choose one (click or type):\n\n"
             "1. Yes, I paid: Type **`yes`**\n"
             "2. No, I have not: Type **`no`**"
        )
        buttons_to_send = [
            Button.inline("1. Yes, I paid", b'paid_yes'),
            Button.inline("2. No, I have not", b'paid_no')
        ]
    elif state == "AWAITING_PAY_METHOD":
        base_text = (
            "Sorry, I didn't catch that. How would you like to pay?\n\n"
            "Please choose one (click or type):\n\n"
            "1. Pay using the Link: Type **`card`**\n"
            "2. Pay with Bitcoin: Type **`bitcoin`**\n"
            "3. Wait for the mentor: Type **`wait`**"
        )
        buttons_to_send = [
            Button.inline("1. 💳 Use Payment Link", b'pay_card'),
            Button.inline("2. ₿ Bitcoin", b'pay_btc'),
            Button.inline("3. Wait for Mentor", b'wait_mentor_payment')
        ]
    elif state == "SENT_CARD_LINK":
        base_text = "Did you complete the payment using the link? Please type **`paid`** if you have finished."
        # No buttons needed, waiting for text
    elif state == "SENT_BTC_ADDRESS":
        base_text = "After sending the Bitcoin, please click the button below or type **`paid`** / **`sent`**."
        # Don't resend button here automatically, process_intent handles it better
        buttons_to_send = [Button.inline("✅ I HAVE SENT THE PAYMENT", b'btc_sent')]

    elif state in ["MENTOR_QUEUE", "PAID_PENDING_VERIFY", "BTC_PENDING_VERIFY"]:
        base_text = get_wait_message() # Re-send appropriate wait message with 'main menu' hint
    else: # Unknown state
        base_text = "Sorry, I'm having trouble understanding. Putting you in the queue for a mentor."
        user_states[sender_id] = "MENTOR_QUEUE" # Default to queue if state is lost
        base_text += "\n\n" + get_wait_message() # Add wait time info

    # --- Send the reply logic (handle edit vs reply) ---
    try:
        # Prefer editing if the trigger was a button press and we have buttons to show
        can_edit = hasattr(message_to_reply, 'edit') and buttons_to_send
        if can_edit:
             # Check message age before trying to edit
             message_time = message_to_reply.message.date
             if datetime.now(pytz.utc) - message_time < timedelta(hours=47):
                 await message_to_reply.edit(base_text, buttons=buttons_to_send)
                 print(f"--- DEBUG: Fallback reply edited successfully with buttons: {bool(buttons_to_send)}")
                 return # Exit if edit succeeded
             else:
                 print(f"--- INFO: Fallback source message too old to edit for {sender_id}. Sending new. ---")
                 # Fall through to send new message if too old

        # Send as a new reply if couldn't edit or shouldn't edit
        await message_to_reply.reply(base_text, buttons=buttons_to_send if buttons_to_send else None)
        print(f"--- DEBUG: Fallback reply sent successfully (new message) with buttons: {bool(buttons_to_send)}")

    except Exception as e:
        print(f"--- ERROR: Failed to send fallback reply (edit/reply): {e} ---")
        # Final attempt: send as a completely new message without replying
        try:
            await client.send_message(sender_id, base_text, buttons=buttons_to_send if buttons_to_send else None)
        except Exception as e2:
            print(f"--- FATAL ERROR: Could not send fallback message at all: {e2} ---")


# ===================================================================
# --- TEXT AND BUTTONS HANDLER ---
# ===================================================================
@client.on(events.NewMessage(incoming=True))
async def handle_new_dm(event):
    """Handles ALL new incoming text messages, including 'main menu'."""
    if not event.is_private: return
    # event.message.out is the correct way to check for outgoing messages in user mode
    if event.message.out: return

    sender_id = event.sender_id
    text = event.text.lower().strip().replace('`', '') # Clean input

    current_state = user_states.get(sender_id)

    # Handle /start or completely new users
    if text == '/start' or current_state is None:
        if text == '/start' and current_state: # If user types /start mid-conversation
            print(f"User {sender_id} sent /start. Resetting state.")
            await delete_previous_messages(sender_id, event.message.id)
        await send_welcome_message(sender_id, event.message)
        return

    # Handle "main menu" command in waiting states
    if text == "main menu" and current_state in ["MENTOR_QUEUE", "PAID_PENDING_VERIFY", "BTC_PENDING_VERIFY"]:
        print(f"User {sender_id} requested main menu from state {current_state}.")
        await delete_previous_messages(sender_id, event.message.id)
        await send_welcome_message(sender_id, event.message)
        return

    # Try to match text input to an intent based on current state
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

    # Process the intent if found
    if intent:
        await process_intent(sender_id, intent, event.message)
    # Handle text when in a waiting state (but not "main menu")
    elif current_state in ["MENTOR_QUEUE", "PAID_PENDING_VERIFY", "BTC_PENDING_VERIFY"]:
        print(f"User {sender_id} sent text '{text}' while in queue state {current_state}. Sending wait message.")
        await event.reply(get_wait_message()) # Send the wait message again
    # Handle general confusion or unrecognized input in active states
    else:
        confusion_phrases = ["not showing", "what option", "which option", "don't see", "where are", "how do i choose"]
        if any(phrase in text for phrase in confusion_phrases) and current_state in ["AWAITING_CHOICE", "AWAITING_PREMIUM_Q", "AWAITING_PAY_METHOD", "SENT_BTC_ADDRESS", "SENT_CARD_LINK"]:
             print(f"User {sender_id} seems confused. Re-prompting for state {current_state}.")
             await send_fallback_message(sender_id, current_state, event.message) # Fallback now handles re-prompting clearly
        else:
             print(f"User {sender_id} sent unrecognized text '{text}' in state {current_state}. Generic fallback.")
             await send_fallback_message(sender_id, current_state, event.message)


@client.on(events.CallbackQuery)
async def handle_button_press(query):
    """Handles all button presses from the automation."""
    sender_id = query.sender_id
    intent = query.data
    await query.answer() # Acknowledge press quickly
    await process_intent(sender_id, intent, query) # Pass the query object

# ===================================================================
# --- MAIN LOGIC FOR ALL INTENTS ---
# ===================================================================
async def process_intent(sender_id, intent, event_object):
    """Handles the logic for ALL intents, with clear text options in messages."""
    state = user_states.get(sender_id)

    async def respond(text, buttons=None):
        """Helper to edit if possible (CallbackQuery), else send new."""
        is_callback = hasattr(event_object, 'edit')
        target_message = event_object.message if is_callback else event_object

        try:
            if is_callback:
                message_time = target_message.date
                # Check if message is recent enough to edit
                if datetime.now(pytz.utc) - message_time < timedelta(hours=47):
                    await event_object.edit(text, buttons=buttons)
                    # print(f"--- DEBUG: Edited message {target_message.id} for {sender_id} ---")
                    return # Success
                else:
                    print(f"--- INFO: Callback message too old to edit for {sender_id}. Sending new. ---")
                    # Fall through to send new message

            # Send as a new message (either reply or standalone)
            # Prefer replying to the original user message if possible
            if not target_message.out: # Check if it's the user's message
                 await target_message.reply(text, buttons=buttons)
                 # print(f"--- DEBUG: Replied to user message {target_message.id} for {sender_id} ---")
            else: # If previous was our message (e.g., failed edit), send standalone
                 await client.send_message(sender_id, text, buttons=buttons)
                 # print(f"--- DEBUG: Sent new message for {sender_id} (original was outgoing/too old) ---")

        except Exception as e:
            print(f"--- ERROR: In respond() for {sender_id}: {e}. Final attempt: send_message ---")
            try:
                # Absolute fallback: send a new message regardless of context
                await client.send_message(sender_id, text, buttons=buttons)
            except Exception as e2:
                 print(f"--- FATAL ERROR: Could not send process_intent message at all: {e2} ---")


    # --- Intent Processing Logic ---
    # (Ensure state checks match the intent to prevent processing out of order)

    if intent == b'continue_bot' and (state == "AWAITING_CHOICE" or state is None):
        user_states[sender_id] = "AWAITING_PREMIUM_Q"
        response_text = (
             "Great! To help me direct you, have you already paid for the premium membership?\n\n"
             "Please choose one (click or type):\n\n"
             "1. Yes, I paid: Type **`yes`**\n"
             "2. No, I have not: Type **`no`**"
        )
        await respond(response_text, buttons=[
            Button.inline("1. Yes, I paid", b'paid_yes'),
            Button.inline("2. No, I have not", b'paid_no')
        ])
        print(f"User {sender_id}: Chose 'continue bot'. Asking Premium Q.")

    elif intent == b'wait_mentor' and (state == "AWAITING_CHOICE" or state is None):
        user_states[sender_id] = "MENTOR_QUEUE"
        await respond(get_wait_message())
        print(f"User {sender_id}: Chose 'wait mentor'. Added to queue.")

    elif intent == b'paid_yes' and state == "AWAITING_PREMIUM_Q":
        user_states[sender_id] = "PAID_PENDING_VERIFY"
        # Split message gracefully in case separator isn't present
        wait_msg_parts = get_wait_message().split('\n\n', 1)
        time_info = wait_msg_parts[1] if len(wait_msg_parts) > 1 else "A mentor will reply as soon as possible."
        await respond(
            f"Great, thank you! 🙏\n\n"
            f"I've marked you as pending verification. A human mentor will personally "
            f"check the payment and get you added to the premium group.\n\n{time_info}\n\n"
            f"_(Automated response. A human mentor will reply next.)_"
        )
        print(f"User {sender_id}: Claimed 'paid yes'. Marked for verification.")

    elif intent == b'paid_no' and state == "AWAITING_PREMIUM_Q":
        user_states[sender_id] = "AWAITING_PAY_METHOD"
        await respond("Understood. Here is the membership information:\n\n_(Automated response)_")
        await client.send_message(sender_id, SALES_MESSAGE)
        payment_options_text = (
            "How would you like to pay?\n\n"
            "Please choose one (click or type):\n\n"
            "1. Pay using the Link: Type **`card`**\n"
            "2. Pay with Bitcoin: Type **`bitcoin`**\n"
            "3. Wait for the mentor: Type **`wait`**\n\n"
            "_(Automated response)_"
        )
        await client.send_message(sender_id, payment_options_text, buttons=[
            Button.inline("1. 💳 Use Payment Link", b'pay_card'),
            Button.inline("2. ₿ Bitcoin", b'pay_btc'),
            Button.inline("3. Wait for Mentor", b'wait_mentor_payment')
        ])
        print(f"User {sender_id}: Has not paid. Sent sales pitch & payment options.")

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
        print(f"User {sender_id}: Chose 'pay card'. Sent payment link.")

    elif intent == b'pay_btc' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "SENT_BTC_ADDRESS"
        address_to_send = random.choice(BTC_ADDRESSES)
        response_text = (
            f"Great. Please send **$50 USD** equivalent of Bitcoin (BTC) to the following address:\n\n"
            f"`{address_to_send}`\n\n"
            f"**IMPORTANT:** After you have sent the payment, "
            f"please click the button below OR type **`paid`** / **`sent`**.\n\n"
            f"_(Automated response)_"
        )
        await respond(response_text)
        await client.send_message(sender_id, "Click here *only after* sending:",
                                  buttons=[Button.inline("✅ I HAVE SENT THE PAYMENT", b'btc_sent')])
        print(f"User {sender_id}: Chose 'pay btc'. Sent address.")

    elif intent == b'wait_mentor_payment' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "MENTOR_QUEUE"
        await respond(get_wait_message())
        print(f"User {sender_id}: Chose 'wait' instead of paying.")

    elif intent == b'btc_sent' and state == "SENT_BTC_ADDRESS":
        user_states[sender_id] = "BTC_PENDING_VERIFY"
        wait_msg_parts = get_wait_message().split('\n\n', 1)
        time_info = wait_msg_parts[1] if len(wait_msg_parts) > 1 else "A mentor will reply as soon as possible."
        await respond(
            f"Thank you! 🙏 Your payment has been marked as pending.\n\n"
            f"A mentor will **personally verify the transaction** on the blockchain "
            f"and will reply here to onboard you.\n\n{time_info}\n\n"
            f"_(Automated response. A human mentor will reply next.)_"
        )
        print(f"User {sender_id}: Confirmed 'btc sent'. Marked for verification.")

    elif intent == b'paid_card_confirm' and state == "SENT_CARD_LINK":
        user_states[sender_id] = "PAID_PENDING_VERIFY"
        wait_msg_parts = get_wait_message().split('\n\n', 1)
        time_info = wait_msg_parts[1] if len(wait_msg_parts) > 1 else "A mentor will reply as soon as possible."
        await respond(
            f"Thank you! 🙏\n\n"
            f"I've marked you as pending verification. A human mentor will personally "
            f"check the payment and get you added to the premium group.\n\n{time_info}\n\n"
            f"_(Automated response. A human mentor will reply next.)_"
        )
        print(f"User {sender_id}: Confirmed 'paid' via card. Marked for verification.")

    else:
        # If intent doesn't match current state, treat as unrecognized
        print(f"--- WARNING: Intent '{intent}' received in unexpected state '{state}' for user {sender_id}. Sending fallback. ---")
        await send_fallback_message(sender_id, state, event_object)


# ===================================================================
# --- SAFETY SWITCH ---
# ===================================================================
@client.on(events.NewMessage(outgoing=True, private=True)) # Added private=True for efficiency
async def handle_my_reply(event):
    """If YOU reply, the bot stops for that user."""
    user_id = event.chat_id
    if user_id in user_states:
        del user_states[user_id]
        print(f"Mentor (you) took over conversation with {user_id}. Automation stopped.")

# ===================================================================
# --- MAIN FUNCTION ---
# ===================================================================
async def main():
    print("Personal Assistant (using StringSession) is starting...")
    # client.start() will use the StringSession provided
    await client.connect()
    if not await client.is_user_authorized():
        print("ERROR: SESSION STRING IS INVALID OR EXPIRED. Please generate a new one.")
        # Optionally add code here to regenerate session string if needed,
        # but that requires interactive input, not suitable for Railway.
        return # Stop if not authorized

    print(f"Logged in as: {(await client.get_me()).first_name}")
    print("Personal Assistant is running. Waiting for new DMs...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    # Standard way to run the async main function
    client.loop.run_until_complete(main())

