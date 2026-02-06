# teacher_portal/decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def teacher_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Требуется авторизация')
            return redirect('login_page')
        
        # Проверяем, что пользователь - учитель
        if not (request.user.groups.filter(name='teacher').exists() or 
                hasattr(request.user, 'teacher_profile')):
            messages.error(request, 'Доступ только для учителей')
            return redirect('dashboard_page')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view