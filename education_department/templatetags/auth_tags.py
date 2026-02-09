from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='is_education_department')
def is_education_department(request):
    """
    Проверяет, является ли пользователь сотрудником учебного отдела
    """
    user = request.user
    if not user.is_authenticated:
        return False
    
    return (
        user.is_superuser or 
        user.groups.filter(name='admin').exists() or
        user.groups.filter(name='education_department').exists()
    )

@register.filter(name='has_education_department_access')
def has_education_department_access(user):
    """
    Проверяет, имеет ли пользователь доступ к учебному отделу
    """
    if not user.is_authenticated:
        return False
    
    return (
        user.is_superuser or 
        user.groups.filter(name='admin').exists() or
        user.groups.filter(name='education_department').exists()
    )

@register.filter(name='is_admin')
def is_admin(user):
    """
    Проверяет, является ли пользователь админом
    """
    if not user.is_authenticated:
        return False
    
    return user.is_superuser or user.groups.filter(name='admin').exists()

@register.filter(name='is_teacher')
def is_teacher(user):
    """
    Проверяет, является ли пользователь учителем
    """
    if not user.is_authenticated:
        return False
    
    return user.groups.filter(name='teacher').exists()

@register.filter(name='is_student')
def is_student(user):
    """
    Проверяет, является ли пользователь учеником
    """
    if not user.is_authenticated:
        return False
    
    return user.groups.filter(name='student').exists()