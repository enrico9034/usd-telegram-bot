import yfinance as yf
import pandas as pd
import time
import requests
import os
import logging
from ecbdata import ecbdata
import datetime
import pytz
import sqlite3

TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
STOCK_SYMBOL = os.environ['STOCK_SYMBOL']
THRESHOLD = float(os.environ['THRESHOLD'])
INVOICE_AMOUNT_USD = float(os.environ.get('INVOICE_AMOUNT_USD', '1000'))  # Default to 1000 if not set
DB_FILE = os.environ.get('DB_FILE', 'data.db')
OFFSET_TELEGRAM = None
DELTA = float(os.environ.get('DELTA', '0.0021'))  # Default to 0.21% if not set

DECIMALS = 2  # <--- Change here if you want to round to fewer/more decimals

logging.basicConfig(format='%(asctime)s %(levelname)s:\t%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def create_db():
    # Check if database exists, if not create it
    if os.path.exists(DB_FILE):
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            user TEXT,
            usd_amount INTEGER,
            ecb_rate INTEGER,
            changed BOOLEAN DEFAULT 0,
            reached BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def save_invoice(user, usd_amount, ecb_rate):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO invoices (date, user, usd_amount, ecb_rate)
        VALUES (?, ?, ?, ?)
    ''', (datetime.datetime.now(pytz.timezone('Europe/Rome')).isoformat()[0:10], user, usd_amount, int(ecb_rate*10000)))
    conn.commit()
    conn.close()

def set_invoice_changed(invoice_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE invoices
        SET changed = 1
        WHERE id = ?
    ''', (invoice_id,))
    conn.commit()
    conn.close()

