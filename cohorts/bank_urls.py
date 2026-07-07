from django.urls import path
from .views import (
    BankAccountListCreateView, BankAccountDetailView,
    BankAccountUpdateView, BankAccountDeleteView,
    BankAccountResolveView,
)

urlpatterns = [
    path('', BankAccountListCreateView.as_view(), name='bank-account-list-create'),
    path('<slug:sqid>', BankAccountDetailView.as_view(), name='bank-account-detail'),
    path('<slug:sqid>/update', BankAccountUpdateView.as_view(), name='bank-account-update'),
    path('<slug:sqid>/delete', BankAccountDeleteView.as_view(), name='bank-account-delete'),
    path('<slug:sqid>/resolve', BankAccountResolveView.as_view(), name='bank-account-resolve'),
]
