import asyncio
import logging
import re
import json
import os
import sys
import signal
from telethon import TelegramClient, events, errors
from datetime import datetime
from typing import List, Dict, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_forwarder.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramForwarder:
    def __init__(self, api_id: str, api_hash: str, phone_number: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.session_file = f'session_{phone_number}'
        self.client = TelegramClient(self.session_file, api_id, api_hash)
        self.source_entities = {}  # Cache for source chat entities
        self.running = True
        
        # Configure the client to handle disconnections
        self.client.flood_sleep_threshold = 60  # Sleep if hit by flood wait
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully"""
        logger.info("Shutdown signal received, stopping forwarder...")
        self.running = False
        if self.client.is_connected():
            asyncio.create_task(self.client.disconnect())
            
    async def ensure_connected(self) -> bool:
        """Ensure client is connected and authorized with error handling"""
        try:
            if not self.client.is_connected():
                await self.client.connect()
                
            if not await self.client.is_user_authorized():
                logger.info(f"Requesting login code for {self.phone_number}")
                await self.client.send_code_request(self.phone_number)
                try:
                    code = input('Enter the code received on Telegram: ')
                    await self.client.sign_in(self.phone_number, code)
                except errors.SessionPasswordNeededError:
                    password = input('Two-step verification enabled. Enter your password: ')
                    await self.client.sign_in(password=password)
                logger.info("Authorization successful")
                
            return True
            
        except errors.FloodWaitError as e:
            logger.error(f"Rate limited! Need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return False
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            await asyncio.sleep(5)  # Wait before retry
            return False

    async def list_chats(self):
        """List all chats/dialogs and save to file"""
        if not await self.ensure_connected():
            logger.error("Failed to connect to Telegram")
            return
            
        try:
            # Get a list of all dialogs
            logger.info("Fetching list of chats...")
            dialogs = await self.client.get_dialogs()
            
            output_file = f"chats_of_{self.phone_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(output_file, "w", encoding="utf-8") as chats_file:
                for dialog in dialogs:
                    chat_info = f"Chat ID: {dialog.id}, Title: {dialog.title}, Type: {dialog.entity.__class__.__name__}"
                    logger.info(chat_info)
                    chats_file.write(f"{chat_info}\n")
            
            logger.info(f"Listed {len(dialogs)} chats and saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Error listing chats: {str(e)}")

    async def get_chat_name(self, chat_id: int) -> str:
        """Get a chat name with caching for efficiency"""
        if chat_id not in self.source_entities:
            try:
                entity = await self.client.get_entity(chat_id)
                self.source_entities[chat_id] = entity
            except Exception as e:
                logger.error(f"Error getting entity {chat_id}: {str(e)}")
                return f"Chat {chat_id}"
                
        entity = self.source_entities[chat_id]
        return entity.title if hasattr(entity, 'title') else f"Chat {chat_id}"

    async def setup_message_handlers(self, source_chat_ids: List[int], destination_chat_id: int):
        """Set up event handlers for message forwarding using events"""
        if not await self.ensure_connected():
            logger.error("Failed to connect to Telegram")
            return
            
        # Get chat names for logging
        source_names = {}
        for chat_id in source_chat_ids:
            source_names[chat_id] = await self.get_chat_name(chat_id)
            logger.info(f"Monitoring source: {source_names[chat_id]} (ID: {chat_id})")
            
        dest_name = await self.get_chat_name(destination_chat_id)
        logger.info(f"Forwarding to destination: {dest_name} (ID: {destination_chat_id})")

        # Set up the event handler for new messages
        @self.client.on(events.NewMessage(chats=source_chat_ids))
        async def new_message_handler(event):
            try:
                # Get source chat info
                source_id = event.chat_id
                source_name = source_names.get(source_id, await self.get_chat_name(source_id))
                
                if event.message.text:
                    # Look for token pattern in the message text
                    # Updated regex to detect 43 or 44 character tokens
                    match = re.search(r'\b[a-zA-Z0-9]{43,44}\b', event.message.text)
                    
                    if match:
                        token = match.group()
                        logger.info(f"Found token: {token} in {source_name}")
                        
                        # Format a cleaner message for forwarding
                        forward_msg = f"{token}"
                        
                        # Send the token to the destination
                        await self.client.send_message(
                            destination_chat_id,
                            forward_msg
                        )
                        logger.info(f"Successfully forwarded token from {source_name} to {dest_name}")
                        
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")

        logger.info("Message handlers set up successfully")
        logger.info("Waiting for new messages. Press Ctrl+C to stop.")
        
        # Keep the client running
        while self.running:
            await asyncio.sleep(1)

class ConfigManager:
    """Handle configuration storing and loading"""
    def __init__(self, config_file="telegram_config.json"):
        self.config_file = config_file
        
    def load_credentials(self) -> tuple:
        """Load API credentials from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as file:
                    config = json.load(file)
                    return (
                        config.get("api_id"),
                        config.get("api_hash"),
                        config.get("phone_number")
                    )
            return None, None, None
        except Exception as e:
            logger.error(f"Error loading credentials: {str(e)}")
            return None, None, None
            
    def save_credentials(self, api_id: str, api_hash: str, phone_number: str):
        """Save API credentials to config file"""
        try:
            config = {
                "api_id": api_id,
                "api_hash": api_hash,
                "phone_number": phone_number
            }
            with open(self.config_file, "w") as file:
                json.dump(config, file, indent=2)
            # Secure the file permissions on Unix systems
            if os.name != 'nt':  # not Windows
                os.chmod(self.config_file, 0o600)  # Read/write for owner only
        except Exception as e:
            logger.error(f"Error saving credentials: {str(e)}")

    def save_chat_config(self, source_chat_ids: List[int], destination_chat_id: int):
        """Save chat configuration for quick restart"""
        try:
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as file:
                    config = json.load(file)
                    
            config["source_chat_ids"] = source_chat_ids
            config["destination_chat_id"] = destination_chat_id
            config["last_updated"] = datetime.now().isoformat()
            
            with open(self.config_file, "w") as file:
                json.dump(config, file, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving chat config: {str(e)}")
            
    def load_chat_config(self) -> tuple:
        """Load saved chat configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as file:
                    config = json.load(file)
                    return (
                        config.get("source_chat_ids"),
                        config.get("destination_chat_id")
                    )
            return None, None
        except Exception as e:
            logger.error(f"Error loading chat config: {str(e)}")
            return None, None

async def main():
    logger.info("Starting Telegram Forwarder")
    
    # Initialize config manager
    config_manager = ConfigManager()
    
    # Attempt to read credentials from config file
    api_id, api_hash, phone_number = config_manager.load_credentials()

    # If credentials not found, prompt the user
    if not all([api_id, api_hash, phone_number]):
        api_id = input("Enter your API ID: ")
        api_hash = input("Enter your API Hash: ")
        phone_number = input("Enter your phone number (with country code): ")
        
        # Save credentials for future use
        config_manager.save_credentials(api_id, api_hash, phone_number)

    # Initialize forwarder
    forwarder = TelegramForwarder(api_id, api_hash, phone_number)
    
    # Display menu options
    print("\n=== Telegram Message Forwarder ===")
    print("1. List All Chats")
    print("2. Forward Messages from Multiple Sources")
    print("3. Use Saved Configuration")
    print("4. Exit")
    
    choice = input("\nEnter your choice (1-4): ")
    
    try:
        if choice == "1":
            await forwarder.list_chats()
            
        elif choice == "2":
            # Get the number of source chats
            num_sources = int(input("Enter the number of source chats to monitor: "))
            source_chat_ids = []
            
            # Collect all source chat IDs
            for i in range(num_sources):
                source_id = int(input(f"Enter source chat ID #{i+1}: "))
                source_chat_ids.append(source_id)
            
            destination_channel_id = int(input("Enter the destination chat ID: "))
            
            # Save this configuration
            config_manager.save_chat_config(source_chat_ids, destination_channel_id)
            
            # Start forwarding
            await forwarder.setup_message_handlers(source_chat_ids, destination_channel_id)
            
        elif choice == "3":
            # Load saved configuration
            source_chat_ids, destination_chat_id = config_manager.load_chat_config()
            
            if not source_chat_ids or not destination_chat_id:
                logger.error("No saved configuration found")
                return
                
            logger.info(f"Using saved configuration: forwarding from {len(source_chat_ids)} sources to destination {destination_chat_id}")
            
            # Start forwarding with saved configuration
            await forwarder.setup_message_handlers(source_chat_ids, destination_chat_id)
            
        elif choice == "4":
            logger.info("Exiting...")
            return
            
        else:
            logger.error("Invalid choice")
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        # Ensure client disconnects properly
        if hasattr(forwarder, 'client') and forwarder.client.is_connected():
            await forwarder.client.disconnect()
            logger.info("Disconnected from Telegram")

if __name__ == "__main__":
    asyncio.run(main())