from django.urls import path
from .views import (
    ResolveBankView, CreateSelfFundedPlanView, ListPlansView, 
    RetrievePlanView, PausePlanView, ResumePlanView, PublicPlanLinkView,
    RequestCancellationView, ConfirmCancellationView
)

urlpatterns = [
    # path('banks', BankListView.as_view(), name='list-banks'),
    path('resolve-bank', ResolveBankView.as_view(), name='resolve-bank'),
    path('create', CreateSelfFundedPlanView.as_view(), name='create-funded-plan'),
    path('', ListPlansView.as_view(), name='list-plans'),
    path('<slug:sqid>', RetrievePlanView.as_view(), name='retrieve-plan'),
    path('<slug:sqid>/pause', PausePlanView.as_view(), name='pause-plan'),
    path('<slug:sqid>/resume', ResumePlanView.as_view(), name='resume-plan'),
    
    # Public link flow
    path('link/<str:payment_link_token>', PublicPlanLinkView.as_view(), name='plan-link-detail'),
    
    # Cancellation
    path('<slug:sqid>/request-cancellation', RequestCancellationView.as_view(), name='request-cancellation'),
    path('<slug:sqid>/confirm-cancellation', ConfirmCancellationView.as_view(), name='confirm-cancellation'),
]
