# این فایل placeholder است
# اگه قبلاً makemigrations زدید این فایل را حذف کنید
# Django از فایل واقعی شما استفاده می‌کند
from django.db import migrations

class Migration(migrations.Migration):
    # این migration فقط برای اینکه 0002 بتونه depend کنه وجود داره
    # اگه migration 0001 واقعی دارید این فایل رو حذف کنید
    initial = True
    dependencies = []
    operations = []
