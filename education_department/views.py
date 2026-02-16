from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum, Max, Min
from django.core.paginator import Paginator
from django.db.models.functions import TruncMonth, TruncYear  # Добавить эту строку!
from django.utils import timezone
from datetime import datetime, date, timedelta
import json
import calendar
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Avg, Count, Q
from api.models import StudentGroup, StudentProfile, Grade, Subject


# Импортируем ВСЕ существующие модели из api
from api.models import *
from django.contrib.auth.models import User, Group
from django.http import JsonResponse
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

# Декораторы (скопируем из вашего декораторов.py)
from MPTed_base.decorators import *


# ===== ФУНКЦИИ ОЦЕНОК ПО ГРУППАМ (КОПИРУЕМ ИЗ ВАШЕГО ФАЙЛА) =====

@login_required
@education_department_required
def group_grades_overview(request):
    """Обзор оценок по группам (ТОЧНАЯ КОПИЯ ВАШЕЙ ФУНКЦИИ)"""
    # Получаем все группы
    groups = StudentGroup.objects.all().select_related('curator').order_by('year', 'name')
    
    # Статистика по группам
    groups_stats = []
    for group in groups:
        # Количество учеников в группе
        student_count = StudentProfile.objects.filter(student_group=group).count()
        
        # Средняя оценка по группе
        avg_grade_result = Grade.objects.filter(
            student__student_profile__student_group=group
        ).aggregate(avg=Avg('value'))
        avg_grade = round(avg_grade_result['avg'], 1) if avg_grade_result['avg'] else 0
        
        # Количество оценок
        grades_count = Grade.objects.filter(
            student__student_profile__student_group=group
        ).count()
        
        groups_stats.append({
            'group': group,
            'student_count': student_count,
            'avg_grade': avg_grade,
            'grades_count': grades_count,
        })
    
    context = {
        'groups_stats': groups_stats,
    }
    # Итоги (правильные, без шаблонных костылей)
    total_students = sum(s['student_count'] for s in groups_stats)
    total_grades = sum(s['grades_count'] for s in groups_stats)

    # Сколько групп без куратора
    groups_without_curator = sum(1 for s in groups_stats if not s['group'].curator)

    # Средний балл по всем оценкам (не среднее из средних!)
    overall_avg_result = Grade.objects.aggregate(avg=Avg('value'))
    overall_avg = round(overall_avg_result['avg'], 1) if overall_avg_result['avg'] else 0

    context = {
        'groups_stats': groups_stats,
        'total_students': total_students,
        'total_grades': total_grades,
        'groups_without_curator': groups_without_curator,
        'overall_avg': overall_avg,
    }
    return render(request, 'education_department/group_grades_overview.html', context)

    


