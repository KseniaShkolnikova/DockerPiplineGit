from django.urls import path
from . import views

app_name = 'backup_service'

urlpatterns = [
    # Резервные копии
    path('', views.backup_list, name='backup_list'),
    path('create/', views.backup_create, name='backup_create'),
    path('<int:backup_id>/', views.backup_detail, name='backup_detail'),
    path('<int:backup_id>/download/', views.backup_download, name='backup_download'),
    path('<int:backup_id>/restore/', views.backup_restore, name='backup_restore'),
    path('<int:backup_id>/delete/', views.backup_delete, name='backup_delete'),
    
    # Расписания
    path('schedules/', views.schedule_list, name='schedule_list'),
    path('schedules/create/', views.schedule_create, name='schedule_create'),
    path('schedules/<int:schedule_id>/edit/', views.schedule_edit, name='schedule_edit'),
    path('schedules/<int:schedule_id>/delete/', views.schedule_delete, name='schedule_delete'),
    path('schedules/<int:schedule_id>/toggle/', views.schedule_toggle, name='schedule_toggle'),
]