from django.urls import path
from . import views

app_name = 'education_department'

urlpatterns = [
    # Главная панель
    path('', views.department_dashboard, name='dashboard'),
    
    # Оценки по группам (ТОЧНО ТАКИЕ ЖЕ URL как были)
    path('grades/groups/', views.group_grades_overview, name='group_grades_overview'),
    path('grades/', views.group_grades_overview, name='group_grades_overview'),
    path('grades/group/<int:group_id>/', views.group_grades_detail, name='group_grades_detail'),
    path('grades/group/<int:group_id>/subject/<int:subject_id>/', 
         views.group_subject_grades, name='group_subject_grades'),
    
    # Обзор учителей (ТОЧНО ТАКИЕ ЖЕ URL как были)
    path('teachers/overview/', views.teachers_overview, name='teachers_overview'),
    path('teachers/<int:teacher_id>/full/', views.teacher_full_detail, name='teacher_full_detail'),
    path('teachers/<int:teacher_id>/subject/<int:subject_id>/performance/', 
         views.teacher_subject_performance, name='teacher_subject_performance'),
    path("homework/stats/", views.homework_stats, name="homework_stats"),
     # education_department/urls.py
     path("grades/report/pdf/", views.grades_school_report_pdf, name="grades_school_report_pdf"),

    # Заглушки для будущих функций
    path('teachers/', views.teachers_overview, name='teachers_overview'),
    path('teachers/<int:teacher_id>/admin/', views.teacher_full_detail_admin, name='teacher_full_detail_admin'),
    path('homework/', views.homework_overview, name='homework_overview'),
    path('schedule/', views.schedule_management, name='schedule_management'),
    path('teachers/<int:teacher_id>/', views.teacher_full_detail, name='teacher_full_detail'),
    path('teachers/<int:teacher_id>/subject/<int:subject_id>/performance/', 
         views.teacher_subject_performance, name='teacher_subject_performance'),
]