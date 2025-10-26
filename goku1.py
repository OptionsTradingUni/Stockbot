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
# <-- FIXED: Using Sellix.io link as discussed -->
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

# <-- CORRECT: Using StringSession for Railway -->
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
        # From 1:30 AM up to 7:59 AM
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
        # All other times (8:00 AM to 1:29 AM)
        else:
            return (
                "No problem. You've been added to the mentor's queue.\n\n"
                "The mentor is active but currently handling **high message volume** (likely in a live trade or with another member). "
                "They will reply to you here personally as soon as they are free. Thank you!"
            )
            
    except Exception as e:
        print(f"Error in get_wait_message: {e}")
        # Fallback in case of timezone error
        return (
            "No problem. You've been added to the mentor's queue. "
            "They will reply to you here personally as soon as they are available. Thank you!"
        )

# ===================================================================
# --- 1. WELCOME MESSAGE HANDLER ---
# ===================================================================
async def send_welcome_message(sender_id, message_to_reply):
    """Sends the initial welcome message and sets the user's state."""
    user_states[sender_id] = "AWAITING_CHOICE"
    
    welcome_text = (
        "👋 Hello! You've reached out to a mentor at **Options Trading University**.\n\n"
        "This is an automated message due to very high message volume. "
        "You can use this assistant to get answers or join, or you can wait for a human.\n\n"
        "Please choose an option below:"
    )
    
    await message_to_reply.reply(
        welcome_text,
        buttons=[
            Button.inline("Continue with the assistant", b'continue_bot'),
            Button.inline("Wait for a human mentor", b'wait_mentor')
        ]
    )
    print(f"New conversation with {sender_id}. Sent initial choice.")

# ===================================================================
# --- 2. FALLBACK (ERROR) MESSAGE HANDLER ---
# ===================================================================
async def send_fallback_message(sender_id, state, message_to_reply):
    """Sends a "I don't understand" message and re-sends the correct prompt."""
    
    base_text = "Sorry, I'm an automated assistant and didn't understand that. Please use the buttons or try rephrasing."
    buttons = []
    
    if state == "AWAITING_CHOICE":
        base_text = "Sorry, I didn't understand. Please choose an option below:"
        buttons = [
            Button.inline("Continue with the assistant", b'continue_bot'),
            Button.inline("Wait for a human mentor", b'wait_mentor')
        ]
    elif state == "AWAITING_PREMIUM_Q":
        base_text = "Sorry, I just need a 'Yes' or 'No'. Have you paid already?"
        buttons = [
            Button.inline("Yes, I paid", b'paid_yes'),
            Button.inline("No, I have not", b'paid_no')
        ]
    elif state == "AWAITING_PAY_METHOD":
        base_text = "Sorry, I didn't catch that. How would you like to pay?"
        buttons = [
            Button.inline("💳 Pay with Credit Card", b'pay_card'),
            Button.inline("₿ Pay with Bitcoin", b'pay_btc'),
            Button.inline("I'll wait for the mentor", b'wait_mentor_payment')
        ]
    elif state == "SENT_BTC_ADDRESS":
        base_text = "Just click the button below once you've sent the payment."
        buttons = [Button.inline("✅ I HAVE SENT THE PAYMENT", b'btc_sent')]
        
    elif state in ["MENTOR_QUEUE", "PAID_PENDING_VERIFY", "BTC_PENDING_VERIFY"]:
        base_text = get_wait_message().split('\n\n', 1)[1] # Get the "please wait" part
        base_text = f"No problem! A human mentor will be here to help you. {base_text}"

    await message_to_reply.reply(base_text, buttons=buttons if buttons else None)

