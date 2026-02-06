# attendance_student/views.py
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q
from api.models import Attendance, StudentProfile, DailySchedule, ScheduleLesson, Subject
from MPTed_base.decorators import student_required


def get_student_group_and_schedule(user):
    """Получает группу ученика и его расписание"""
    try:
        profile = StudentProfile.objects.get(user=user)
        group = profile.student_group
        return profile, group
    except StudentProfile.DoesNotExist:
        return None, None


def get_attendance_status_for_lesson(student, lesson, date):
    """Определяет статус посещаемости для урока"""
    try:
        attendance = Attendance.objects.get(
            student=student,
            schedule_lesson=lesson,
            date=date
        )
        if attendance.status == 'P':
            return 'present'  # Был, ничего не ставим (пустая строка)
        elif attendance.status == 'L':
            return 'late'  # Опоздал
        elif attendance.status == 'A':
            return 'absent'  # Не был
    except Attendance.DoesNotExist:
        # Если посещаемость не выставлена, считаем "не был"
        return 'absent'
    
    return 'absent'


@student_required
def attendance_dashboard(request):
    """Главная страница посещаемости - позавчера, вчера и сегодня"""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    day_before_yesterday = today - timedelta(days=2)
    
    days = [
        {'date': day_before_yesterday, 'name': 'Позавчера', 'is_today': False},
        {'date': yesterday, 'name': 'Вчера', 'is_today': False},
        {'date': today, 'name': 'Сегодня', 'is_today': True},
    ]
    
    # Получаем профиль и группу ученика
    student_profile, student_group = get_student_group_and_schedule(request.user)
    
    # Если ученик не в группе
    if not student_group:
        context = {
            'student_profile': student_profile,
            'has_group': False,
            'error_message': 'Вы не привязаны к учебной группе'
        }
        return render(request, 'attendance_student/attendance_dashboard.html', context)
    
    # Получаем день недели для каждой даты
    week_day_map = {
        0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 
        4: 'FRI', 5: 'SAT', 6: 'SUN'
    }
    
    attendance_data = []
    total_lessons = 0
    present_count = 0
    late_count = 0
    absent_count = 0
    
    for day_info in days:
        date = day_info['date']
        week_day = week_day_map[date.weekday()]
        
        # Получаем расписание на этот день
        try:
            schedule = DailySchedule.objects.get(
                student_group=student_group,
                week_day=week_day,
                is_active=True
            )
        except DailySchedule.DoesNotExist:
            schedule = None
        
        day_lessons = []
        day_stats = {
            'present': 0,
            'late': 0,
            'absent': 0,
            'total': 0
        }
        
        if schedule and not schedule.is_weekend:
            # Получаем уроки на этот день
            lessons = ScheduleLesson.objects.filter(
                daily_schedule=schedule
            ).order_by('lesson_number').select_related('subject', 'teacher')
            
            for lesson in lessons:
                # Определяем статус посещаемости
                status = get_attendance_status_for_lesson(request.user, lesson, date)
                
                # Формируем отображаемое значение
                display_value = ''
                if status == 'late':
                    display_value = 'О'
                elif status == 'absent':
                    display_value = 'НБ'
                # Если status == 'present' - оставляем пустую строку
                
                lesson_data = {
                    'id': lesson.id,
                    'lesson_number': lesson.lesson_number,
                    'subject': lesson.subject,
                    'teacher': lesson.teacher,
                    'time': f"{lesson.lesson_number * 45 + 480 // 60}:{(lesson.lesson_number * 45 + 480) % 60:02d}",
                    'status': status,
                    'display_value': display_value,
                    'has_attendance': status in ['present', 'late', 'absent']
                }
                day_lessons.append(lesson_data)
                
                # Считаем статистику
                if status == 'present':
                    day_stats['present'] += 1
                    present_count += 1
                elif status == 'late':
                    day_stats['late'] += 1
                    late_count += 1
                elif status == 'absent':
                    day_stats['absent'] += 1
                    absent_count += 1
                
                day_stats['total'] += 1
                total_lessons += 1
        
        # Рассчитываем процент посещаемости для дня
        if day_stats['total'] > 0:
            day_stats['attendance_rate'] = int((day_stats['present'] / day_stats['total']) * 100)
        else:
            day_stats['attendance_rate'] = 0
        
        attendance_data.append({
            'date': date,
            'name': day_info['name'],
            'is_today': day_info['is_today'],
            'week_day': week_day,
            'schedule': schedule,
            'lessons': day_lessons,
            'stats': day_stats,
            'is_weekend': schedule.is_weekend if schedule else False,
            'has_lessons': len(day_lessons) > 0
        })
    
    # Общая статистика
    if total_lessons > 0:
        overall_attendance_rate = int((present_count / total_lessons) * 100)
    else:
        overall_attendance_rate = 0
    
    context = {
        'attendance_data': attendance_data,
        'today': today,
        'total_lessons': total_lessons,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'overall_attendance_rate': overall_attendance_rate,
        'student_profile': student_profile,
        'student_group': student_group,
        'has_group': True,
    }
    
    return render(request, 'attendance_student/attendance_dashboard.html', context)


