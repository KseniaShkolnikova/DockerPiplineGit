from rest_framework import viewsets
from django.contrib.auth.models import User
from .models import *
from .serializers import *
from .permissions import CustomPermission
from .pagination import PaginationPage

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class StudentGroupViewSet(viewsets.ModelViewSet):
    queryset = StudentGroup.objects.all()
    serializer_class = StudentGroupSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class StudentProfileViewSet(viewsets.ModelViewSet):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class TeacherProfileViewSet(viewsets.ModelViewSet):
    queryset = TeacherProfile.objects.all()
    serializer_class = TeacherProfileSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class TeacherSubjectViewSet(viewsets.ModelViewSet):
    queryset = TeacherSubject.objects.all()
    serializer_class = TeacherSubjectSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class DailyScheduleViewSet(viewsets.ModelViewSet):
    queryset = DailySchedule.objects.all()
    serializer_class = DailyScheduleSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class ScheduleLessonViewSet(viewsets.ModelViewSet):
    queryset = ScheduleLesson.objects.all()
    serializer_class = ScheduleLessonSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class HomeworkViewSet(viewsets.ModelViewSet):
    queryset = Homework.objects.all()
    serializer_class = HomeworkSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class HomeworkSubmissionViewSet(viewsets.ModelViewSet):
    queryset = HomeworkSubmission.objects.all()
    serializer_class = HomeworkSubmissionSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class GradeViewSet(viewsets.ModelViewSet):
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage

class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [CustomPermission]
    pagination_class = PaginationPage