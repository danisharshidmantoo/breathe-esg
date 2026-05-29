from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmissionRecordViewSet, UploadView, stats_view

router = DefaultRouter()
router.register(r'records', EmissionRecordViewSet, basename='records')

urlpatterns = [
    path('upload/', UploadView.as_view(), name='upload'),
    path('stats/', stats_view, name='stats'),
    path('', include(router.urls)),
]