# attendance_student/views.py - оптимизированная версия
@student_required
def attendance_history(request):
    """История посещаемости по всем предметам - оптимизированная версия"""
    from django.db.models import Count, Q, Sum, Case, When, Value, IntegerField
    from django.db.models.functions import TruncMonth
    
    student_profile, student_group = get_student_group_and_schedule(request.user)
    
    if not student_group:
        context = {'student_profile': student_profile, 'has_group': False}
        return render(request, 'attendance_student/attendance_history.html', context)
    
    # Определяем период (последние 30 дней)
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    # Получаем все уникальные даты за период, когда были уроки
    dates_with_lessons = []
    
    # Проверяем каждый день
    current_date = thirty_days_ago
    while current_date <= today:
        week_day = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'][current_date.weekday()]
        
        # Есть ли расписание на этот день?
        if DailySchedule.objects.filter(
            student_group=student_group,
            week_day=week_day,
            is_active=True,
            is_weekend=False
        ).exists():
            dates_with_lessons.append(current_date)
        
        current_date += timedelta(days=1)
    
    # Получаем все предметы из расписания группы
    subjects = Subject.objects.filter(
        schedule_lessons__daily_schedule__student_group=student_group
    ).distinct()
    
    subjects_data = []
    
    # Для каждого предмета собираем статистику
    for subject in subjects:
        # Получаем ID всех уроков этого предмета
        lesson_ids = ScheduleLesson.objects.filter(
            subject=subject,
            daily_schedule__student_group=student_group
        ).values_list('id', flat=True)
        
        if not lesson_ids:
            continue
        
        # Считаем общее количество уроков за период
        total_lessons_count = 0
        
        for date in dates_with_lessons:
            # Находим день недели для этой даты
            week_day = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'][date.weekday()]
            
            # Получаем расписание на этот день
            try:
                schedule = DailySchedule.objects.get(
                    student_group=student_group,
                    week_day=week_day,
                    is_active=True,
                    is_weekend=False
                )
                
                # Считаем уроки этого предмета в этот день
                day_lessons_count = ScheduleLesson.objects.filter(
                    subject=subject,
                    daily_schedule=schedule
                ).count()
                
                total_lessons_count += day_lessons_count
                
            except DailySchedule.DoesNotExist:
                continue
        
        if total_lessons_count == 0:
            continue
        
        # Получаем статистику посещаемости по этому предмету
        attendances = Attendance.objects.filter(
            student=request.user,
            schedule_lesson__in=lesson_ids,
            date__range=[thirty_days_ago, today]
        )
        
        present_count = attendances.filter(status='P').count()
        late_count = attendances.filter(status='L').count()
        
        # Не был = всего уроков - (был + опоздал)
        absent_count = total_lessons_count - present_count - late_count
        
        attendance_rate = int((present_count / total_lessons_count) * 100) if total_lessons_count > 0 else 0
        
        subjects_data.append({
            'subject': subject,
            'total': total_lessons_count,
            'present': present_count,
            'late': late_count,
            'absent': absent_count,
            'attendance_rate': attendance_rate,
            'is_critical': attendance_rate < 80,
        })
    
    # Сортируем по проценту посещаемости
    subjects_data.sort(key=lambda x: x['attendance_rate'])
    
    # Общая статистика
    if subjects_data:
        total_all = sum(s['total'] for s in subjects_data)
        present_all = sum(s['present'] for s in subjects_data)
        late_all = sum(s['late'] for s in subjects_data)
        absent_all = sum(s['absent'] for s in subjects_data)
        overall_rate = int((present_all / total_all) * 100) if total_all > 0 else 0
    else:
        total_all = present_all = late_all = absent_all = overall_rate = 0
    
    context = {
        'subjects_data': subjects_data,
        'overall_rate': overall_rate,
        'total_all': total_all,
        'present_all': present_all,
        'late_all': late_all,
        'absent_all': absent_all,
        'student_profile': student_profile,
        'student_group': student_group,
        'has_group': True,
    }
    
    return render(request, 'attendance_student/attendance_history.html', context)