import unittest
import time
from unittest.mock import patch, MagicMock, mock_open
import bot

class TestFullBot(unittest.TestCase):

    def setUp(self):
        """Set up a clean state for each test."""
        bot.PROCESSED_ORDERS = {}
        bot.PRODUCT_INDEX = {
            'test_product': {
                'all_blocks': [f'Card {i}' for i in range(10)],
                'by_bic': {}, 'by_postal_dept': {}, 'by_age_range': {}
            }
        }
        self.patcher_os_path = patch('os.path.exists', return_value=True)
        self.mock_file_patcher = patch('builtins.open', new_callable=mock_open)
        self.patcher_os_path.start()
        self.mock_file_patcher.start()

    def tearDown(self):
        """Clean up after each test."""
        self.patcher_os_path.stop()
        self.mock_file_patcher.stop()

    @patch('bot.load_from_file')
    @patch('bot.bot')
    def test_admin_view_payments(self, mock_bot, mock_load):
        """Test admin can view a list of pending payments."""
        mock_load.return_value = {"123": {"user_data": {"username": "user1"}, "quantity": 5, "product": "test_product"}}
        mock_call = MagicMock(from_user=MagicMock(id=bot.ADMIN_USER_ID), message=MagicMock(chat=MagicMock(id=1), message_id=1), data="admin_payments")
        bot.callback_handler(mock_call)
        self.assertTrue(mock_bot.send_message.called)
        self.assertIn("user1", mock_bot.send_message.call_args[0][1])

    @patch('bot.process_paid_order')
    @patch('bot.check_oxapay_payment', return_value={"paid": True})
    @patch('bot.load_from_file')
    @patch('bot.bot')
    def test_admin_validate_payment_success(self, mock_bot, mock_load, mock_check, mock_process):
        """Test admin can successfully validate a paid order."""
        mock_load.return_value = {"123": {"track_id": "track1"}}
        mock_call = MagicMock(from_user=MagicMock(id=bot.ADMIN_USER_ID), message=MagicMock(chat=MagicMock(id=1), message_id=1), data="validate_payment:123")
        bot.callback_handler(mock_call)
        mock_process.assert_called_once()

    @patch('bot.process_paid_order')
    @patch('bot.check_oxapay_payment', return_value={"paid": False})
    @patch('bot.load_from_file')
    @patch('bot.bot')
    def test_admin_validate_payment_fail_not_paid(self, mock_bot, mock_load, mock_check, mock_process):
        """Test admin validation fails if payment is not yet confirmed."""
        mock_load.return_value = {"123": {"track_id": "track1"}}
        mock_call = MagicMock(from_user=MagicMock(id=bot.ADMIN_USER_ID), message=MagicMock(chat=MagicMock(id=1), message_id=1), data="validate_payment:123")
        bot.callback_handler(mock_call)
        self.assertFalse(mock_process.called)

    @patch('bot.process_paid_order')
    @patch('bot.check_oxapay_payment', return_value={"paid": True})
    def test_automatic_payment_flow(self, mock_check_payment, mock_process_order):
        """Test the automatic payment monitoring flow triggers processing."""
        with patch('time.sleep', return_value=None):
            chat_id = 12345
            payment_data = {"track_id": "auto_track_1"}
            bot.monitor_oxapay_payment(chat_id, payment_data)
            time.sleep(0.01)
            mock_process_order.assert_called_once_with(chat_id, payment_data, "auto_track_1")

if __name__ == '__main__':
    unittest.main()
