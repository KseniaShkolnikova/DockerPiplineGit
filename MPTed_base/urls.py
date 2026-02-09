from django.urls import path
from . import views

urlpatterns = [
    # Страницы
    path('', views.login_page, name='login_page'),
    path('login/', views.login, name='login'),
    path('dashboard/', views.dashboard_page, name='dashboard_page'),
    path('admin-dashboard/', views.admin_dashboard_page, name='admin_dashboard_page'), 
    path('logout/', views.logout_view, name='logout_view'),
    
    # Управление классами
    path('admin-dashboard/groups/', views.groups_list, name='groups_list'),
    path('admin-dashboard/groups/create/', views.group_create, name='group_create'),
    path('admin-dashboard/groups/<int:group_id>/edit/', views.group_edit, name='group_edit'),
    path('admin-dashboard/groups/<int:group_id>/delete/', views.group_delete, name='group_delete'),
    path('admin-dashboard/groups/<int:group_id>/students/', views.group_students, name='group_students'),
    # Управление предметами
    path('admin-dashboard/subjects/', views.subjects_list, name='subjects_list'),
    path('admin-dashboard/subjects/create/', views.subject_create, name='subject_create'),
    path('admin-dashboard/subjects/<int:subject_id>/edit/', views.subject_edit, name='subject_edit'),
    path('admin-dashboard/subjects/<int:subject_id>/delete/', views.subject_delete, name='subject_delete'),

    path('teachers/', views.teachers_list, name='teachers_list'),
    path('teachers/new/', views.teacher_create, name='teacher_create'),
    path('teachers/<int:teacher_id>/', views.teacher_detail, name='teacher_detail'),
    path('teachers/<int:teacher_id>/edit/', views.teacher_edit, name='teacher_edit'),
    path('teachers/<int:teacher_id>/subjects/', views.teacher_subjects, name='teacher_subjects'),
    path('teachers/<int:teacher_id>/toggle-active/', views.teacher_toggle_active, name='teacher_toggle_active'),
    path('teachers/<int:teacher_id>/delete/', views.teacher_delete, name='teacher_delete'),

    path('admin-dashboard/students/', views.students_list, name='students_list'),
    path('admin-dashboard/students/create/', views.student_create, name='student_create'),
    path('admin-dashboard/students/<int:student_id>/', views.student_detail, name='student_detail'),
    path('admin-dashboard/students/<int:student_id>/edit/', views.student_edit, name='student_edit'),
    path('admin-dashboard/students/<int:student_id>/toggle-active/', views.student_toggle_active, name='student_toggle_active'),
    path('admin-dashboard/students/<int:student_id>/delete/', views.student_delete, name='student_delete'),

    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/schedule/', views.student_schedule, name='student_schedule'),
    path('student/grades/', views.student_grades, name='student_grades'),
    path('student/homework/', views.student_homework, name='student_homework'),
    path('student/attendance/', views.student_attendance, name='student_attendance'),
    path('student/profile/', views.student_profile_view, name='student_profile'),
    path('student/announcements/', views.student_announcements, name='student_announcements'),
    path('student/homework/submit/', views.submit_homework, name='submit_homework'),
    path('student/homework/<int:homework_id>/', views.homework_detail, name='homework_detail'),
    path('student/submission/<int:submission_id>/delete/', views.delete_submission, name='delete_submission'),
    path('student/profile/', views.student_profile_view, name='student_profile'),
    path('student/profile/change-password/', views.change_password, name='change_password'),

    path('admin-dashboard/audit-logs/', views.audit_logs, name='audit_logs'),
    path('admin-dashboard/audit-logs/<int:log_id>/', views.audit_log_detail, name='audit_log_detail'),
    path('admin-dashboard/audit-logs/clear/', views.clear_audit_logs, name='clear_audit_logs'),
    path('homework/<int:homework_id>/view_file/', 
         views.view_homework_file, 
         name='view_homework_file'),
    
    path('submissions/<int:submission_id>/view_file/', 
         views.view_submission_file, 
         name='view_submission_file'),
 
]