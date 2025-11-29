import unittest
from unittest.mock import MagicMock
from datetime import datetime
from risk_manager import RiskManager

class TestRiskManagerSync(unittest.TestCase):
    def setUp(self):
        self.config = {
            'max_daily_loss_percent': 5.0,
            'max_consecutive_losses': 3,
            'risk_percent_per_trade': 1.0
        }
        self.mt5 = MagicMock()
        self.risk_manager = RiskManager(self.config, self.mt5)

    def test_sync_daily_stats_loss(self):
        # Mock deals: 1 win, 2 losses
        # Profit: +100, -50, -60 => Net: -10
        # Consecutive losses: Win, Loss, Loss => 2
        
        deals = [
            {'profit': 100.0, 'swap': 0.0, 'commission': 0.0, 'time': 1000},
            {'profit': -50.0, 'swap': 0.0, 'commission': 0.0, 'time': 2000},
            {'profit': -60.0, 'swap': 0.0, 'commission': 0.0, 'time': 3000}
        ]
        self.mt5.get_history_deals.return_value = deals
        
        self.risk_manager.sync_daily_stats()
        
        self.assertEqual(self.risk_manager.daily_loss, 10.0)
        self.assertEqual(self.risk_manager.consecutive_losses, 2)

    def test_sync_daily_stats_profit(self):
        # Profit: +100, -50 => Net: +50
        # Daily loss should be 0
        deals = [
            {'profit': 100.0, 'swap': 0.0, 'commission': 0.0},
            {'profit': -50.0, 'swap': 0.0, 'commission': 0.0}
        ]
        self.mt5.get_history_deals.return_value = deals
        
        self.risk_manager.sync_daily_stats()
        
        self.assertEqual(self.risk_manager.daily_loss, 0.0)

if __name__ == '__main__':
    unittest.main()
