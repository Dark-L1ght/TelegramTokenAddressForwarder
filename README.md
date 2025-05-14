# Telegram Token Contract Address Autoforwarder

The Telegram Token Contract Address Autoforwarder is a Python script that allows you to automatically forward Contract Addresses from one chat (group or channel) to another. It works with both groups and channels, requiring only the necessary permissions to access the messages.
This Repository is a Clone of [Telegram-Autoforwarder](https://github.com/redianmarku/Telegram-Autoforwarder), With a modification from myself.

## Features

- Automatically Forward Token CAs.
- Works with both groups and channels.
- Multiple groups and channels.
- Simple setup and usage.

## How it Works

The script uses the Telethon library to interact with the Telegram API. You provide the script with your Telegram API ID, API hash, and phone number for authentication. Then, you can choose to list all chats you're a part of and select the ones you want to use for forwarding messages. Once configured, the script continuously checks for messages in the specified source chat and forwards them to the destination chat if they contain any Contract Addresses.

## Setup and Usage

1. Clone the repository:

   ```bash
   git clone https://github.com/Dark-L1ght/TelegramAutoForwarder.git
   cd Telegram-Autoforwarder
   ```

2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure the script:

   - Open `TelegramForwarder.py` file and provide your Telegram API ID, API hash, and phone number in the appropriate variables.
   - Modify other settings as needed directly in the script.

4. Run the script:

   ```bash
   python TelegramForwarder.py
   ```

5. Choose an option:
   - List Chats: View a list of all chats you're a part of and select the ones to use for message forwarding.
   - Forward Messages From Multiple Sources: Enter the source chat IDs, destination chat ID.
   - Use Saved Configuration: Use IDs from prior usage.

## Notes

- Remember to keep your API credentials secure and do not share them publicly.
- Ensure that you have the necessary permissions to access messages in the chats you want to use.
- Adjust the script's behavior and settings according to your requirements.

## License

This project is licensed under the MIT License.