# ===================================================================
# --- 3. TEXT AND BUTTONS ARE HANDLED HERE ---
# ===================================================================
@client.on(events.NewMessage(incoming=True))
async def handle_new_dm(event):
    """
    Handles ALL new incoming text messages.
    """
    if not event.is_private: return
    if event.message.out: return # Correctly ignore our own outgoing messages
        
    sender_id = event.sender_id
    text = event.text.lower().strip()
    
    # Check if this is a new conversation
    if sender_id not in user_states:
        await send_welcome_message(sender_id, event.message)
        return

    # If conversation exists, get their state
    state = user_states.get(sender_id)
    intent = None

    # --- This is the "Smart Text" part ---
    if state == "AWAITING_CHOICE":
        if "continue" in text or "assistant" in text or "bot" in text:
            intent = b'continue_bot'
        elif "wait" in text or "human" in text or "mentor" in text:
            intent = b'wait_mentor'

    elif state == "AWAITING_PREMIUM_Q":
        if "yes" in text or "i paid" in text or "already paid" in text:
            intent = b'paid_yes'
        elif "no" in text or "i have not" in text or "haven't" in text:
            intent = b'paid_no'
            
    elif state == "AWAITING_PAY_METHOD":
        if "card" in text or "credit" in text:
            intent = b'pay_card'
        elif "btc" in text or "bitcoin" in text:
            intent = b'pay_btc'
        elif "wait" in text or "mentor" in text:
            intent = b'wait_mentor_payment'

    # <-- ADDED: Smart text handler for *after* card link is sent
    elif state == "SENT_CARD_LINK":
        if "paid" in text or "done" in text or "sent" in text or "finished" in text:
            intent = b'paid_card_confirm'

    elif state == "SENT_BTC_ADDRESS":
        if "sent" in text or "i have sent" in text or "paid" in text:
            intent = b'btc_sent'
    
    # --- Route the intent ---
    if intent:
        # If we understood the text, process it as if a button was pressed
        await process_intent(sender_id, intent, event.message)
    else:
        # If we didn't understand, send the fallback message
        await send_fallback_message(sender_id, state, event.message)


@client.on(events.CallbackQuery)
async def handle_button_press(query):
    """Handles all button presses from the automation."""
    sender_id = query.sender_id
    intent = query.data
    
    await query.answer() # Acknowledge the press
    
    # Process the button intent
    await process_intent(sender_id, intent, query)

