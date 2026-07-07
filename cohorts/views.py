from django.shortcuts import get_object_or_404

from rest_framework import generics, status, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from plans.models import PayPlan
from transactions.serializers import TransactionSerializer
from .models import Cohort, CohortMembership, SavedBankAccount
from .serializers import (
    CohortSerializer, CohortDetailSerializer, CreateCohortSerializer,
    UpdateCohortSerializer, AddPayersSerializer, CohortMembershipSerializer,
    CohortSummarySerializer, BatchActionSerializer, SavedBankAccountSerializer,
    CreateBankAccountSerializer, UpdateBankAccountSerializer, ResolveBankSerializer,
)
from .services import (
    create_cohort, add_payers_to_cohort, remove_payer_from_cohort,
    update_cohort, get_cohort_summary, get_cohort_transactions,
    batch_pause_plans, batch_resume_plans, batch_retry_plans,
)
from .bank_services import (
    save_bank_account, update_bank_account, delete_bank_account,
    resolve_bank_account as bank_resolve_service,
)


class BaseCohortAccessMixin:
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Cohort.objects.filter(organizer=self.request.user)


@extend_schema(tags=["Cohorts"])
class CohortListCreateView(BaseCohortAccessMixin, generics.GenericAPIView):
    serializer_class = CreateCohortSerializer

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CohortSerializer
        return CreateCohortSerializer

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = CohortSerializer(queryset, many=True)
        return Response({"data": serializer.data, "status": "success"})

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        payers = validated_data.pop('payers', None)

        cohort, payer_results = create_cohort(request.user, validated_data, payers=payers)

        response_data = CohortSerializer(cohort).data
        if payer_results:
            response_data['payers'] = [
                {
                    'plan_sqid': r['plan'].sqid,
                    'resolution_link': r['resolution_link'],
                }
                for r in payer_results
            ]

        return Response(
            {"data": response_data, "detail": "Cohort created successfully", "status": "success"},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Cohorts"])
class RetrieveCohortView(BaseCohortAccessMixin, generics.RetrieveAPIView):
    serializer_class = CohortDetailSerializer
    lookup_field = 'sqid'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"data": serializer.data, "status": "success"})


@extend_schema(tags=["Cohorts"])
class UpdateCohortView(BaseCohortAccessMixin, generics.UpdateAPIView):
    serializer_class = UpdateCohortSerializer
    lookup_field = 'sqid'
    http_method_names = ['put', 'patch']

    def perform_update(self, serializer):
        cohort = self.get_object()
        validated_data = serializer.validated_data
        update_cohort(cohort, validated_data)
        self.instance = cohort

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(
            {"data": CohortSerializer(self.instance).data, "detail": "Cohort updated successfully", "status": "success"},
        )


@extend_schema(tags=["Cohorts"])
class DeleteCohortView(BaseCohortAccessMixin, generics.DestroyAPIView):
    lookup_field = 'sqid'

    def perform_destroy(self, instance):
        instance.soft_delete()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Cohort deleted successfully", "status": "success"},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Cohorts"])