@login_required
@education_department_required
def group_grades_detail(request, group_id):
    """Детальная статистика оценок по группе (ТОЧНАЯ КОПИЯ ВАШЕЙ ФУНКЦИИ)"""
    group = get_object_or_404(StudentGroup, id=group_id)
    
    # Получаем предметы, которые есть у группы в расписании
    subjects_in_schedule = Subject.objects.filter(
        schedule_lessons__daily_schedule__student_group=group
    ).distinct().order_by('name')
    
    # Получаем всех учеников группы
    students = StudentProfile.objects.filter(
        student_group=group
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    # Статистика по предметам
    subjects_stats = []
    for subject in subjects_in_schedule:
        # Учителя, которые ведут этот предмет в этой группе
        teachers = User.objects.filter(
            schedule_lessons__daily_schedule__student_group=group,
            schedule_lessons__subject=subject
        ).distinct()
        
        # Оценки по этому предмету в группе
        grades = Grade.objects.filter(
            student__student_profile__student_group=group,
            subject=subject
        )
        
        # Средняя оценка по предмету
        avg_result = grades.aggregate(avg=Avg('value'))
        avg_grade = round(avg_result['avg'], 1) if avg_result['avg'] else 0
        
        # Количество оценок
        grades_count = grades.count()
        
        # Распределение оценок
        grade_distribution = {}
        for value in [5, 4, 3, 2]:
            count = grades.filter(value=value).count()
            if count > 0:
                grade_distribution[value] = count
        
        subjects_stats.append({
            'subject': subject,
            'teachers': teachers,
            'avg_grade': avg_grade,
            'grades_count': grades_count,
            'grade_distribution': grade_distribution,
        })
    
    # Общая статистика по группе
    all_grades = Grade.objects.filter(
        student__student_profile__student_group=group
    )
    
    total_grades = all_grades.count()
    overall_avg_result = all_grades.aggregate(avg=Avg('value'))
    overall_avg = round(overall_avg_result['avg'], 1) if overall_avg_result['avg'] else 0
    
    # Статистика по типам оценок
    grade_types_stats = []
    for grade_type_code, grade_type_name in Grade.GradeType.choices:
        count = all_grades.filter(grade_type=grade_type_code).count()
        if count > 0:
            avg_result = all_grades.filter(grade_type=grade_type_code).aggregate(avg=Avg('value'))
            avg = round(avg_result['avg'], 1) if avg_result['avg'] else 0
            grade_types_stats.append({
                'type': grade_type_code,
                'name': grade_type_name,
                'count': count,
                'avg': avg,
            })
    
    # Последние оценки в группе
    recent_grades = all_grades.select_related(
        'student', 'subject', 'teacher'
    ).order_by('-date')[:10]
    
    context = {
        'group': group,
        'students': students,
        'subjects_stats': subjects_stats,
        'total_grades': total_grades,
        'overall_avg': overall_avg,
        'grade_types_stats': grade_types_stats,
        'recent_grades': recent_grades,
        'student_count': students.count(),
    }
    return render(request, 'education_department/group_grades_detail.html', context)


@login_required
@education_department_required
def group_subject_grades(request, group_id, subject_id):
    """Оценки по конкретному предмету в группе (ТОЧНАЯ КОПИЯ ВАШЕЙ ФУНКЦИИ)"""
    group = get_object_or_404(StudentGroup, id=group_id)
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Проверяем, есть ли этот предмет в расписании группы
    if not ScheduleLesson.objects.filter(
        daily_schedule__student_group=group,
        subject=subject
    ).exists():
        messages.error(request, f'Предмет "{subject.name}" не входит в расписание группы {group.name}')
        return redirect('education_department:group_grades_detail', group_id=group_id)
    
    # Получаем всех учеников группы
    students = StudentProfile.objects.filter(
        student_group=group
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    # Получаем учителей, которые ведут этот предмет в группе
    teachers = User.objects.filter(
        schedule_lessons__daily_schedule__student_group=group,
        schedule_lessons__subject=subject
    ).distinct()
    
    # Собираем оценки по ученикам
    students_grades = []
    for student_profile in students:
        grades = Grade.objects.filter(
            student=student_profile.user,
            subject=subject
        ).order_by('-date')
        
        # Средняя оценка ученика по предмету
        avg_result = grades.aggregate(avg=Avg('value'))
        avg_grade = round(avg_result['avg'], 1) if avg_result['avg'] else 0
        
        # Количество оценок
        grades_count = grades.count()
        
        # Последние 5 оценок
        recent_grades = grades[:5]
        
        students_grades.append({
            'student': student_profile,
            'grades': grades,
            'avg_grade': avg_grade,
            'grades_count': grades_count,
            'recent_grades': recent_grades,
        })
    
    # Общая статистика по предмету в группе
    all_grades = Grade.objects.filter(
        student__student_profile__student_group=group,
        subject=subject
    )
    
    total_grades = all_grades.count()
    overall_avg_result = all_grades.aggregate(avg=Avg('value'))
    overall_avg = round(overall_avg_result['avg'], 1) if overall_avg_result['avg'] else 0
    
    # Распределение оценок
    grade_distribution = {}
    for value in [5, 4, 3, 2]:
        count = all_grades.filter(value=value).count()
        percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
        if count > 0:
            grade_distribution[value] = {
                'count': count,
                'percentage': percentage
            }
    
    # Статистика по типам оценок для этого предмета
    grade_types_stats = []
    for grade_type_code, grade_type_name in Grade.GradeType.choices:
        count = all_grades.filter(grade_type=grade_type_code).count()
        if count > 0:
            avg_result = all_grades.filter(grade_type=grade_type_code).aggregate(avg=Avg('value'))
            avg = round(avg_result['avg'], 1) if avg_result['avg'] else 0
            percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
            grade_types_stats.append({
                'type': grade_type_code,
                'name': grade_type_name,
                'count': count,
                'avg': avg,
                'percentage': percentage,
            })
    
    context = {
        'group': group,
        'subject': subject,
        'teachers': teachers,
        'students_grades': students_grades,
        'total_grades': total_grades,
        'overall_avg': overall_avg,
        'grade_distribution': grade_distribution,
        'grade_types_stats': grade_types_stats,
    }
    return render(request, 'education_department/group_subject_grades.html', context)


# ===== ФУНКЦИИ ОБЗОРА УЧИТЕЛЕЙ (КОПИРУЕМ ИЗ ВАШЕГО ФАЙЛА) =====

@login_required
@education_department_required
def teacher_subject_performance(request, teacher_id, subject_id):
    """Производительность учителя по конкретному предмету (аналог вашей функции)"""
    user = get_object_or_404(User, id=teacher_id)
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Проверяем, что учитель преподает этот предмет
    if not TeacherSubject.objects.filter(
        teacher__user=user,
        subject=subject
    ).exists():
        messages.error(request, f'Учитель не преподает предмет "{subject.name}"')
        return redirect('education_department:teacher_full_detail', teacher_id=teacher_id)
    
    # Группы, в которых учитель ведет этот предмет
    teaching_groups = StudentGroup.objects.filter(
        daily_schedules__lessons__teacher=user,
        daily_schedules__lessons__subject=subject
    ).distinct().order_by('year', 'name')
    
    # Оценки учителя по этому предмету
    grades = Grade.objects.filter(
        teacher=user,
        subject=subject
    ).select_related('student', 'schedule_lesson__daily_schedule__student_group')
    
    total_grades = grades.count()
    avg_grade_result = grades.aggregate(avg=Avg('value'))
    avg_grade = round(avg_grade_result['avg'], 1) if avg_grade_result['avg'] else 0
    
    # Статистика по месяцам
    import calendar
    from django.db.models.functions import TruncMonth
    
    monthly_stats = []
    monthly_data = grades.annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        count=Count('id'),
        avg=Avg('value')
    ).order_by('-month')[:12]  # Последние 12 месяцев
    
    for stat in monthly_data:
        monthly_stats.append({
            'month': stat['month'].strftime('%Y-%m'),
            'month_name': calendar.month_name[stat['month'].month],
            'year': stat['month'].year,
            'count': stat['count'],
            'avg': round(stat['avg'], 1) if stat['avg'] else 0,
        })
    
    # Статистика по группам
    group_stats = []
    for group in teaching_groups:
        group_grades = grades.filter(
            schedule_lesson__daily_schedule__student_group=group
        )
        group_total = group_grades.count()
        
        if group_total > 0:
            group_avg_result = group_grades.aggregate(avg=Avg('value'))
            group_avg = round(group_avg_result['avg'], 1) if group_avg_result['avg'] else 0
            
            group_stats.append({
                'group': group,
                'total': group_total,
                'avg': group_avg,
            })
    
    # Распределение оценок
    grade_distribution = {}
    for value in [5, 4, 3, 2]:
        count = grades.filter(value=value).count()
        if count > 0:
            percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
            grade_distribution[value] = {
                'count': count,
                'percentage': percentage
            }
    
    # Последние оценки
    recent_grades = grades.order_by('-date')[:20]
    
    context = {
        'teacher_user': user,
        'subject': subject,
        'teaching_groups': teaching_groups,
        'total_grades': total_grades,
        'avg_grade': avg_grade,
        'monthly_stats': monthly_stats,
        'group_stats': group_stats,
        'grade_distribution': grade_distribution,
        'recent_grades': recent_grades,
    }
    return render(request, 'education_department/teachers/teacher_subject_performance.html', context)

@login_required
@education_department_required
def teacher_full_detail(request, teacher_id):
    """Полная детальная информация об учителе (аналог вашей функции)"""
    user = get_object_or_404(User, id=teacher_id)
    
    # Проверяем, что это учитель
    if not user.groups.filter(name='teacher').exists() and not hasattr(user, 'teacher_profile'):
        messages.error(request, 'Пользователь не является учителем')
        return redirect('education_department:teachers_overview')
    
    try:
        profile = user.teacher_profile
    except TeacherProfile.DoesNotExist:
        profile = None
        messages.warning(request, 'У учителя нет профиля')
    
    # Предметы учителя
    teacher_subjects = TeacherSubject.objects.filter(
        teacher__user=user
    ).select_related('subject')
    
    # Группы, в которых преподает учитель
    teaching_groups = StudentGroup.objects.filter(
        daily_schedules__lessons__teacher=user
    ).distinct().order_by('year', 'name')
    
    # Детальное расписание учителя
    schedule_by_day = {}
    schedule_lessons = ScheduleLesson.objects.filter(
        teacher=user
    ).select_related(
        'daily_schedule', 'subject', 'daily_schedule__student_group'
    ).order_by('daily_schedule__week_day', 'lesson_number')
    
    for lesson in schedule_lessons:
        day = lesson.daily_schedule.get_week_day_display()
        day_code = lesson.daily_schedule.week_day
        
        if day_code not in schedule_by_day:
            schedule_by_day[day_code] = {
                'day_name': day,
                'lessons': []
            }
        schedule_by_day[day_code]['lessons'].append(lesson)
    
    # Статистика оценок
    grades_stats = Grade.objects.filter(
        teacher=user
    )
    
    total_grades = grades_stats.count()
    avg_grade_result = grades_stats.aggregate(avg=Avg('value'))
    avg_grade = round(avg_grade_result['avg'], 1) if avg_grade_result['avg'] else 0
    
    # Статистика по предметам
    grades_by_subject = []
    for ts in teacher_subjects:
        subject_grades = Grade.objects.filter(
            teacher=user,
            subject=ts.subject
        )
        
        subject_stats = subject_grades.aggregate(
            total=Count('id'),
            avg=Avg('value'),
            first_date=Min('date'),
            last_date=Max('date')
        )
        
        # Распределение оценок по предмету
        grade_distribution = {}
        for value in [5, 4, 3, 2]:
            count = subject_grades.filter(value=value).count()
            if count > 0:
                percentage = round((count / subject_stats['total'] * 100), 1) if subject_stats['total'] > 0 else 0
                grade_distribution[value] = {
                    'count': count,
                    'percentage': percentage
                }
        
        grades_by_subject.append({
            'subject': ts.subject,
            'total': subject_stats['total'] or 0,
            'avg': round(subject_stats['avg'], 1) if subject_stats['avg'] else 0,
            'first_date': subject_stats['first_date'],
            'last_date': subject_stats['last_date'],
            'grade_distribution': grade_distribution,
        })
    
    # Статистика по типам оценок
    grades_by_type = []
    for grade_type_code, grade_type_name in Grade.GradeType.choices:
        type_grades = grades_stats.filter(grade_type=grade_type_code)
        count = type_grades.count()
        if count > 0:
            avg_result = type_grades.aggregate(avg=Avg('value'))
            avg = round(avg_result['avg'], 1) if avg_result['avg'] else 0
            percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
            
            grades_by_type.append({
                'type': grade_type_code,
                'name': grade_type_name,
                'count': count,
                'avg': avg,
                'percentage': percentage,
            })
    
    # Последние выставленные оценки
    recent_grades = grades_stats.select_related(
        'student', 'subject'
    ).order_by('-date')[:10]
    
    # Ученики, у которых учитель преподает
    students_taught = User.objects.filter(
        grades__teacher=user
    ).distinct().count()
    
    context = {
        'teacher_user': user,
        'profile': profile,
        'teacher_subjects': teacher_subjects,
        'teaching_groups': teaching_groups,
        'schedule_by_day': schedule_by_day,
        'total_grades': total_grades,
        'avg_grade': avg_grade,
        'grades_by_subject': grades_by_subject,
        'grades_by_type': grades_by_type,
        'recent_grades': recent_grades,
        'students_taught': students_taught,
        'lesson_count': schedule_lessons.count(),
        'subject_count': teacher_subjects.count(),
        'group_count': teaching_groups.count(),
    }
    return render(request, 'education_department/teacher_full_detail.html', context)


@login_required
@education_department_required
def teachers_overview(request):
    """Обзорная страница учителей с подробной информацией (ТОЧНАЯ КОПИЯ ВАШЕЙ ФУНКЦИИ)"""
    # Получаем всех учителей
    teachers_qs = User.objects.filter(
        Q(groups__name='teacher') | Q(teacher_profile__isnull=False)
    ).distinct().order_by('last_name', 'first_name')
    
    # Фильтры
    search_query = request.GET.get('search', '').strip()
    if search_query:
        teachers_qs = teachers_qs.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(teacher_profile__patronymic__icontains=search_query)
        ).distinct()
    
    # Подготавливаем детальную информацию об учителях
    teachers_info = []
    for user in teachers_qs:
        try:
            profile = user.teacher_profile
            patronymic = profile.patronymic
            phone = profile.phone
            qualification = profile.qualification
            birth_date = profile.birth_date
        except TeacherProfile.DoesNotExist:
            patronymic = ''
            phone = ''
            qualification = ''
            birth_date = None
        
        # Получаем предметы учителя
        subjects = TeacherSubject.objects.filter(
            teacher__user=user
        ).select_related('subject')
        
        # Группы, в которых преподает учитель
        teaching_groups = StudentGroup.objects.filter(
            daily_schedules__lessons__teacher=user
        ).distinct().order_by('year', 'name')
        
        # Расписание учителя
        schedule_lessons = ScheduleLesson.objects.filter(
            teacher=user
        ).select_related(
            'daily_schedule', 'subject', 'daily_schedule__student_group'
        ).order_by('daily_schedule__week_day', 'lesson_number')
        
        # Статистика по оценкам
        grades_stats = Grade.objects.filter(
            teacher=user
        ).aggregate(
            total=Count('id'),
            avg=Avg('value'),
            latest=Max('date')
        )
        
        # Количество учеников у учителя (через оценки)
        unique_students = Grade.objects.filter(
            teacher=user
        ).values('student').distinct().count()
        
        teachers_info.append({
            'id': user.id,
            'user': user,
            'profile': profile if hasattr(user, 'teacher_profile') else None,
            'patronymic': patronymic,
            'phone': phone,
            'qualification': qualification,
            'birth_date': birth_date,
            'subjects': subjects,
            'teaching_groups': teaching_groups,
            'schedule_lessons': schedule_lessons,
            'grades_total': grades_stats['total'] or 0,
            'grades_avg': round(grades_stats['avg'], 1) if grades_stats['avg'] else 0,
            'grades_latest': grades_stats['latest'],
            'unique_students': unique_students,
            'subject_count': subjects.count(),
            'group_count': teaching_groups.count(),
            'lesson_count': schedule_lessons.count(),
        })
    
    # Общая статистика
    total_teachers = teachers_qs.count()
    active_teachers = teachers_qs.filter(is_active=True).count()
    
    # Статистика по предметам среди учителей
    subject_stats = Subject.objects.filter(
        subject_teachers__isnull=False
    ).annotate(
        teacher_count=Count('subject_teachers', distinct=True)
    ).order_by('-teacher_count')[:10]
    
    context = {
        'teachers_info': teachers_info,
        'search_query': search_query,
        'total_teachers': total_teachers,
        'active_teachers': active_teachers,
        'subject_stats': subject_stats,
    }
    return render(request, 'education_department/teachers_overview.html', context)


