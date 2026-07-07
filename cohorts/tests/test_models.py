from django.test import TestCase
from django.db import IntegrityError

from plans.factories import PayPlanFactory, UserFactory
from plans.models import PayPlan
from cohorts.models import Cohort, CohortMembership, SavedBankAccount


class TestCohortModel(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_creates_cohort(self):
        cohort = Cohort.objects.create(
            name="Rent Collection",
            organizer=self.user,
            frequency=Cohort.Frequency.MONTHLY,
            interval_count=1,
            start_date="2026-01-01T00:00:00Z",
            receiver_account_name="John Doe",
            receiver_account_number="1234567890",
            receiver_bank_code="011",
        )
        self.assertEqual(cohort.name, "Rent Collection")
        self.assertEqual(cohort.organizer, self.user)
        self.assertEqual(cohort.frequency, Cohort.Frequency.MONTHLY)
        self.assertEqual(cohort.proration_mode, Cohort.ProrationMode.PRO_RATED)
        self.assertEqual(cohort.visibility, Cohort.Visibility.CLOSED)

    def test_cohort_has_no_status_field(self):
        self.assertFalse(hasattr(Cohort, 'status'))


class TestCohortMembershipModel(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(creator=self.user)
        self.cohort = Cohort.objects.create(
            name="Test Cohort",
            organizer=self.user,
            frequency=Cohort.Frequency.MONTHLY,
            interval_count=1,
            start_date="2026-01-01T00:00:00Z",
            receiver_account_name="John Doe",
            receiver_account_number="1234567890",
            receiver_bank_code="011",
        )

    def test_creates_membership(self):
        membership = CohortMembership.objects.create(
            cohort=self.cohort,
            plan=self.plan,
            amount=100.00,
        )
        self.assertEqual(membership.cohort, self.cohort)
        self.assertEqual(membership.plan, self.plan)
        self.assertEqual(membership.amount, 100.00)
        self.assertEqual(membership.status, CohortMembership.Status.INVITED)

    def test_membership_has_no_user_field(self):
        self.assertFalse(hasattr(CohortMembership, 'user'))

    def test_user_accessible_via_plan_creator(self):
        membership = CohortMembership.objects.create(
            cohort=self.cohort,
            plan=self.plan,
            amount=100.00,
        )
        self.assertEqual(membership.plan.creator, self.user)

    def test_plan_one_to_one_unique(self):
        CohortMembership.objects.create(
            cohort=self.cohort, plan=self.plan, amount=100.00,
        )
        with self.assertRaises(IntegrityError):
            CohortMembership.objects.create(
                cohort=self.cohort, plan=self.plan, amount=200.00,
            )


class TestSavedBankAccountModel(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_creates_saved_bank_account(self):
        account = SavedBankAccount.objects.create(
            user=self.user,
            account_name="John Doe",
            account_number="1234567890",
            bank_code="011",
            bank_name="First Bank",
        )
        self.assertEqual(account.account_name, "John Doe")
        self.assertEqual(account.status, SavedBankAccount.Status.ACTIVE)
        self.assertFalse(account.is_default)

    def test_unique_user_account_bank_constraint(self):
        SavedBankAccount.objects.create(
            user=self.user,
            account_name="John Doe",
            account_number="1234567890",
            bank_code="011",
            bank_name="First Bank",
        )
        with self.assertRaises(IntegrityError):
            SavedBankAccount.objects.create(
                user=self.user,
                account_name="John Doe",
                account_number="1234567890",
                bank_code="011",
                bank_name="First Bank",
            )


class TestCohortRelationships(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(creator=self.user)
        self.cohort = Cohort.objects.create(
            name="Test Cohort",
            organizer=self.user,
            frequency=Cohort.Frequency.MONTHLY,
            interval_count=1,
            start_date="2026-01-01T00:00:00Z",
            receiver_account_name="John Doe",
            receiver_account_number="1234567890",
            receiver_bank_code="011",
        )

    def test_cohort_has_memberships(self):
        membership = CohortMembership.objects.create(
            cohort=self.cohort, plan=self.plan, amount=100.00,
        )
        self.assertIn(membership, self.cohort.memberships.all())

    def test_plan_has_cohort_membership(self):
        membership = CohortMembership.objects.create(
            cohort=self.cohort, plan=self.plan, amount=100.00,
        )
        plan = PayPlan.objects.get(pk=self.plan.pk)
        self.assertEqual(plan.cohort_membership, membership)

    def test_cascade_delete_cohort_removes_memberships(self):
        CohortMembership.objects.create(
            cohort=self.cohort, plan=self.plan, amount=100.00,
        )
        self.cohort.delete()
        self.assertEqual(CohortMembership.objects.count(), 0)
