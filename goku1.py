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
# <-- Use Sellix.io or another platform -->
PAYMENT_LINK = "https://pay.sellix.io/your-product-link"
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
    wait message with correct time expectations.
    """
    try:
        mentor_tz = pytz.timezone(MENTOR_TIMEZONE)
        us_tz = pytz.timezone(US_TIMEZONE)
        now_mentor = datetime.now(mentor_tz)
        
        hour = now_mentor.hour
        minute = now_mentor.minute

        # --- Your INACTIVE (Sleep) Time ---
        if (hour == 1 and minute >= 30) or (hour > 1 and hour < 8):
            reply_time_mentor = (now_mentor + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
            reply_time_us = reply_time_mentor.astimezone(us_tz)
            mentor_time_str = reply_time_mentor.strftime("%-I:%M %p %Z")
            us_time_str = reply_time_us.strftime("%-I:%M %p %Z")
            return (
                "No problem. You've been added to the mentor's queue.\n\n"
                "Please note: The team is currently handling **peak message volume** from all regions, so replies are delayed. "
                "A mentor will personally reply to you around **"
                f"{mentor_time_str}** (approximately **{us_time_str}**).\n\n"
                "Thank you for your patience!"
            )
        # --- Your ACTIVE (High Traffic) Time ---
        else:
            return (
                "No problem. You've been added to the mentor's queue.\n\n"
                "The mentor is active but currently handling **high message volume** (likely in a live trade or with another member). "
                "They will reply to you here personally as soon as they are free. Thank you!"
            )
    except Exception as e:
        print(f"Error in get_wait_message: {e}")
        return (
            "No problem. You've been added to the mentor's queue. "
            "They will reply to you here personally as soon as they are available. Thank you!"
        )

# ===================================================================
# --- 1. WELCOME MESSAGE HANDLER (Explicit Options) ---
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
    
    await message_to_reply.reply(
        welcome_text,
        buttons=[
            Button.inline("1. Continue with Assistant", b'continue_bot'),
            Button.inline("2. Wait for Mentor", b'wait_mentor')
        ]
    )
    print(f"New conversation with {sender_id}. Sent initial choice.")

# ===================================================================
# --- 2. FALLBACK (ERROR) MESSAGE HANDLER (Improved Clarity) ---
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
            "1. Pay with Credit Card: Type **`card`**\n"
            "2. Pay with Bitcoin: Type **`bitcoin`**\n"
            "3. Wait for the mentor: Type **`wait`**"
        )
        buttons_to_send = [
            Button.inline("1. 💳 Credit Card", b'pay_card'),
            Button.inline("2. ₿ Bitcoin", b'pay_btc'),
            Button.inline("3. Wait for Mentor", b'wait_mentor_payment')
        ]
        
    elif state == "SENT_CARD_LINK":
        base_text = "Did you complete the payment using the link? Please type **`paid`** if you have finished."

    elif state == "SENT_BTC_ADDRESS":
        base_text = "After sending the Bitcoin, please click the button below or type **`paid`** / **`sent`**."
        # Resend the button for clarity
        await message_to_reply.reply(
            base_text,
            buttons=[Button.inline("✅ I HAVE SENT THE PAYMENT", b'btc_sent')]
        )
        return # Exit after sending the button message

    elif state in ["MENTOR_QUEUE", "PAID_PENDING_VERIFY", "BTC_PENDING_VERIFY"]:
        base_text = (
            "Thank you for your message. You are still in the queue. "
            "A human mentor will reply here as soon as they are available. "
            "Sending more messages will not speed up the queue."
        )
        
    else:
        base_text = "Sorry, I'm having trouble understanding. A mentor will assist you shortly."
        user_states[sender_id] = "MENTOR_QUEUE" # Put them in queue if state is lost

    # --- Send the reply ---
    try:
        await message_to_reply.reply(base_text, buttons=buttons_to_send if buttons_to_send else None)
        print(f"--- DEBUG: Fallback reply sent successfully with buttons: {bool(buttons_to_send)}")
    except Exception as e:
        print(f"--- ERROR: Failed to send fallback reply: {e} ---")

# ===================================================================
# --- 3. TEXT AND BUTTONS ARE HANDLED HERE (Exact Matches) ---
# ===================================================================
@client.on(events.NewMessage(incoming=True))
async def handle_new_dm(event):
    """
    Handles ALL new incoming text messages, focusing on exact command matches.
    """
    if not event.is_private: return
    if event.message.out: return
        
    sender_id = event.sender_id
    # Use exact text, removing backticks if user copies them
    text = event.text.lower().strip().replace('`', '') 
    
    if sender_id not in user_states:
        await send_welcome_message(sender_id, event.message)
        return

    state = user_states.get(sender_id)
    intent = None

    # --- Match specific commands ---
    if state == "AWAITING_CHOICE":
        if text == "continue": intent = b'continue_bot'
        elif text == "wait": intent = b'wait_mentor'

    elif state == "AWAITING_PREMIUM_Q":
        if text == "yes": intent = b'paid_yes'
        elif text == "no": intent = b'paid_no'
            
    elif state == "AWAITING_PAY_METHOD":
        if text == "card": intent = b'pay_card'
        elif text == "bitcoin": intent = b'pay_btc'
        elif text == "wait": intent = b'wait_mentor_payment'

    elif state == "SENT_CARD_LINK":
        if text == "paid": intent = b'paid_card_confirm'

    elif state == "SENT_BTC_ADDRESS":
        if text == "paid" or text == "sent": intent = b'btc_sent'
    
    # --- Route or Fallback ---
    if intent:
        await process_intent(sender_id, intent, event.message)
    else:
        # Check for confusion *before* generic fallback
        confusion_phrases = ["not showing", "what option", "which option", "don't see", "where are", "how do i choose"]
        if any(phrase in text for phrase in confusion_phrases) and state in ["AWAITING_CHOICE", "AWAITING_PREMIUM_Q", "AWAITING_PAY_METHOD", "SENT_BTC_ADDRESS"]:
             print(f"User {sender_id} seems confused. Re-prompting for state {state}.")
             await send_fallback_message(sender_id, state, event.message) # Fallback now handles re-prompting clearly
        else:
             print(f"User {sender_id} sent unrecognized text '{text}' in state {state}. Generic fallback.")
             await send_fallback_message(sender_id, state, event.message)


@client.on(events.CallbackQuery)
async def handle_button_press(query):
    """Handles all button presses from the automation."""
    sender_id = query.sender_id
    intent = query.data
    await query.answer()
    await process_intent(sender_id, intent, query)

# ===================================================================
# --- 4. MAIN LOGIC FOR ALL INTENTS (Explicit Options) ---
# ===================================================================
async def process_intent(sender_id, intent, event_object):
    """
    Handles the logic for ALL intents, with clear text options in messages.
    """
    state = user_states.get(sender_id)
    
    async def respond(text, buttons=None):
        try:
            if hasattr(event_object, 'edit'):
                await event_object.edit(text, buttons=buttons)
            else:
                await event_object.reply(text, buttons=buttons)
        except Exception as e:
            print(f"Error responding: {e}. Sending as new message.")
            await client.send_message(sender_id, text, buttons=buttons)

    # --- 1. Continue with assistant ---
    if intent == b'continue_bot' and (state == "AWAITING_CHOICE" or state is None):
        user_states[sender_id] = "AWAITING_PREMIUM_Q"
        response_text = (
             "Great! To help me direct you, have you already paid for the premium membership?\n\n"
             "Please choose one (click or type):\n\n"
             "1. Yes, I paid: Type **`yes`**\n"
             "2. No, I have not: Type **`no`**"
        )
        await respond(
            response_text,
            buttons=[
                Button.inline("1. Yes, I paid", b'paid_yes'),
                Button.inline("2. No, I have not", b'paid_no')
            ]
        )
        print(f"User {sender_id}: Chose 'continue bot'.")
    
    # --- 2. Wait for mentor ---
    elif intent == b'wait_mentor' and (state == "AWAITING_CHOICE" or state is None):
        user_states[sender_id] = "MENTOR_QUEUE"
        wait_message = get_wait_message()
        await respond(wait_message)
        print(f"User {sender_id}: Chose 'wait mentor'.")
    
    # --- 3. Yes, I paid ---
    elif intent == b'paid_yes' and state == "AWAITING_PREMIUM_Q":
        user_states[sender_id] = "PAID_PENDING_VERIFY"
        wait_message_part = get_wait_message().split('\n\n', 1)[1]
        await respond(
            "Great, thank you! 🙏\n\n"
            "I've marked you as pending verification. A human mentor will personally "
            "check the payment and get you added to the premium group.\n\n" +
            wait_message_part + "\n\n"
            "_(This is an automated response. A human mentor will reply next.)_"
        )
        print(f"User {sender_id}: Claimed 'paid yes'.")

    # --- 4. No, I have not paid ---
    elif intent == b'paid_no' and state == "AWAITING_PREMIUM_Q":
        user_states[sender_id] = "AWAITING_PAY_METHOD"
        await respond(
            "Understood. Here is the membership information:\n\n"
            "_(This is an automated response)_"
        )
        # Send sales message separately
        await client.send_message(sender_id, SALES_MESSAGE)
        # Send payment options message
        payment_options_text = (
            "How would you like to pay?\n\n"
            "Please choose one (click or type):\n\n"
            "1. Pay with Credit Card: Type **`card`**\n"
            "2. Pay with Bitcoin: Type **`bitcoin`**\n"
            "3. Wait for the mentor: Type **`wait`**\n\n"
            "_(This is an automated response)_"
        )
        await client.send_message(
            sender_id,
            payment_options_text,
            buttons=[
                Button.inline("1. 💳 Credit Card", b'pay_card'),
                Button.inline("2. ₿ Bitcoin", b'pay_btc'),
                Button.inline("3. Wait for Mentor", b'wait_mentor_payment')
            ]
        )
        print(f"User {sender_id}: Has not paid. Sent sales pitch & payment options.")

    # --- 5. Pay with Credit Card ---
    elif intent == b'pay_card' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "SENT_CARD_LINK"
        response_text = (
            f"Perfect. You can use this secure link to pay with a credit card.\n\n"
            f"**Payment Link:** {PAYMENT_LINK}\n\n"
            "**Important:** After you have paid, please come back here and "
            "type **`paid`** so a mentor can verify and add you.\n\n"
            "_(This is an automated response)_"
        )
        await respond(response_text)
        print(f"User {sender_id}: Chose 'pay card'. Sent payment link.")
    
    # --- 6. Pay with Bitcoin ---
    elif intent == b'pay_btc' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "SENT_BTC_ADDRESS"
        address_to_send = random.choice(BTC_ADDRESSES)
        response_text = (
            "Great. Please send **$50 USD** equivalent of Bitcoin (BTC) to the following address:\n\n"
            f"`{address_to_send}`\n\n" # Address is copyable
            "**IMPORTANT:** After you have sent the payment, "
            "please click the button below OR type **`paid`** / **`sent`**.\n\n"
            "_(This is an automated response)_"
        )
        await respond(response_text)
        # Send the confirmation button separately for clarity
        await client.send_message(
            sender_id,
            "Click here *only after* you have sent the Bitcoin:",
            buttons=[Button.inline("✅ I HAVE SENT THE PAYMENT", b'btc_sent')]
        )
        print(f"User {sender_id}: Chose 'pay btc'. Sent address.")

    # --- 7. Wait for mentor (instead of paying) ---
    elif intent == b'wait_mentor_payment' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "MENTOR_QUEUE"
        wait_message = get_wait_message()
        await respond(wait_message)
        print(f"User {sender_id}: Chose 'wait' instead of paying.")

    # --- 8. Confirmed Bitcoin sent ---
    elif intent == b'btc_sent' and state == "SENT_BTC_ADDRESS":
        user_states[sender_id] = "BTC_PENDING_VERIFY"
        wait_message_part = get_wait_message().split('\n\n', 1)[1]
        await respond(
            "Thank you! 🙏 Your payment has been marked as pending.\n\n"
            "A mentor will **personally verify the transaction** on the blockchain "
            "and will reply here to onboard you.\n\n" +
            wait_message_part + "\n\n"
            "_(This is an automated response. A human mentor will reply next.)_"
        )
        print(f"User {sender_id}: Confirmed 'btc sent'.")

    # --- 9. Confirmed Card paid ---
    elif intent == b'paid_card_confirm' and state == "SENT_CARD_LINK":
        user_states[sender_id] = "PAID_PENDING_VERIFY"
        wait_message_part = get_wait_message().split('\n\n', 1)[1]
        await respond(
            "Thank you! 🙏\n\n"
            "I've marked you as pending verification. A human mentor will personally "
            "check the payment and get you added to the premium group.\n\n" +
            wait_message_part + "\n\n"
            "_(This is an automated response. A human mentor will reply next.)_"
        )
        print(f"User {sender_id}: Confirmed 'paid' via card.")


# ===================================================================
# --- 5. SAFETY SWITCH ---
# ===================================================================
@client.on(events.NewMessage(outgoing=True))
async def handle_my_reply(event):
    """If YOU reply, the bot stops for that user."""
    if not event.is_private: return
    user_id = event.chat_id
    if user_id in user_states:
        del user_states[user_id]
        print(f"Mentor has taken over conversation with {user_id}. Automation stopped.")

# ===================================================================
# --- 6. MAIN FUNCTION ---
# ===================================================================
async def main():
    print("Personal Assistant (using StringSession) is starting...")
    await client.start()
    print("Personal Assistant is running. Waiting for new DMs...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
