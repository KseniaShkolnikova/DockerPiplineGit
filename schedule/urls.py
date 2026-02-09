from django.urls import path
from . import views

app_name = 'schedule'

urlpatterns = [
    path('', views.schedule_dashboard, name='schedule_dashboard'),
    path('toggle-weekend/', views.toggle_weekend_day, name='toggle_weekend_day'),
    path('add-lesson/', views.add_lesson, name='add_lesson'),
    path('lesson/<int:lesson_id>/delete/', views.delete_lesson, name='delete_lesson'),
    path('lesson/<int:lesson_id>/update/', views.update_lesson, name='update_lesson'),
    path('subject/<int:subject_id>/teachers/', views.get_subject_teachers, name='get_subject_teachers'),
]