@login_required
@admin_required
def teacher_full_detail_admin(request, teacher_id):
    """Полная детальная информация об учителе (ТОЧНАЯ КОПИЯ ВАШЕЙ ФУНКЦИИ)"""
    user = get_object_or_404(User, id=teacher_id)
    
    # Проверяем, что это учитель
    if not user.groups.filter(name='teacher').exists() and not hasattr(user, 'teacher_profile'):
        messages.error(request, 'Пользователь не является учителем')
        return redirect('education_department:teachers_overview')
    
    try:
        profile = user.teacher_profile
    except TeacherProfile.DoesNotExist:
        profile = None
        messages.warning(request, 'У учителя нет профиля')
    
    # Предметы учителя
    teacher_subjects = TeacherSubject.objects.filter(
        teacher__user=user
    ).select_related('subject')
    
    # Группы, в которых преподает учитель
    teaching_groups = StudentGroup.objects.filter(
        daily_schedules__lessons__teacher=user
    ).distinct().order_by('year', 'name')
    
    # Детальное расписание учителя
    schedule_by_day = {}
    schedule_lessons = ScheduleLesson.objects.filter(
        teacher=user
    ).select_related(
        'daily_schedule', 'subject', 'daily_schedule__student_group'
    ).order_by('daily_schedule__week_day', 'lesson_number')
    
    for lesson in schedule_lessons:
        day = lesson.daily_schedule.get_week_day_display()
        day_code = lesson.daily_schedule.week_day
        
        if day_code not in schedule_by_day:
            schedule_by_day[day_code] = {
                'day_name': day,
                'lessons': []
            }
        schedule_by_day[day_code]['lessons'].append(lesson)
    
    # Статистика оценок
    grades_stats = Grade.objects.filter(
        teacher=user
    )
    
    total_grades = grades_stats.count()
    avg_grade_result = grades_stats.aggregate(avg=Avg('value'))
    avg_grade = round(avg_grade_result['avg'], 1) if avg_grade_result['avg'] else 0
    
    # Статистика по предметам
    grades_by_subject = []
    for ts in teacher_subjects:
        subject_grades = Grade.objects.filter(
            teacher=user,
            subject=ts.subject
        )
        
        subject_stats = subject_grades.aggregate(
            total=Count('id'),
            avg=Avg('value'),
            first_date=Min('date'),
            last_date=Max('date')
        )
        
        # Распределение оценок по предмету
        grade_distribution = {}
        for value in [5, 4, 3, 2]:
            count = subject_grades.filter(value=value).count()
            if count > 0:
                percentage = round((count / subject_stats['total'] * 100), 1) if subject_stats['total'] > 0 else 0
                grade_distribution[value] = {
                    'count': count,
                    'percentage': percentage
                }
        
        grades_by_subject.append({
            'subject': ts.subject,
            'total': subject_stats['total'] or 0,
            'avg': round(subject_stats['avg'], 1) if subject_stats['avg'] else 0,
            'first_date': subject_stats['first_date'],
            'last_date': subject_stats['last_date'],
            'grade_distribution': grade_distribution,
        })
    
    # Статистика по типам оценок
    grades_by_type = []
    for grade_type_code, grade_type_name in Grade.GradeType.choices:
        type_grades = grades_stats.filter(grade_type=grade_type_code)
        count = type_grades.count()
        if count > 0:
            avg_result = type_grades.aggregate(avg=Avg('value'))
            avg = round(avg_result['avg'], 1) if avg_result['avg'] else 0
            percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
            
            grades_by_type.append({
                'type': grade_type_code,
                'name': grade_type_name,
                'count': count,
                'avg': avg,
                'percentage': percentage,
            })
    
    # Последние выставленные оценки
    recent_grades = grades_stats.select_related(
        'student', 'subject'
    ).order_by('-date')[:10]
    
    # Ученики, у которых учитель преподает
    students_taught = User.objects.filter(
        grades__teacher=user
    ).distinct().count()
    
    context = {
        'teacher_user': user,
        'profile': profile,
        'teacher_subjects': teacher_subjects,
        'teaching_groups': teaching_groups,
        'schedule_by_day': schedule_by_day,
        'total_grades': total_grades,
        'avg_grade': avg_grade,
        'grades_by_subject': grades_by_subject,
        'grades_by_type': grades_by_type,
        'recent_grades': recent_grades,
        'students_taught': students_taught,
        'lesson_count': schedule_lessons.count(),
        'subject_count': teacher_subjects.count(),
        'group_count': teaching_groups.count(),
    }
    return render(request, 'education_department/teacher_full_detail.html', context)


