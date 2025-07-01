from telethon import TelegramClient, types
from telethon.errors import FloodWaitError, ChatWriteForbiddenError
import asyncio
import logging

# === CONFIGURATION ===
api_id = 18479833  # Your API ID
api_hash = '8ffb643f4492979a8c5eb56fe43ec6d7'  # Your API HASH
session_name = 'us_session'  # .session file name

# Broadcast message
MESSAGE = '''✅ Buying Old Group 2016-2022 best price in Market

🗣 1-6 Month 2023 : 5.5$
🗣 7-12 Month 2023 : 5$

⭐️ Message me'''

# Interval between broadcasts (in seconds)
INTERVAL = 300  # 5 minutes

# Configure logging with timestamps
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('telethon.client.updates').setLevel(logging.WARNING)

async def get_joined_groups(client):
    """Return a list of all group and megagroup chat IDs the bot has joined."""
    group_ids = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, types.Chat) or (isinstance(entity, types.Channel) and entity.megagroup):
            group_ids.append(entity.id)
    return group_ids

async def broadcast_to_joined_groups(client):
    sent = []
    group_ids = await get_joined_groups(client)
    for chat_id in group_ids:
        try:
            await client.send_message(chat_id, MESSAGE)
            logging.info(f"Sent promo to chat ID {chat_id}")
            sent.append(chat_id)
            await asyncio.sleep(5)  # small delay to respect rate limits
        except FloodWaitError as e:
            logging.warning(f"FloodWait: waiting {e.seconds}s before continuing.")
            await asyncio.sleep(e.seconds)
        except ChatWriteForbiddenError:
            logging.warning(f"No write permission for chat ID {chat_id}")
        except Exception as e:
            logging.error(f"Failed to send to {chat_id}: {e}")
    return sent

async def main():
    client = TelegramClient(session_name, api_id, api_hash)
    try:
        await client.start()
        logging.info("Client started. Beginning scheduled broadcasts...")
        while True:
            sent = await broadcast_to_joined_groups(client)
            logging.info(f"Round complete. Messages sent to {len(sent)} groups.")
            await asyncio.sleep(INTERVAL)
    except KeyboardInterrupt:
        logging.info("Interrupted; shutting down.")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        await client.disconnect()
        logging.info("Client disconnected.")

if __name__ == '__main__':
    asyncio.run(main())
