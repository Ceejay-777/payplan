from django.urls import path
from .views import (
    CohortListCreateView, RetrieveCohortView,
    UpdateCohortView, DeleteCohortView,
    CohortPayerListCreateView, RemovePayerFromCohortView,
    CohortSummaryView, CohortTransactionsView,
    CohortBatchPauseView, CohortBatchResumeView, CohortBatchRetryView,
)

urlpatterns = [
    path('', CohortListCreateView.as_view(), name='cohort-list-create'),
    path('<slug:sqid>', RetrieveCohortView.as_view(), name='retrieve-cohort'),
    path('<slug:sqid>/update', UpdateCohortView.as_view(), name='update-cohort'),
    path('<slug:sqid>/delete', DeleteCohortView.as_view(), name='delete-cohort'),
    path('<slug:sqid>/payers', CohortPayerListCreateView.as_view(), name='cohort-payers'),
    path('<slug:sqid>/payers/<slug:plan_sqid>', RemovePayerFromCohortView.as_view(), name='remove-payer'),
    path('<slug:sqid>/summary', CohortSummaryView.as_view(), name='cohort-summary'),
    path('<slug:sqid>/transactions', CohortTransactionsView.as_view(), name='cohort-transactions'),
    path('<slug:sqid>/batch-pause', CohortBatchPauseView.as_view(), name='cohort-batch-pause'),
    path('<slug:sqid>/batch-resume', CohortBatchResumeView.as_view(), name='cohort-batch-resume'),
    path('<slug:sqid>/batch-retry', CohortBatchRetryView.as_view(), name='cohort-batch-retry'),
]
