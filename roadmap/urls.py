from django.urls import path
from . import views

app_name = "roadmap"

urlpatterns = [
    path("roadmap/generate/<int:project_id>/", views.generate_roadmap, name="generate"),
    path("roadmap/assistant/<int:project_id>/", views.assistant, name="assistant"),
]