def get_pending_invoices():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user, usd_amount, ecb_rate, reached
        FROM invoices
        WHERE changed = 0
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_user_pending_invoices(user):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, date, usd_amount, ecb_rate
        FROM invoices
        WHERE changed = 0 AND user = ?
    ''', (user,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_today_ecb_change():
    if datetime.datetime.now(pytz.timezone('Europe/Rome')).hour < 16:
        return None
    today = datetime.datetime.now(pytz.timezone('Europe/Rome')).isoformat()[0:10]
    df_today = ecbdata.get_series('EXR.D.USD.EUR.SP00.A', 
                            start=today,
                            end=today)
    usd_eur=1/df_today.OBS_VALUE
    return float(usd_eur.iat[0].round(4))

# Read messages from chat with api
def get_updates():
    global OFFSET_TELEGRAM
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {'timeout': 1}
    if OFFSET_TELEGRAM:
        params['offset'] = OFFSET_TELEGRAM
    response = requests.get(url, params=params)
    return response.json()

def check_for_commands():
    global OFFSET_TELEGRAM
    updates = get_updates()
    if not updates.get('ok'):
        logger.error("Failed to fetch updates from Telegram.")
        return None

    for result in updates.get('result', []):
        OFFSET_TELEGRAM = result.get("update_id", 0) + 1  # Update offset to the latest update_id + 1
        message = result.get('message', {})
        text = message.get('text', '')
        chat_id = message.get('chat', {}).get('id')
        username = message.get('from', {}).get('username', 'unknown')

        if chat_id != int(CHAT_ID):
            continue  # Ignore messages from other chats

        if text.startswith('/price'):
            current_price = get_current_price(STOCK_SYMBOL)
            if current_price is not None:
                telegram_send_msg(f"Current price of *{STOCK_SYMBOL}* is *{current_price}*")
            else:
                telegram_send_msg(f"Could not fetch the price for *{STOCK_SYMBOL}*.")

        elif text.startswith('/ecb'):
            ecb_change = get_today_ecb_change()
            if ecb_change is not None:
                telegram_send_msg(f"Today's ECB USD/EUR rate is *{ecb_change}*")
            else:
                telegram_send_msg("ECB data is available only after 16:00 CET.")

        elif text.startswith('/invoice'):
            ecb_change = get_today_ecb_change()
            if ecb_change is not None:
                eur_amount = round(INVOICE_AMOUNT_USD * ecb_change, 2)
                eur_amount_without_tax_disc = round(eur_amount - 2, 2)  # Assuming stamp duty is 2 EUR
                save_invoice(user=username, usd_amount=INVOICE_AMOUNT_USD, ecb_rate=ecb_change)
                telegram_send_msg(f"Invoice of *{INVOICE_AMOUNT_USD} USD*\nReal Value: *{eur_amount} EUR*\n(without tax disc: *{eur_amount_without_tax_disc} EUR*)\nat today's ECB change of *{ecb_change}*")
            else:
                telegram_send_msg("*ECB data is available only after 16:00 CET.*")

        elif text.startswith('/getinvoices'):
            invoices = get_user_pending_invoices(username)
            if invoices:
                msg = "Your pending invoices:\n"
                for inv in invoices:
                    inv_id, date, usd_amount, ecb_rate = inv
                    msg += f"ID: {inv_id} | {date} | {ecb_rate/10000}\n"
                telegram_send_msg(msg)
            else:
                telegram_send_msg("You have no pending invoices.")

        elif text.startswith('/changeall'):
            invoices = get_user_pending_invoices(username)
            if not invoices:
                telegram_send_msg("No pending invoices to check.")
                continue
            for inv in invoices:
                inv_id, user, usd_amount, ecb_rate = inv
                set_invoice_changed(inv_id)
                telegram_send_msg(f"Invoice ID: *{inv_id}* for user *{user}* has been set as changed")

        elif text.startswith('/change'):
            parts = text.split()
            if len(parts) != 2 or not parts[1].isdigit():
                telegram_send_msg("Usage: /change <invoice_id>")
                continue
            inv_id = int(parts[1])
            invoices = get_user_pending_invoices(username)
            invoice_ids = [inv[0] for inv in invoices]
            if inv_id not in invoice_ids:
                telegram_send_msg(f"No pending invoice found with ID: {inv_id}")
                continue
            set_invoice_changed(inv_id)
            telegram_send_msg(f"Invoice ID: *{inv_id}* has been set as changed")

        elif text.startswith('/simulateall'):
            invoices = get_user_pending_invoices(username)
            invoice_ids = [inv[0] for inv in invoices]
            for inv in invoices:
                _, _, usd_amount, original_ecb_change = inv
                original_ecb_change = original_ecb_change / 10000  # Convert back to float
                telegram_send_msg(
                    f"Invoice ID: *{inv[0]}* for user @{username}\n"
                    f"Original ECB rate: *{original_ecb_change}*\n"
                    f"Current price: *{get_current_price(STOCK_SYMBOL)}*\n"
                    f"Fineco price: *{get_current_price(STOCK_SYMBOL) - DELTA}*\n"
                    f"ECB Change: *{round(usd_amount * original_ecb_change, 2)} EUR*\n"
                    f"EUR Change: *{round(usd_amount * (get_current_price(STOCK_SYMBOL) - DELTA), 2)} EUR*\n"
                    f"Delta change reached: *{round(usd_amount * (get_current_price(STOCK_SYMBOL) - original_ecb_change - DELTA), 2)} EUR*"
                    )

        elif text.startswith('/simulate'):
            parts = text.split()
            if len(parts) != 2 or not parts[1].isdigit():
                telegram_send_msg("Usage: /simulate [invoice_id]")
                continue
            inv_id = int(parts[1])
            invoices = get_user_pending_invoices(username)
            invoice_ids = [inv[0] for inv in invoices]
            if inv_id not in invoice_ids:
                telegram_send_msg(f"No pending invoice found with ID: {inv_id}")
                continue
            for inv in invoices:
                if inv[0] == inv_id:
                    _, _, usd_amount, original_ecb_change = inv
                    original_ecb_change = original_ecb_change / 10000  # Convert back to float
                    telegram_send_msg(
                        f"Invoice ID: *{inv_id}* for user @{username}\n"
                        f"Original ECB rate: *{original_ecb_change}*\n"
                        f"Current price: *{get_current_price(STOCK_SYMBOL)}*\n"
                        f"Fineco price: *{get_current_price(STOCK_SYMBOL) - DELTA}*\n"
                        f"ECB Change: *{round(usd_amount * original_ecb_change, 2)} EUR*\n"
                        f"EUR Change: *{round(usd_amount * (get_current_price(STOCK_SYMBOL)- DELTA), 2)} EUR*\n"
                        f"Delta change reached: *{round(usd_amount * (get_current_price(STOCK_SYMBOL) - original_ecb_change - DELTA), 2)} EUR*"
                        )

        elif text.startswith('/help'):
            telegram_send_msg(
                "*USD Telegram Bot - Commands*\n"
                "/price - Get current stock price\n"
                "/ecb - Get today's ECB USD/EUR rate\n"
                "/invoice - Create an invoice for 7490 USD\n"
                "/getinvoices - List your pending invoices\n"
                "/change [invoice_id] - Mark an invoice as changed\n"
                "/changeall - Mark all pending invoices as changed\n"
                "/help - Show this help message\n"
            )

def check_change_reached(original_ecb_change):
    current_price = get_current_price(STOCK_SYMBOL)
    if current_price is None:
        return False
    if current_price - original_ecb_change >= DELTA:
        return True
    return False

def set_reached(invoice_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE invoices
        SET reached = 1
        WHERE id = ?
    ''', (invoice_id,))
    conn.commit()
    conn.close()

