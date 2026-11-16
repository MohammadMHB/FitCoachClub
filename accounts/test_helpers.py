"""
توابع کمکی مشترک برای تست‌نویسی در همه‌ی اپ‌ها (coach، trainee، admin_panel).
اینجا نگه داشته می‌شن تا هر اپ فایل تست مخصوص به خودش رو داشته باشه بدون
تکرار این factory function‌ها.
"""
from accounts.models import User, TraineeProfile


def make_coach(username='coach1'):
    return User.objects.create_user(
        username=username, password='pass12345',
        first_name='علی', last_name='مربی', role='coach',
    )


def make_trainee(coach, username='trainee1', weight=90, height=170, age=25):
    user = User.objects.create_user(
        username=username, password='pass12345',
        first_name='رضا', last_name='شاگرد', role='trainee',
    )
    return TraineeProfile.objects.create(
        user=user, coach=coach, weight=weight, height=height, age=age,
    )


def make_admin(username='admin_food'):
    return User.objects.create_superuser(
        username=username, password='pass12345', role='admin',
    )