# ===================================================================
# --- 4. MAIN LOGIC FOR ALL INTENTS ---
# ===================================================================
async def process_intent(sender_id, intent, event_object):
    """
    This new function handles the logic for ALL intents,
    from either text or buttons.
    'event_object' can be a message (to reply to) or a query (to edit).
    """
    state = user_states.get(sender_id) # Get current state
    
    # Helper to check if we should 'edit' a message or 'reply'
    async def respond(text, buttons=None):
        try:
            if hasattr(event_object, 'edit'):
                await event_object.edit(text, buttons=buttons)
            else:
                await event_object.reply(text, buttons=buttons)
        except Exception as e:
            # Handle case where message is old and can't be edited
            print(f"Error responding: {e}. Sending as new message.")
            await client.send_message(sender_id, text, buttons=buttons)


    # --- 1. User chose "Continue with assistant" ---
    if intent == b'continue_bot' and (state == "AWAITING_CHOICE" or state is None):
        user_states[sender_id] = "AWAITING_PREMIUM_Q"
        await respond(
            "Great! To help me direct you, have you already paid for the premium membership?\n\n"
            "_(This is an automated response)_",
            buttons=[
                Button.inline("Yes, I paid", b'paid_yes'),
                Button.inline("No, I have not", b'paid_no')
            ]
        )
        print(f"User {sender_id} chose to continue with bot.")
    
    # --- 2. User chose "Wait for mentor" ---
    elif intent == b'wait_mentor' and (state == "AWAITING_CHOICE" or state is None):
        user_states[sender_id] = "MENTOR_QUEUE"
        wait_message = get_wait_message()
        await respond(wait_message)
        print(f"User {sender_id} chose to wait for mentor.")
    
    # --- 3. User said "Yes, I paid" ---
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
        print(f"User {sender_id} claims they paid. Marked for verification.")

    # --- 4. User said "No, I have not" ---
    elif intent == b'paid_no' and state == "AWAITING_PREMIUM_Q":
        user_states[sender_id] = "AWAITING_PAY_METHOD"
        await respond(
            "Understood. Here is the membership information:\n\n"
            "_(This is an automated response)_"
        )
        await client.send_message(sender_id, SALES_MESSAGE)
        await client.send_message(
            sender_id,
            "How would you like to pay?\n\n"
            "_(This is an automated response)_",
            buttons=[
                Button.inline("💳 Pay with Credit Card", b'pay_card'),
                Button.inline("₿ Pay with Bitcoin", b'pay_btc'),
                Button.inline("I'll wait for the mentor", b'wait_mentor_payment')
            ]
        )
        print(f"User {sender_id} has not paid. Sent sales pitch.")

    # --- 5. User chose "Pay with Credit Card" ---
    elif intent == b'pay_card' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "SENT_CARD_LINK" # <-- Renamed state
        await respond(
            f"Perfect. You can use this secure link to pay with a credit card.\n\n"
            f"**Payment Link:** {PAYMENT_LINK}\n\n" # <-- Using correct link
            "**Important:** After you have paid, please come back here and "
            "type **'I paid'** so a mentor can verify and add you.\n\n"
            "_(This is an automated response)_"
        )
        print(f"User {sender_id} clicked Pay with Card. Sent Sellix link.")
    
    # --- 6. User chose "Pay with Bitcoin" ---
    elif intent == b'pay_btc' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "SENT_BTC_ADDRESS"
        address_to_send = random.choice(BTC_ADDRESSES)
        await respond(
            "Great. Please send **$50 USD** of Bitcoin (BTC) to the following address:\n\n"
            f"`{address_to_send}`\n\n"
            "**IMPORTANT:** This is the *only* official address. After you have sent the payment, "
            "please click the button below or type 'I have paid'.\n\n"
            "_(This is an automated response)_"
        )
        await client.send_message(
            sender_id,
            "Click here *after* you have sent the Bitcoin:",
            buttons=[Button.inline("✅ I HAVE SENT THE PAYMENT", b'btc_sent')]
        )
        print(f"User {sender_id} clicked Pay with Bitcoin.")

    # --- 7. User chose "I'll wait" (instead of paying) ---
    elif intent == b'wait_mentor_payment' and state == "AWAITING_PAY_METHOD":
        user_states[sender_id] = "MENTOR_QUEUE"
        wait_message = get_wait_message()
        await respond(wait_message)
        print(f"User {sender_id} is waiting for the mentor.")

    # --- 8. User confirmed "I SENT THE PAYMENT" (for BTC) ---
    elif intent == b'btc_sent' and state == "SENT_BTC_ADDRESS":
        user_states[sender_id] = "BTC_PENDING_VERIFY"
        wait_message_part = get_wait_message().split('\n\n', 1)[1] # Get timing
        await respond(
            "Thank you! 🙏 Your payment has been marked as pending.\n\n"
            "A mentor will **personally verify the transaction** on the blockchain "
            "and will reply here to onboard you.\n\n" +
            wait_message_part + "\n\n"
            "_(This is an automated response. A human mentor will reply next.)_"
        )
        print(f"User {sender_id} claims they sent Bitcoin. Marked for verification.")

    # --- 9. NEW: User confirmed "I paid" (for Card) ---
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
        print(f"User {sender_id} claims they paid via card. Marked for verification.")


# ===================================================================
# --- 5. SAFETY SWITCH ---
# ===================================================================
@client.on(events.NewMessage(outgoing=True))
async def handle_my_reply(event):
    """
    This is the safety switch. If YOU reply, the bot stops.
    """
    if not event.is_private:
        return
        
    user_id = event.chat_id
    if user_id in user_states:
        del user_states[user_id]
        print(f"Mentor has taken over conversation with {user_id}. Automation stopped for them.")

# ===================================================================
# --- 6. MAIN FUNCTION ---
# ===================================================================
async def main():
    print("Personal Assistant (goku1) is starting...")
    # This will log in using the SESSION_STRING_1
    await client.start()
    print("Personal Assistant (goku1) is running. Waiting for new DMs...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
