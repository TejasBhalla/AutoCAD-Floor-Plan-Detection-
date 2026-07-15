from django.urls import path
from .views import UploadFloorPlanView, SaveLayoutView, LoadLayoutView

urlpatterns = [
    path('upload-floorplan/', UploadFloorPlanView.as_view(), name='upload-floorplan'),
    path('save-layout/', SaveLayoutView.as_view(), name='save-layout'),
    path('load-layout/', LoadLayoutView.as_view(), name='load-layout'),
]
