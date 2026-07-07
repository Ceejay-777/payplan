from unittest.mock import patch
from django.test import TestCase
from django.conf import settings

from cohorts.email_notifications import send_invitation_email, send_payer_joined_notification


class TestInvitationEmail(TestCase):
    @patch('cohorts.email_notifications.send_html_email')
    def test_sends_invitation_to_payer(self, mock_send):
        send_invitation_email(
            payer_email='payer@example.com',
            cohort_name='Test Cohort',
            resolution_link='https://example.com?p=abc&plt=def',
            amount='100.00',
        )
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        self.assertEqual(kwargs['recipient'], 'payer@example.com')
        self.assertIn('Test Cohort', kwargs['subject'])
        self.assertEqual(kwargs['template_path'], 'emails/cohort_invitation.html')
        self.assertIn('resolution_link', kwargs['context'])
        self.assertIn('cohort_name', kwargs['context'])

    @patch('cohorts.email_notifications.send_html_email')
    def test_skips_when_no_email(self, mock_send):
        send_invitation_email(
            payer_email='',
            cohort_name='Test',
            resolution_link='link',
            amount='100.00',
        )
        mock_send.assert_not_called()


class TestPayerJoinedNotification(TestCase):
    @patch('cohorts.email_notifications.send_html_email')
    def test_sends_notification_to_organizer(self, mock_send):
        send_payer_joined_notification(
            organizer_email='organizer@example.com',
            organizer_name='Organizer',
            cohort_name='Test Cohort',
            payer_email='payer@example.com',
        )
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        self.assertEqual(kwargs['recipient'], 'organizer@example.com')
        self.assertIn('Test Cohort', kwargs['subject'])
        self.assertEqual(kwargs['template_path'], 'emails/payer_joined.html')
