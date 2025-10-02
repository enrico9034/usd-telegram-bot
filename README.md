# USD Telegram Bot

A Telegram bot that monitors USD/EUR exchange rates and stock prices, providing notifications and invoice management capabilities. This bot integrates with the European Central Bank (ECB) data and Yahoo Finance to track financial metrics and send alerts to Telegram users.

## Features

- 📈 **Stock Price Monitoring**: Get real-time stock prices using Yahoo Finance
- 💱 **ECB Exchange Rate Tracking**: Monitor official USD/EUR exchange rates from the European Central Bank
- 📋 **Invoice Management**: Create, track, and manage USD invoices with automatic rate conversion
- � **Invoice Simulation**: Simulate currency conversions with current rates and Fineco pricing calculations
- �🔔 **Threshold Alerts**: Receive notifications when exchange rates change beyond specified thresholds
- 💾 **SQLite Database**: Persistent storage for invoice data and user interactions
- 🐳 **Docker Support**: Easy deployment with Docker and Docker Compose

## Bot Commands

- `/price` - Get current stock price for the configured symbol
- `/ecb` - Get today's official ECB USD/EUR exchange rate
- `/invoice` - Create a new invoice with the configured USD amount
- `/getinvoices` - List all your pending invoices
- `/change [invoice_id]` - Mark a specific invoice as changed/processed
- `/changeall` - Mark all your pending invoices as changed/processed
- `/simulate [invoice_id]` - Simulate currency conversion for a specific invoice with current rates and Fineco pricing
- `/simulateall` - Simulate currency conversion for all pending invoices with current rates and Fineco pricing
- `/help` - Display available commands

## Prerequisites

- Python 3.x
- Docker and Docker Compose (for containerized deployment)
- Telegram Bot Token (from @BotFather)
- Telegram Chat ID

## Installation

### Option 1: Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/enrico9034/usd-telegram-bot.git
cd usd-telegram-bot
```

2. Copy the environment file and configure it:
```bash
cp env.example env
```

3. Edit the `docker-compose.yaml` file with your configuration:
```yaml
environment:
  - TELEGRAM_BOT_TOKEN=your_bot_token_here
  - CHAT_ID=your_chat_id_here
  - STOCK_SYMBOL=EUR=X
  - THRESHOLD=1
  - INVOICE_AMOUNT_USD=7490
  - DB_FILE=/app/data/invoices.db
```

4. Run with Docker Compose:
```bash
docker compose up -d
```

### Option 2: Local Development

1. Clone the repository:
```bash
git clone https://github.com/enrico9034/usd-telegram-bot.git
cd usd-telegram-bot
```
2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

3. Install dependencies:
```bash
cd app
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
source ../env
```

5. Run the application:
```bash
python app.py
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from @BotFather | - | ✅ |
| `CHAT_ID` | Telegram chat ID where messages will be sent | - | ✅ |
| `STOCK_SYMBOL` | Yahoo Finance stock symbol to monitor | `EUR=X` | ✅ |
| `THRESHOLD` | Percentage threshold for price change alerts | `1` | ✅ |
| `INVOICE_AMOUNT_USD` | Default USD amount for invoices | `1000` | ❌ |
| `DELTA` | Delta value for Fineco price calculations (default 0.21%) | `0.0021` | ❌ |
| `DB_FILE` | Path to SQLite database file | `data.db` | ❌ |

### Getting Your Telegram Credentials

1. **Bot Token**: Message @BotFather on Telegram to create a new bot and get your token
2. **Chat ID**: 
   - Add your bot to a chat or group
   - Send a message to the bot
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response

## Database Schema

The bot uses SQLite to store invoice data:

```sql
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    user TEXT,
    usd_amount INTEGER,
    ecb_rate INTEGER,
    changed BOOLEAN DEFAULT 0,
    reached BOOLEAN DEFAULT 0
);
```

## Project Structure

```
usd-telegram-bot/
├── app/
│   ├── app.py              # Main application logic
│   ├── Dockerfile          # Docker configuration
│   └── requirements.txt    # Python dependencies
├── local/
│   └── invoices.db        # SQLite database (created at runtime)
├── docker-compose-example.yaml
├── env.example           # Environment variables template
└── README.md            # This file
```

## How It Works

1. **Monitoring Loop**: The bot continuously polls for new Telegram messages and processes commands
2. **ECB Integration**: Uses the `ecbdata` library to fetch official EUR/USD exchange rates
3. **Stock Tracking**: Integrates with Yahoo Finance via `yfinance` for real-time stock prices
4. **Invoice Management**: Stores invoice data with exchange rates for later reference
5. **Notifications**: Sends Telegram messages for price alerts and user interactions

## Development

### Adding New Features

1. Fork the repository
2. Create a feature branch
3. Make your changes in `app/app.py`
4. Test using the local development setup
5. Submit a pull request

## Troubleshooting

### Common Issues

1. **Bot not responding**: Check your `TELEGRAM_BOT_TOKEN` and ensure the bot is active
2. **No messages received**: Verify your `CHAT_ID` is correct
3. **Database errors**: Ensure the `local/` directory has write permissions
4. **ECB data unavailable**: ECB rates are only available after 4 PM CET on business days

### Logs

When running with Docker Compose, view logs with:
```bash
docker compose logs -f app
```

## License

This project is open source. Please check the repository for license details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you encounter any issues or have questions, please open an issue on the GitHub repository.