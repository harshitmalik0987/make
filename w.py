from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, ChatWriteForbiddenError
import asyncio
import logging

# === CONFIGURATION ===
# Replace these with your own values from https://my.telegram.org
api_id = 18479833  # Your API ID
api_hash = '8ffb643f4492979a8c5eb56fe43ec6d7'  # Your API Hash
session_name = 'us_session'  # Name for the session file

# Initial state
is_forwarding = False
message = "Default message"  # Initial message to send
interval = 60  # Default interval in seconds

# Set up logging to see what the bot is doing
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('telethon.client.updates').setLevel(logging.WARNING)

# Function to get all joined groups
async def get_joined_groups(client):
    """Return a list of all group chat IDs the user has joined."""
    group_ids = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        # Check if it's a group or supergroup
        if hasattr(entity, 'megagroup') and entity.megagroup:
            group_ids.append(entity.id)
        elif hasattr(entity, 'group') and entity.group:
            group_ids.append(entity.id)
    return group_ids

# Background task to send messages to groups
async def forwarding_loop(client):
    global is_forwarding, message, interval
    group_ids = await get_joined_groups(client)
    index = 0
    while True:
        if is_forwarding and group_ids:
            chat_id = group_ids[index % len(group_ids)]
            try:
                await client.send_message(chat_id, message)
                logging.info(f"Sent message to chat ID {chat_id}")
            except FloodWaitError as e:
                logging.warning(f"FloodWait: waiting {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except ChatWriteForbiddenError:
                logging.warning(f"No permission to write to chat ID {chat_id}")
            except Exception as e:
                logging.error(f"Failed to send to {chat_id}: {e}")
            index += 1
        await asyncio.sleep(interval)

# Handle commands from Saved Messages
@client.on(events.NewMessage(from_users='me'))
async def handle_commands(event):
    global is_forwarding, message, interval
    text = event.message.text
    if text.startswith('/'):
        parts = text.split(maxsplit=1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ''
        
        if command == '/start':
            is_forwarding = True
            await event.reply("Forwarding started.")
            logging.info("Forwarding started by command")
        
        elif command == '/stop':
            is_forwarding = False
            await event.reply("Forwarding stopped.")
            logging.info("Forwarding stopped by command")
        
        elif command == '/set':
            try:
                new_interval = int(args)
                if new_interval <= 0:
                    raise ValueError
                interval = new_interval
                await event.reply(f"Interval set to {interval} seconds.")
                logging.info(f"Interval set to {interval} seconds")
            except ValueError:
                await event.reply("Invalid interval. Use /set <seconds> where seconds > 0")
                logging.warning("Invalid interval provided")
        
        elif command == '/message':
            if args.strip():
                message = args
                await event.reply("Message set.")
                logging.info(f"Message set to: {message}")
            else:
                await event.reply("Usage: /message <text>")
                logging.warning("No message text provided")

# Main function to run the bot
async def main():
    client = TelegramClient(session_name, api_id, api_hash)
    try:
        await client.start()
        logging.info("Bot started successfully.")
        # Start the forwarding loop in the background
        asyncio.create_task(forwarding_loop(client))
        # Keep the bot running
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        await client.disconnect()
        logging.info("Bot disconnected.")

# Run the bot
if __name__ == '__main__':
    asyncio.run(main())
