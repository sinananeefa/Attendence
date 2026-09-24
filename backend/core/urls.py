from django.contrib import admin
from django.urls import path, include
from .views import health_check, system_overview

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health_check'),
    path('api/system/overview/', system_overview, name='system_overview'),
    path('api/auth/', include('accounts.urls')),
    path('api/academic/', include('academic.urls')),
    path('api/attendance/', include('attendance.urls')),
    path('api/ai/', include('ai_assistant.urls')),
]
