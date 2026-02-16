from django.db import models
from django.contrib.auth.models import User
import os

class DatabaseBackup(models.Model):
    """Модель для хранения информации о резервных копиях"""
    
    BACKUP_TYPES = [
        ('manual', 'Ручное'),
        ('auto', 'Автоматическое'),
        ('scheduled', 'По расписанию'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'В процессе'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
        ('restoring', 'Восстановление'),
    ]
    
    name = models.CharField('Название', max_length=255)
    filename = models.CharField('Имя файла', max_length=255, blank=True)
    file_path = models.CharField('Путь к файлу', max_length=500, blank=True)
    file_size = models.BigIntegerField('Размер файла (байт)', default=0)
    
    backup_type = models.CharField('Тип', max_length=20, choices=BACKUP_TYPES, default='manual')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Создал')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    completed_at = models.DateTimeField('Дата завершения', null=True, blank=True)
    
    description = models.TextField('Описание', blank=True)
    error_message = models.TextField('Ошибка', blank=True)
    
    # Информация о базе данных
    database_name = models.CharField('Имя БД', max_length=255, blank=True)
    tables_count = models.IntegerField('Количество таблиц', default=0)
    row_count = models.BigIntegerField('Всего записей', default=0)
    
    # Метаданные
    compression_ratio = models.FloatField('Степень сжатия', null=True, blank=True)
    md5_hash = models.CharField('MD5 хеш', max_length=32, blank=True)
    
    class Meta:
        verbose_name = 'Резервная копия'
        verbose_name_plural = 'Резервные копии'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    def delete(self, *args, **kwargs):
        """Удаляем файл при удалении записи"""
        if self.file_path and os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
            except:
                pass
        super().delete(*args, **kwargs)
    
    def get_file_size_display(self):
        """Форматирование размера файла"""
        size = self.file_size
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"


class BackupSchedule(models.Model):
    """Модель для расписания автоматических бэкапов"""
    
    FREQUENCY_CHOICES = [
        ('hourly', 'Каждый час'),
        ('daily', 'Ежедневно'),
        ('weekly', 'Еженедельно'),
        ('monthly', 'Ежемесячно'),
    ]
    
    DAYS_OF_WEEK = [
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    ]
    
    name = models.CharField('Название', max_length=255)
    is_active = models.BooleanField('Активно', default=True)
    
    frequency = models.CharField('Частота', max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    
    # Для ежедневных/еженедельных
    time = models.TimeField('Время', default='03:00')
    
    # Для еженедельных
    day_of_week = models.IntegerField('День недели', choices=DAYS_OF_WEEK, null=True, blank=True)
    
    # Для ежемесячных
    day_of_month = models.IntegerField('День месяца', null=True, blank=True,
                                       help_text='1-31, отрицательные значения с конца месяца')
    
    # Для почасовых
    interval_hours = models.IntegerField('Интервал (часы)', default=6,
                                         help_text='Для почасового режима')
    
    # Настройки
    keep_last = models.IntegerField('Хранить последних', default=10,
                                    help_text='Количество последних копий для хранения')
    compression = models.BooleanField('Сжимать', default=True)
    
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    last_run = models.DateTimeField('Последний запуск', null=True, blank=True)
    next_run = models.DateTimeField('Следующий запуск', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Расписание бэкапов'
        verbose_name_plural = 'Расписания бэкапов'
    
    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()}"
    
    def get_schedule_description(self):
        """Получить описание расписания"""
        if self.frequency == 'hourly':
            return f"Каждые {self.interval_hours} часов"
        elif self.frequency == 'daily':
            return f"Ежедневно в {self.time.strftime('%H:%M')}"
        elif self.frequency == 'weekly':
            day_name = dict(self.DAYS_OF_WEEK).get(self.day_of_week, '')
            return f"Еженедельно по {day_name} в {self.time.strftime('%H:%M')}"
        elif self.frequency == 'monthly':
            day = self.day_of_month if self.day_of_month else 1
            return f"Ежемесячно {day}-го числа в {self.time.strftime('%H:%M')}"
        return "Не задано"


class BackupLog(models.Model):
    """Логи операций с бэкапами"""
    
    ACTION_CHOICES = [
        ('create', 'Создание'),
        ('restore', 'Восстановление'),
        ('delete', 'Удаление'),
        ('download', 'Скачивание'),
    ]
    
    backup = models.ForeignKey(DatabaseBackup, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField('Действие', max_length=20, choices=ACTION_CHOICES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField('Время', auto_now_add=True)
    details = models.TextField('Детали', blank=True)
    ip_address = models.GenericIPAddressField('IP адрес', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Лог бэкапа'
        verbose_name_plural = 'Логи бэкапов'
        ordering = ['-timestamp']