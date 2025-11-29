import logging
import time
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Monitor:
    def __init__(self, config, mt5_client):
        self.config = config
        self.mt5 = mt5_client
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("trading_bot.log"),
                logging.StreamHandler()
            ]
        )

    def send_telegram_message(self, message):
        """
        Send message to Telegram.
        """
        token = self.config.get('telegram_bot_token')
        chat_id = self.config.get('telegram_chat_id')
        
        if not token or not chat_id:
            logger.warning("Telegram token or chat_id not configured. Skipping alert.")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        
        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to send Telegram message: {response.text}")
        except Exception as e:
            logger.error(f"Exception sending Telegram message: {e}")

    def send_alert(self, message):
        """
        Send general alert to Telegram.
        """
        logger.info(f"ALERT: {message}")
        self.send_telegram_message(f"⚠️ *ALERT*\n{message}")

    def send_trade_notification(self, signal, lot_size, result):
        """
        Send trade execution notification.
        """
        symbol = signal.symbol
        side = signal.side
        price = result.get('price', signal.entry_price)
        sl = signal.sl_price
        tp = signal.tp_price
        ticket = result.get('order', 'Unknown')
        
        msg = (
            f"🚀 *TRADE EXECUTED*\n"
            f"Symbol: *{symbol}*\n"
            f"Side: *{side}*\n"
            f"Lot: *{lot_size}*\n"
            f"Price: *{price}*\n"
            f"SL: {sl}\n"
            f"TP: {tp}\n"
            f"Ticket: `{ticket}`\n"
            f"Reason: {signal.reason}"
        )
        self.send_telegram_message(msg)

    def send_summary(self, hours=4):
        """
        Send P&L summary for the last n hours.
        """
        to_date = datetime.now()
        from_date = to_date - timedelta(hours=hours)
        
        deals = self.mt5.get_history_deals(from_date, to_date)
        
        total_profit = 0.0
        total_deals = 0
        winning_deals = 0
        losing_deals = 0
        
        # Filter for entry/exit deals (exclude balance operations if possible, though history_deals usually includes them)
        # Entry deals usually have profit=0. Exit deals have profit.
        # We sum up profit.
        
        for deal in deals:
            # deal_type = deal.get('type') # 0=BUY, 1=SELL, 2=BALANCE
            # entry = deal.get('entry') # 0=IN, 1=OUT, 2=INOUT, 3=OUT_BY
            
            profit = deal.get('profit', 0.0)
            swap = deal.get('swap', 0.0)
            commission = deal.get('commission', 0.0)
            net_profit = profit + swap + commission
            
            # Only count deals that affect P&L (usually exits)
            if net_profit != 0:
                total_profit += net_profit
                total_deals += 1
                if net_profit > 0:
                    winning_deals += 1
                else:
                    losing_deals += 1
                    
        msg = (
            f"📊 *SUMMARY ({hours}h)*\n"
            f"Time: {to_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"Deals: {total_deals}\n"
            f"Win/Loss: {winning_deals}/{losing_deals}\n"
            f"Total P&L: *{total_profit:.2f}*"
        )
        
        logger.info(f"Sending summary: {msg}")
        self.send_telegram_message(msg)

    def send_heartbeat(self, balance):
        """
        Send a heartbeat message with current balance.
        """
        msg = f"💓 *Heartbeat*\nBot is alive.\nBalance: *${balance:.2f}*"
        logger.info(f"Sending heartbeat: {msg}")
        self.send_telegram_message(msg)

    def poll_and_alert(self):
        """
        Periodic check for account status and alerts.
        """
        pass