@login_required
@education_department_required
def teacher_subject_performance(request, teacher_id, subject_id):
    """Производительность учителя по конкретному предмету (ТОЧНАЯ КОПИЯ ВАШЕЙ ФУНКЦИИ)"""
    user = get_object_or_404(User, id=teacher_id)
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Проверяем, что учитель преподает этот предмет
    if not TeacherSubject.objects.filter(
        teacher__user=user,
        subject=subject
    ).exists():
        messages.error(request, f'Учитель не преподает предмет "{subject.name}"')
        return redirect('education_department:teacher_full_detail', teacher_id=teacher_id)
    
    # Группы, в которых учитель ведет этот предмет
    teaching_groups = StudentGroup.objects.filter(
        daily_schedules__lessons__teacher=user,
        daily_schedules__lessons__subject=subject
    ).distinct().order_by('year', 'name')
    
    # Оценки учителя по этому предмету
    grades = Grade.objects.filter(
        teacher=user,
        subject=subject
    ).select_related('student', 'schedule_lesson__daily_schedule__student_group')
    
    total_grades = grades.count()
    avg_grade_result = grades.aggregate(avg=Avg('value'))
    avg_grade = round(avg_grade_result['avg'], 1) if avg_grade_result['avg'] else 0
    
    # Статистика по месяцам
    monthly_stats = []
    monthly_data = grades.annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        count=Count('id'),
        avg=Avg('value')
    ).order_by('-month')[:12]  # Последние 12 месяцев
    
    for stat in monthly_data:
        monthly_stats.append({
            'month': stat['month'].strftime('%Y-%m'),
            'month_name': calendar.month_name[stat['month'].month],
            'year': stat['month'].year,
            'count': stat['count'],
            'avg': round(stat['avg'], 1) if stat['avg'] else 0,
        })
    
    # Статистика по группам
    group_stats = []
    for group in teaching_groups:
        group_grades = grades.filter(
            schedule_lesson__daily_schedule__student_group=group
        )
        group_total = group_grades.count()
        
        if group_total > 0:
            group_avg_result = group_grades.aggregate(avg=Avg('value'))
            group_avg = round(group_avg_result['avg'], 1) if group_avg_result['avg'] else 0
            
            group_stats.append({
                'group': group,
                'total': group_total,
                'avg': group_avg,
            })
    
    # Распределение оценок
    grade_distribution = {}
    for value in [5, 4, 3, 2]:
        count = grades.filter(value=value).count()
        if count > 0:
            percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
            grade_distribution[value] = {
                'count': count,
                'percentage': percentage
            }
    
    # Последние оценки
    recent_grades = grades.order_by('-date')[:20]
    
    context = {
        'teacher_user': user,
        'subject': subject,
        'teaching_groups': teaching_groups,
        'total_grades': total_grades,
        'avg_grade': avg_grade,
        'monthly_stats': monthly_stats,
        'group_stats': group_stats,
        'grade_distribution': grade_distribution,
        'recent_grades': recent_grades,
    }
    return render(request, 'education_department/teacher_subject_performance.html', context)


