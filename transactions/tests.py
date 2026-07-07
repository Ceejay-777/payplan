from django.test import TestCase

from plans.factories import PayPlanFactory, UserFactory
from plans.models import PayPlan
from transactions.models import Transaction, TransactionEvent
from transactions.services import record_transaction


class TestRecordTransaction(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(creator=self.user, status=PayPlan.Status.ACTIVE)

    def test_creates_transaction(self):
        txn = record_transaction(
            plan=self.plan,
            charge_reference="engine_ref_1",
            amount=self.plan.amount,
            cycle_number=1,
            status=Transaction.Status.CHARGE_SUCCESS,
            event_type=TransactionEvent.EventTypes.CHARGE_SUCCEEDED,
        )

        self.assertEqual(txn.plan, self.plan)
        self.assertEqual(txn.status, Transaction.Status.CHARGE_SUCCESS)
        self.assertEqual(txn.billing_cycle_number, 1)
        self.assertEqual(txn.charge_reference, "engine_ref_1")

    def test_creates_audit_event(self):
        txn = record_transaction(
            plan=self.plan,
            charge_reference="engine_ref_2",
            amount=self.plan.amount,
            cycle_number=2,
            status=Transaction.Status.CHARGE_SUCCESS,
            event_type=TransactionEvent.EventTypes.CHARGE_SUCCEEDED,
        )

        events = TransactionEvent.objects.filter(transaction=txn)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().event_type, TransactionEvent.EventTypes.CHARGE_SUCCEEDED)

    def test_updates_existing_transaction(self):
        record_transaction(
            plan=self.plan,
            charge_reference="engine_ref_3",
            amount=self.plan.amount,
            cycle_number=3,
            status=Transaction.Status.CHARGE_PENDING,
            event_type=TransactionEvent.EventTypes.CHARGE_INITIATED,
        )

        txn = record_transaction(
            plan=self.plan,
            charge_reference="engine_ref_3",
            amount=self.plan.amount,
            cycle_number=3,
            status=Transaction.Status.CHARGE_SUCCESS,
            event_type=TransactionEvent.EventTypes.CHARGE_SUCCEEDED,
        )

        self.assertEqual(txn.status, Transaction.Status.CHARGE_SUCCESS)
        events = TransactionEvent.objects.filter(transaction=txn)
        self.assertEqual(events.count(), 2)
