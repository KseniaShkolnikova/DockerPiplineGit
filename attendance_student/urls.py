# attendance_student/urls.py
from django.urls import path
from . import views

app_name = 'attendance_student'

urlpatterns = [
    path('', views.attendance_dashboard, name='student_attendance'),
    path('history/', views.attendance_history, name='attendance_history'),
]