class CohortPayerListCreateView(BaseCohortAccessMixin, generics.GenericAPIView):
    serializer_class = AddPayersSerializer
    lookup_field = 'sqid'
    lookup_url_kwarg = 'sqid'

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CohortMembershipSerializer
        return AddPayersSerializer

    def get(self, request, sqid, *args, **kwargs):
        cohort = self.get_object()
        memberships = CohortMembership.objects.filter(cohort=cohort).select_related('plan__creator')
        serializer = CohortMembershipSerializer(memberships, many=True)
        return Response({"data": serializer.data, "status": "success"})

    def post(self, request, sqid, *args, **kwargs):
        cohort = self.get_object()
        serializer = AddPayersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payer_results = add_payers_to_cohort(cohort, serializer.validated_data['payers'])

        return Response(
            {
                "data": {
                    "payers": [
                        {
                            'plan_sqid': r['plan'].sqid,
                            'resolution_link': r['resolution_link'],
                        }
                        for r in payer_results
                    ]
                },
                "detail": f"{len(payer_results)} payer(s) added successfully",
                "status": "success",
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Cohorts"])
class RemovePayerFromCohortView(BaseCohortAccessMixin, generics.GenericAPIView):
    lookup_field = 'sqid'
    lookup_url_kwarg = 'sqid'

    def delete(self, request, sqid, plan_sqid, *args, **kwargs):
        cohort = self.get_object()
        plan = get_object_or_404(PayPlan, sqid=plan_sqid)
        remove_payer_from_cohort(cohort, plan)
        return Response(
            {"detail": "Payer removed from cohort", "status": "success"},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Cohorts"])
class CohortSummaryView(BaseCohortAccessMixin, generics.RetrieveAPIView):
    lookup_field = 'sqid'

    def retrieve(self, request, *args, **kwargs):
        cohort = self.get_object()
        summary = get_cohort_summary(cohort)
        serializer = CohortSummarySerializer(summary)
        return Response({"data": serializer.data, "status": "success"})


class CohortTransactionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema(tags=["Cohorts"])
class CohortTransactionsView(BaseCohortAccessMixin, generics.GenericAPIView):
    lookup_field = 'sqid'
    pagination_class = CohortTransactionPagination

    @extend_schema(
        parameters=[
            OpenApiParameter(name='start_date', type=OpenApiTypes.DATETIME, location=OpenApiParameter.QUERY, description='Filter transactions on or after this date (ISO 8601)'),
            OpenApiParameter(name='end_date', type=OpenApiTypes.DATETIME, location=OpenApiParameter.QUERY, description='Filter transactions on or before this date (ISO 8601)'),
        ]
    )
    def get(self, request, sqid, *args, **kwargs):
        cohort = self.get_object()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        transactions = get_cohort_transactions(cohort, start_date=start_date, end_date=end_date)
        page = self.paginate_queryset(transactions)
        if page is not None:
            serializer = TransactionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = TransactionSerializer(transactions, many=True)
        return Response({"data": serializer.data, "status": "success"})


class BaseBatchActionView(BaseCohortAccessMixin, generics.GenericAPIView):
    serializer_class = BatchActionSerializer
    lookup_field = 'sqid'
    action_func = None

    def post(self, request, sqid, *args, **kwargs):
        cohort = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = self.action_func(cohort, **serializer.validated_data)
        return Response({"data": result, "status": "success"})


@extend_schema(tags=["Cohorts"])
class CohortBatchPauseView(BaseBatchActionView):
    action_func = staticmethod(batch_pause_plans)


@extend_schema(tags=["Cohorts"])
class CohortBatchResumeView(BaseBatchActionView):
    action_func = staticmethod(batch_resume_plans)


@extend_schema(tags=["Cohorts"])
class CohortBatchRetryView(BaseBatchActionView):
    action_func = staticmethod(batch_retry_plans)


class BaseBankAccountAccessMixin:
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavedBankAccount.objects.filter(
            user=self.request.user,
            status=SavedBankAccount.Status.ACTIVE,
        )


@extend_schema(tags=["Bank Accounts"])
class BankAccountListCreateView(BaseBankAccountAccessMixin, generics.GenericAPIView):
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return SavedBankAccountSerializer
        return CreateBankAccountSerializer

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = SavedBankAccountSerializer(queryset, many=True)
        return Response({"data": serializer.data, "status": "success"})

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = save_bank_account(
            user=request.user,
            account_number=serializer.validated_data['account_number'],
            bank_code=serializer.validated_data['bank_code'],
            nickname=serializer.validated_data.get('nickname'),
            is_default=serializer.validated_data.get('is_default', False),
        )
        return Response(
            {"data": SavedBankAccountSerializer(account).data, "detail": "Bank account saved successfully", "status": "success"},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Bank Accounts"])
class BankAccountDetailView(BaseBankAccountAccessMixin, generics.RetrieveAPIView):
    serializer_class = SavedBankAccountSerializer
    lookup_field = 'sqid'


@extend_schema(tags=["Bank Accounts"])
class BankAccountUpdateView(BaseBankAccountAccessMixin, generics.UpdateAPIView):
    lookup_field = 'sqid'
    http_method_names = ['put', 'patch']

    def get_serializer_class(self):
        return UpdateBankAccountSerializer

    def perform_update(self, serializer):
        account = self.get_object()
        update_bank_account(account, serializer.validated_data)
        self.instance = account

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(
            {"data": SavedBankAccountSerializer(self.instance).data, "detail": "Bank account updated successfully", "status": "success"},
        )


@extend_schema(tags=["Bank Accounts"])
class BankAccountDeleteView(BaseBankAccountAccessMixin, generics.DestroyAPIView):
    lookup_field = 'sqid'

    def perform_destroy(self, instance):
        delete_bank_account(instance)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Bank account deleted successfully", "status": "success"},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Bank Accounts"])
class BankAccountResolveView(BaseBankAccountAccessMixin, generics.GenericAPIView):
    serializer_class = ResolveBankSerializer
    lookup_field = 'sqid'

    def post(self, request, *args, **kwargs):
        account = self.get_object()
        try:
            account_name = bank_resolve_service(account.account_number, account.bank_code)
            account.account_name = account_name
            account.save(update_fields=['account_name'])
            return Response({
                "data": SavedBankAccountSerializer(account).data,
                "detail": "Bank account resolved successfully",
                "status": "success",
            })
        except Exception as e:
            return Response(
                {"detail": f"Bank resolution failed: {e}", "status": "error"},
                status=status.HTTP_400_BAD_REQUEST,
            )