# ===== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ НОВОГО ПРИЛОЖЕНИЯ =====

@login_required
@education_department_required
def department_dashboard(request):
    """Главная панель учебного отдела"""
    # Статистика
    total_groups = StudentGroup.objects.count()
    total_students = StudentProfile.objects.count()
    total_teachers = TeacherProfile.objects.count()
    total_subjects = Subject.objects.count()
    
    # Последние оценки
    recent_grades = Grade.objects.select_related(
        'student', 'subject', 'teacher'
    ).order_by('-date')[:10]
    
    # Последние домашние задания
    recent_homeworks = Homework.objects.select_related(
        'student_group', 'schedule_lesson__subject'
    ).order_by('-created_at')[:5]
    
    context = {
        'total_groups': total_groups,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_subjects': total_subjects,
        'recent_grades': recent_grades,
        'recent_homeworks': recent_homeworks,
    }
    return render(request, 'education_department/dashboard.html', context)


# Заглушки для будущих функций
@login_required
@education_department_required
def homework_overview(request):
    """Обзор домашних заданий (ЗАГЛУШКА)"""
    messages.info(request, 'Функция домашних заданий находится в разработке')
    return render(request, 'education_department/homework/overview.html')


@login_required
@education_department_required
def schedule_management(request):
    """Управление расписанием (ЗАГЛУШКА - используем существующее приложение schedule)"""
    messages.info(request, 'Управление расписанием находится в отдельном приложении')
    return redirect('schedule:dashboard')

