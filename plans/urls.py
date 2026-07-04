from django.urls import path
from .views import (
    ResolveBankView, CreateSelfFundedPlanView, ListUserPlansView, 
    RetrieveUserPlanView, PausePlanView, ResumePlanView,
    RequestCancellationView, ConfirmCancellationView, ResolveLinkFundedPayPlanView,
    CreateLinkFundedPayPlan
)

urlpatterns = [
    # path('banks', BankListView.as_view(), name='list-banks'),
    path('', ListUserPlansView.as_view(), name='list-plans'),
    path('resolve-bank', ResolveBankView.as_view(), name='resolve-bank'),
    
    path('self-funded/create', CreateSelfFundedPlanView.as_view(), name='create-funded-plan'),
    path('link-funded/create', CreateLinkFundedPayPlan.as_view(), name='create-link-plan'),
    path('link-funded/resolve', ResolveLinkFundedPayPlanView.as_view(), name='create-link-plan'),
    
    path('<slug:sqid>/request-cancellation', RequestCancellationView.as_view(), name='request-cancellation'),
    path('<slug:sqid>/confirm-cancellation', ConfirmCancellationView.as_view(), name='confirm-cancellation'),
    
    path('<slug:sqid>', RetrieveUserPlanView.as_view(), name='retrieve-plan'),
    path('<slug:sqid>/pause', PausePlanView.as_view(), name='pause-plan'),
    path('<slug:sqid>/resume', ResumePlanView.as_view(), name='resume-plan'),
]
