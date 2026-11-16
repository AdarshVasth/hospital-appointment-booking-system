from django.contrib import admin
from django.urls import path

from booking import views

urlpatterns = [
    path("", views.home),
    path("admin/", admin.site.urls),
    path("api/session/", views.session),
    path("api/auth/<str:action>/", views.auth),
    path("api/directory/", views.directory),
    path("api/availability/", views.availability),
    path("api/doctor/slots/", views.doctor_slots),
    path("api/doctor/slots/<int:pk>/", views.doctor_slot),
    path("api/appointments/", views.book),
    path("api/appointments/<int:pk>/cancel/", views.cancel),
    path("api/appointments/<int:pk>/complete/", views.complete),
    path("api/dashboard/", views.dashboard),
]