def unset_reached(invoice_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE invoices
        SET reached = 0
        WHERE id = ?
    ''', (invoice_id,))
    conn.commit()
    conn.close()

def notify_change_reached():
    invoices = get_pending_invoices()
    for inv in invoices:
        invoice_id, user, usd_amount, original_ecb_change, reached = inv
        original_ecb_change = original_ecb_change / 10000  # Convert back to float
        if check_change_reached(original_ecb_change):
            if not reached:
                set_reached(invoice_id)
                telegram_send_msg(
                    f"Invoice ID: *{invoice_id}* for user @{user} has reached the desired change!\n"
                    f"Original ECB rate: *{original_ecb_change}*\n"
                    f"Current price: *{get_current_price(STOCK_SYMBOL)}*\n"
                    f"Fineco price: *{get_current_price(STOCK_SYMBOL) - DELTA}*\n"
                    f"ECB Change: *{round(usd_amount * original_ecb_change, 2)} EUR*\n"
                    f"EUR Change: *{round(usd_amount * (get_current_price(STOCK_SYMBOL) - DELTA), 2)} EUR*\n"
                    f"Delta change reached: *{round(usd_amount * (get_current_price(STOCK_SYMBOL) - original_ecb_change - DELTA), 2)} EUR*"
                )
        else:
            if reached:
                unset_reached(invoice_id)
                telegram_send_msg(
                    f"Invoice ID: *{invoice_id}* for user @{user} is no longer at the desired change.\n"
                )


def truncate(number, decimals=0):
    if decimals < 0:
        raise ValueError("decimals must be >= 0")
    multiplier = 10 ** decimals
    return int(number * multiplier) / multiplier

def get_current_price(ticker):
    ticker = ticker.upper()
    try:
        data = yf.download(ticker, period='5d')
        if data.empty:
            logger.error(f"No data for ticker: {ticker}")
            return None
        last_close = data['Close'].sort_values('Date', ascending=False).iloc[0][f'{ticker}']
        return float(truncate(last_close, 4))
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        return None

def telegram_send_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'disable_web_page_preview': True,
        'parse_mode': 'Markdown'
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        resp = r.json()
        if resp.get('ok'):
            logging.info("Message sent successfully.")
        else:
            logger.error(f"Failed to send message. Reason: {resp}")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")

def monitor_stock():
    create_db()
    check_for_commands()  # Check for any commands at startup
    initial_price = get_current_price(STOCK_SYMBOL)
    if initial_price is None:
        telegram_send_msg("Unable to fetch initial price, aborting monitor.")
        return

    initial_price_rounded = truncate(initial_price, DECIMALS)
    telegram_send_msg(
        f"Monitoring *{STOCK_SYMBOL}*\nInitial price: *{initial_price}*\n"
        f"Threshold: *{THRESHOLD}%*\n"
        f"Initial (rounded): *{initial_price_rounded}*"
    )

    while True:
        # Check for commands every second (more responsive)
        for i in range(10):  # 10 iterations of 1 second = 10 seconds total
            check_for_commands()  # Check for any commands
            time.sleep(1)  # Wait 1 second
        
        # Monitor price every 10 seconds
        current_price = get_current_price(STOCK_SYMBOL)
        if current_price is None:
            logger.warning("Couldn't get current price. Retrying...")
            continue

        percent_change = abs((initial_price - current_price) / initial_price * 100)
        logging.info(f"Current price: {current_price} | Change: {percent_change:.2f}%")

        # Notify if threshold is exceeded
        if percent_change >= THRESHOLD:
            telegram_send_msg(
                f"*{STOCK_SYMBOL}* has changed by *{percent_change:.2f}%* (>{THRESHOLD}%)!\n"
                f"Current price: *{current_price}*"
            )
            initial_price = current_price  # Update reference price

        # Notify only if significant figure changes (desired decimal)
        current_price_rounded = truncate(current_price, DECIMALS)
        if current_price_rounded != initial_price_rounded:
            telegram_send_msg(
                f"*{STOCK_SYMBOL}* price moved from *{initial_price_rounded:.2f}* to *{current_price_rounded:.2f}*"
            )
            initial_price_rounded = current_price_rounded
        
        notify_change_reached()  # Check if any invoice has reached the desired change

if __name__ == "__main__":
    monitor_stock()