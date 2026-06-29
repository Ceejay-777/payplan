from django.urls import path
from .views import (
    CreatePlanView, ListPlansView, RetrievePlanView, PausePlanView, 
    ResumePlanView, PublicPlanLinkView, AuthorizePlanView,
    RequestCancellationView, ConfirmCancellationView
)

urlpatterns = [
    path('', ListPlansView.as_view(), name='list-plans'),
    path('create', CreatePlanView.as_view(), name='create-plan'),
    path('<slug:sqid>', RetrievePlanView.as_view(), name='retrieve-plan'),
    path('<slug:sqid>/pause', PausePlanView.as_view(), name='pause-plan'),
    path('<slug:sqid>/resume', ResumePlanView.as_view(), name='resume-plan'),
    
    # Public link flow
    path('link/<str:payment_link_token>', PublicPlanLinkView.as_view(), name='plan-link-detail'),
    path('link/<str:token>/authorize', AuthorizePlanView.as_view(), name='authorize-plan'),
    
    # Cancellation
    path('<slug:sqid>/request-cancellation', RequestCancellationView.as_view(), name='request-cancellaton'),
    path('<slug:sqid>/confirm-cancellation', ConfirmCancellationView.as_view(), name='confirm-cancellation'),
]
