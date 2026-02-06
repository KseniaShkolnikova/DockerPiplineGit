# teacher_portal/urls.py
from django.urls import path
from . import views

app_name = 'teacher_portal'

urlpatterns = [
    # Главная
    path('', views.dashboard, name='dashboard'),
    
    # Управление оценками
    path('grades/', views.manage_grades, name='grades'),
    path('grades/add/', views.add_grade, name='add_grade'),
    path('grades/<int:grade_id>/edit/', views.edit_grade, name='edit_grade'),
    path('grades/<int:grade_id>/delete/', views.delete_grade, name='delete_grade'),
    
    # Посещаемость
    path('attendance/', views.manage_attendance, name='attendance'),
    path('attendance/save/', views.save_attendance, name='save_attendance'),
    
    # Домашние задания
    path('homework/', views.manage_homework, name='homework'),
    path('homework/create/', views.create_homework, name='create_homework'),
    path('homework/<int:homework_id>/submissions/', views.homework_submissions, name='homework_submissions'),
    path('submissions/<int:submission_id>/grade/', views.grade_submission, name='grade_submission'),
    path('homework/delete/<int:homework_id>/', views.delete_homework, name='delete_homework'),  
    path('homework/<int:homework_id>/edit/', views.edit_homework, name='edit_homework'), 
    # Расписание
    path('schedule/', views.view_schedule, name='schedule'),
    
    # Объявления
    path('announcements/', views.manage_announcements, name='announcements'),
    path('announcements/create/', views.create_announcement, name='create_announcement'),
    path('announcements/<int:announcement_id>/delete/', views.delete_announcement, name='delete_announcement'),
    path('announcements/<int:announcement_id>/edit/', views.edit_announcement, name='edit_announcement'),
    # Ученики
    path('students/', views.view_students, name='students'),
    path('students/<int:student_id>/', views.student_detail, name='student_detail'),
    
    # Статистика
    path('statistics/', views.view_statistics, name='statistics'),
]