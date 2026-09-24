from django.urls import path
from .views import AIAssistantQueryView, AIToolsCatalogView, AIDirectToolExecutionView

app_name = 'ai_assistant'

urlpatterns = [
    path('query/', AIAssistantQueryView.as_view(), name='query'),
    path('tools/', AIToolsCatalogView.as_view(), name='tools-catalog'),
    path('tools/execute/', AIDirectToolExecutionView.as_view(), name='tools-execute'),
]
