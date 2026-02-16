from django.apps import AppConfig

class BackupServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backup_service'
    verbose_name = 'Сервис резервного копирования'