from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

@login_required
@education_department_required
def homework_stats(request):
    """
    Статистика домашних заданий (только просмотр).
    Фильтры: период, группа, предмет, статус сдачи.
    """
    # --- фильтры ---
    period = request.GET.get("period", "30")  # 7 / 30 / 90 / all
    group_id = request.GET.get("group", "")
    subject_id = request.GET.get("subject", "")
    status = request.GET.get("status", "")   # submitted / not_submitted / any

    # период
    now = timezone.now()
    if period in ("7", "30", "90"):
        date_from = now - timedelta(days=int(period))
    else:
        date_from = None

    # базовый queryset ДЗ
    homeworks_qs = Homework.objects.select_related(
        "student_group", "schedule_lesson__subject"
    ).all().order_by("-created_at")

    if date_from:
        homeworks_qs = homeworks_qs.filter(created_at__gte=date_from)

    if group_id:
        homeworks_qs = homeworks_qs.filter(student_group_id=group_id)

    if subject_id:
        homeworks_qs = homeworks_qs.filter(schedule_lesson__subject_id=subject_id)

    # статус сдачи (на уровне ДЗ)
    # submitted = есть хотя бы 1 submission
    # not_submitted = нет ни одной submission
    if status == "submitted":
        homeworks_qs = homeworks_qs.annotate(submissions_cnt=Count("submissions")).filter(submissions_cnt__gt=0)
    elif status == "not_submitted":
        homeworks_qs = homeworks_qs.annotate(submissions_cnt=Count("submissions")).filter(submissions_cnt=0)

    # --- агрегаты для карточек ---
    # кол-во ДЗ
    total_homeworks = homeworks_qs.count()

    # кол-во сдач по выбранным ДЗ
    submissions_total = HomeworkSubmission.objects.filter(
        homework__in=homeworks_qs
    ).count()

    # уникальных учеников, которые сдавали
    students_submitted = User.objects.filter(
        homework_submissions__homework__in=homeworks_qs
    ).distinct().count()

    # среднее кол-во сдач на 1 ДЗ (грубо)
    avg_submissions_per_hw = round(submissions_total / total_homeworks, 2) if total_homeworks else 0

    # --- таблица последних ДЗ (без тяжёлых join’ов) ---
    latest_homeworks = homeworks_qs[:25]

    # справочники для фильтров
    groups = StudentGroup.objects.all().order_by("year", "name")
    subjects = Subject.objects.all().order_by("name")

    context = {
        "filters": {
            "period": period,
            "group": group_id,
            "subject": subject_id,
            "status": status,
        },
        "groups": groups,
        "subjects": subjects,
        "total_homeworks": total_homeworks,
        "submissions_total": submissions_total,
        "students_submitted": students_submitted,
        "avg_submissions_per_hw": avg_submissions_per_hw,
        "latest_homeworks": latest_homeworks,
    }
    return render(request, "education_department/homework_stats.html", context)





