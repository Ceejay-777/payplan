from django.urls import path
from .views import TransactionListView, TransactionDetailView

urlpatterns = [
    path('', TransactionListView.as_view(), name='list-transactions'),
    path('<slug:sqid>', TransactionDetailView.as_view(), name='retrieve-transaction'),
]
