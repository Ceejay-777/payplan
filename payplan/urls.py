from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

import django_eventstream

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path("events/", include(django_eventstream.urls), {"channels": ["test"]}),
    
    # API endpoints
    path('api/auth/',         include('core.urls')),
    path('api/plans/',        include('plans.urls')),
    path('api/transactions/', include('transactions.urls')),
    path('api/webhooks/',     include('webhooks.urls')),
    
    # Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