from io import BytesIO
import os

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Avg, Count

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


@login_required
@education_department_required
def grades_school_report_pdf(request):
    """
    PDF отчёт по общей статистике оценок по школе (без CRUD).
    """

    # ====== агрегаты "по школе" ======
    total_groups = StudentGroup.objects.count()
    total_students = StudentProfile.objects.count()
    total_grades = Grade.objects.count()

    overall_avg_val = Grade.objects.aggregate(avg=Avg("value"))["avg"]
    overall_avg = round(_safe_float(overall_avg_val, 0.0), 2) if overall_avg_val else 0

    groups_without_curator = StudentGroup.objects.filter(curator__isnull=True).count()

    # распределение оценок (пример по целым: 5,4,3,2)
    dist = {v: Grade.objects.filter(value=v).count() for v in [5, 4, 3, 2]}

    # топ-5 предметов по количеству оценок (надёжно через Grade)
    top_subjects = (
        Grade.objects
        .values("subject__name")
        .annotate(grades_cnt=Count("id"))
        .order_by("-grades_cnt", "subject__name")[:5]
    )

    # топ-5 групп по среднему баллу (где есть оценки)
    groups_avg = (
        StudentGroup.objects
        .annotate(
            grades_cnt=Count("students__user__grades", distinct=True),
            avg_grade=Avg("students__user__grades__value"),
            student_cnt=Count("students", distinct=True),
        )
        .filter(grades_cnt__gt=0)
        .order_by("-avg_grade")[:5]
    )

    # ====== PDF ======
    buffer = BytesIO()

    # шрифт из проекта
    font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "ARIAL.TTF")

    try:
        pdfmetrics.registerFont(TTFont("Arial", font_path))
        base_font = "Arial"
    except Exception:
        base_font = "Helvetica"  # если шрифт не найден, кириллица может сломаться

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    title = styles["Title"]
    h2 = styles["Heading2"]
    h3 = styles["Heading3"]

    for st in (normal, title, h2, h3):
        st.fontName = base_font

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Отчёт по оценкам",
    )

    story = []

    report_date = timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M")

    story.append(Paragraph("ОТЧЁТ", title))
    story.append(Paragraph("Общая статистика оценок по школе", h2))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Дата формирования: {report_date}", normal))
    story.append(Spacer(1, 12))

    # 1) Общая сводка
    summary_data = [
        ["Показатель", "Значение"],
        ["Всего групп", str(total_groups)],
        ["Всего учеников", str(total_students)],
        ["Всего оценок", str(total_grades)],
        ["Средний балл (по школе)", (f"{overall_avg:.2f}" if overall_avg else "—")],
        ["Групп без куратора", str(groups_without_curator)],
    ]
    summary_table = Table(summary_data, colWidths=[110 * mm, 60 * mm])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), base_font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f4f7")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d5dd")),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Paragraph("1) Общая сводка", h3))
    story.append(summary_table)
    story.append(Spacer(1, 12))

    # 2) Распределение оценок
    dist_data = [
        ["Оценка", "Количество"],
        ["5", str(dist[5])],
        ["4", str(dist[4])],
        ["3", str(dist[3])],
        ["2", str(dist[2])],
    ]
    dist_table = Table(dist_data, colWidths=[50 * mm, 120 * mm])
    dist_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), base_font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f4f7")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d5dd")),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Paragraph("2) Распределение оценок", h3))
    story.append(dist_table)
    story.append(Spacer(1, 12))

    # 3) Топ предметов
    subj_data = [["Предмет", "Оценок"]]
    for s in top_subjects:
        subj_data.append([s["subject__name"] or "—", str(s["grades_cnt"] or 0)])

    subj_table = Table(subj_data, colWidths=[130 * mm, 40 * mm])
    subj_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), base_font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f4f7")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d5dd")),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Paragraph("3) Топ-5 предметов по количеству оценок", h3))
    story.append(subj_table)
    story.append(Spacer(1, 12))

    # 4) Топ групп
    grp_data = [["Группа", "Учеников", "Оценок", "Средний балл"]]
    for g in groups_avg:
        grp_data.append([
            f"{g.name} ({g.year} год)",
            str(g.student_cnt or 0),
            str(g.grades_cnt or 0),
            f"{_safe_float(g.avg_grade, 0.0):.2f}" if g.avg_grade else "—",
        ])

    grp_table = Table(grp_data, colWidths=[85 * mm, 30 * mm, 25 * mm, 30 * mm])
    grp_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), base_font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f4f7")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d5dd")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Paragraph("4) Топ-5 групп по среднему баллу (где есть оценки)", h3))
    story.append(grp_table)
    story.append(Spacer(1, 18))

    story.append(Paragraph("Подпись ответственного: ____________________", normal))
    story.append(Spacer(1, 6))
    story.append(Paragraph("М.П.", normal))

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    filename = f"school_grades_report_{timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M')}.pdf"
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write(pdf)
    return response
