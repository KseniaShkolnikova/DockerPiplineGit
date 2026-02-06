from django.urls import path, include
from rest_framework import routers
from .views import *

router = routers.SimpleRouter()
router.register('users', UserViewSet)
router.register('subjects', SubjectViewSet)
router.register('student-groups', StudentGroupViewSet)
router.register('student-profiles', StudentProfileViewSet)
router.register('teacher-profiles', TeacherProfileViewSet)
router.register('teacher-subjects', TeacherSubjectViewSet)
router.register('daily-schedules', DailyScheduleViewSet)
router.register('schedule-lessons', ScheduleLessonViewSet)
router.register('homeworks', HomeworkViewSet)
router.register('homework-submissions', HomeworkSubmissionViewSet)
router.register('grades', GradeViewSet)
router.register('comments', CommentViewSet)
router.register('attendance', AttendanceViewSet)
router.register('announcements', AnnouncementViewSet)

urlpatterns = router.urls