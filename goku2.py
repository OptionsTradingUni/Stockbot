import asyncio
import random
from telethon import TelegramClient, events, Button
from datetime import datetime, timedelta
import pytz  # This is needed for timezones

# --- !! 1. PASTE YOUR API KEYS HERE (Less Secure) !! ---
API_ID = 7654321  # <-- Put your SECOND account's API ID here
API_HASH = 'xyz98765' # <-- Put your SECOND account's API Hash here

# --- !! 2. SET YOUR TIMEZONE !! ---
MENTOR_TIMEZONE = "Africa/Lagos"
US_TIMEZONE = "America/New_York"

# --- !! 3. PASTE YOUR PAYMENT INFO HERE !! ---
WHOP_PAYMENT_LINK = "https://whop.com/your-product"

BTC_ADDRESSES = [
    "bc1qYourFirstAddressGoesHere",
    "bc1qYourSecondAddressGoesHere",
    "bc1qYourThirdAddressGoesHere",
    "bc1qYourFourthAddressGoesHere",
    "bc1qYourFifthAddressGoesHere"
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


# !! IMPORTANT: This MUST be unique for each assistant file
client = TelegramClient('session_two', API_ID, API_HASH)

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


@client.on(events.NewMessage(incoming=True))  # <-- FIX 1: 'private=True' removed
async def handle_new_dm(event):
    """
    NEW FLOW: Greets the user and offers a choice: Bot or Human.
    """
    # <-- FIX 1: Added this check
    if not event.is_private:
        return
        
    if event.is_self:
        return
    sender_id = event.sender_id
    
    if sender_id not in user_states:
        user_states[sender_id] = "AWAITING_CHOICE" 
        
        welcome_text = (
            "👋 Hello! You've reached an automated assistant for **Options Trading University**.\n\n"
            "Due to very high message volume, our mentors use this system to help everyone faster. "
            "You can get most of your questions answered and even get enrolled right now.\n\n"
            "Please choose an option below:"
        )
        
        await event.reply(
            welcome_text,
            buttons=[
                Button.inline("Continue with the assistant", b'continue_bot'),
                Button.inline("Wait for a human mentor", b'wait_mentor')
            ]
        )
        print(f"New conversation with {sender_id}. Sent initial choice.")


@client.on(events.NewMessage(outgoing=True))  # <-- FIX 2: 'private=True' removed
async def handle_my_reply(event):
    """
    This is the safety switch. If YOU reply, the bot stops.
    """
    # <-- FIX 2: Added this check
    if not event.is_private:
        return
        
    user_id = event.chat_id
    if user_id in user_states:
        del user_states[user_id]
        print(f"Mentor has taken over conversation with {user_id}. Automation stopped for them.")


@client.on(events.CallbackQuery)
async def handle_button_press(query):
    """Handles all button presses from the automation."""
    
    sender_id = query.sender_id
    state = user_states.get(sender_id)
    await query.answer() # Acknowledge the press
    
    # --- 1. User makes the FIRST choice (Bot vs. Human) ---
    if state == "AWAITING_CHOICE":
        if query.data == b'continue_bot':
            user_states[sender_id] = "AWAITING_PREMIUM_Q"
            await query.edit(
                "Great! To help me direct you, have you already paid for the premium membership?\n\n"
                "_(This is an automated response)_",
                buttons=[
                    Button.inline("Yes, I paid", b'paid_yes'),
                    Button.inline("No, I have not", b'paid_no')
                ]
            )
            print(f"User {sender_id} chose to continue with bot.")
        
        elif query.data == b'wait_mentor':
            user_states[sender_id] = "MENTOR_QUEUE"
            wait_message = get_wait_message()
            await query.edit(wait_message)
            print(f"User {sender_id} chose to wait for mentor.")
    
    # --- 2. User answers "Have you paid?" ---
    elif state == "AWAITING_PREMIUM_Q":
        if query.data == b'paid_yes':
            user_states[sender_id] = "PAID_PENDING_VERIFY"
            wait_message_part = get_wait_message().split('\n\n', 1)[1] 
            
            await query.edit(
                "Great, thank you! 🙏\n\n"
                "I've marked you as pending verification. A human mentor will personally "
                "check the payment and get you added to the premium group.\n\n" +
                wait_message_part + "\n\n"
                "_(This is an automated response. A human mentor will reply next.)_"
            )
            print(f"User {sender_id} claims they paid. Marked for verification.")
        
        elif query.data == b'paid_no':
            user_states[sender_id] = "AWAITING_PAY_METHOD"
            await query.edit(
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
            
    # --- 3. User chooses a payment method ---
    elif state == "AWAITING_PAY_METHOD":
        if query.data == b'pay_card':
            user_states[sender_id] = "SENT_WHOP_LINK"
            await query.edit(
                f"Perfect. You can use this secure link to pay with a credit card.\n\n"
                f"**Payment Link:** {WHOP_PAYMENT_LINK}\n\n"
                "After payment, you will receive a confirmation. Please "
                "message the mentor here after you've paid to be added to the group.\n\n"
                "_(This is an automated response)_"
            )
            print(f"User {sender_id} clicked Pay with Card. Sent Whop link.")
        
        elif query.data == b'pay_btc':
            user_states[sender_id] = "SENT_BTC_ADDRESS"
            address_to_send = random.choice(BTC_ADDRESSES)
            
            await query.edit(
                "Great. Please send **$50 USD** of Bitcoin (BTC) to the following address:\n\n"
                f"`{address_to_send}`\n\n"
                "**IMPORTANT:** This is the *only* official address. After you have sent the payment, "
                "please click the button below.\n\n"
                "_(This is an automated response)_"
            )
            await client.send_message(
                sender_id,
                "Click here *after* you have sent the Bitcoin:",
                buttons=[Button.inline("✅ I HAVE SENT THE PAYMENT", b'btc_sent')]
            )
            print(f"User {sender_id} clicked Pay with Bitcoin.")
            
        elif query.data == b'wait_mentor_payment':
            user_states[sender_id] = "MENTOR_QUEUE"
            wait_message = get_wait_message()
            await query.edit(wait_message)
            print(f"User {sender_id} is waiting for the mentor.")

    # --- 4. User confirms they sent the Bitcoin ---
    elif state == "SENT_BTC_ADDRESS":
        if query.data == b'btc_sent':
            user_states[sender_id] = "BTC_PENDING_VERIFY"
            wait_message_part = get_wait_message().split('\n\n', 1)[1] # Get timing
            
            await query.edit(
                "Thank you! 🙏 Your payment has been marked as pending.\n\n"
                "A mentor will **personally verify the transaction** on the blockchain "
                "and will reply here to onboard you.\n\n" +
                wait_message_part + "\n\n"
                "_(This is an automated response. A human mentor will reply next.)_"
            )
            print(f"User {sender_id} claims they sent Bitcoin. Marked for verification.")


async def main():
    print("Personal Assistant (goku2) is starting...")
    await client.start()
    print("Personal Assistant (goku2) is running. Waiting for new DMs...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
