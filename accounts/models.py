from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets
import uuid
from django.core.exceptions import ValidationError
from .phone import normalize_mobile


def _generate_referral_code():
    return secrets.token_urlsafe(8)


class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'مدیر'),
        ('coach', 'مربی'),
        ('trainee', 'شاگرد'),
    ]
    role  = models.CharField(max_length=10, choices=ROLE_CHOICES, default='trainee')
    phone = models.CharField(max_length=15, blank=True, null=True, verbose_name='شماره تلفن')
    phone_normalized = models.CharField(max_length=11, blank=True, default='', db_index=True, editable=False)
    # کد یکتای عمومی برای لینک ثبت‌نام شاگرد (فقط برای مربی‌ها معنا داره).
    # از این کد به‌جای username استفاده می‌کنیم که یوزر/پسورد مربی لو نره.
    referral_code = models.CharField(max_length=32, unique=True, null=True, blank=True,
                                      db_index=True, verbose_name='کد لینک ثبت‌نام')
    # برای ارسال یوزر/پسورد به مربی از پنل ادمین - فقط آخرین پسوردی که تنظیم شده
    last_password_plain = models.CharField(max_length=128, blank=True, null=True)

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    def ensure_referral_code(self):
        """اگر کد نداشت، یکی یکتا می‌سازد و ذخیره می‌کند. برای مربی‌های قدیمی هم کار می‌کند."""
        if self.referral_code:
            return self.referral_code
        for _ in range(10):
            code = _generate_referral_code()
            if not User.objects.filter(referral_code=code).exists():
                self.referral_code = code
                self.save(update_fields=['referral_code'])
                return code
        raise RuntimeError('امکان ساخت کد یکتا وجود نداشت.')

    def save(self, *args, **kwargs):
        try:
            self.phone_normalized = normalize_mobile(self.phone)
        except ValidationError:
            self.phone_normalized = ''
        if kwargs.get('update_fields') is not None and 'phone' in kwargs['update_fields']:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'phone_normalized'}
        # هر مربی همیشه باید یک کد لینک ثبت‌نام داشته باشد؛ اینجا هم پوشش
        # می‌دیم که هرجایی (پنل ادمین، shell، فیکسچر و...) مربی ساخته بشه،
        # کدش خودکار ست بشه، بدون نیاز به یادآوری صدا زدن ensure_referral_code.
        if self.role == 'coach' and not self.referral_code:
            for _ in range(10):
                code = _generate_referral_code()
                if not User.objects.filter(referral_code=code).exclude(pk=self.pk).exists():
                    self.referral_code = code
                    break
        super().save(*args, **kwargs)

    @property
    def is_admin(self):   return self.role == 'admin'
    @property
    def is_coach(self):   return self.role == 'coach'
    @property
    def is_trainee(self): return self.role == 'trainee'


class TraineeProfile(models.Model):
    STATUS_CHOICES = [
        ('underweight', 'لاغر'),
        ('normal',      'نرمال'),
        ('overweight',  'اضافه وزن'),
        ('obese',       'چاق'),
    ]
    user   = models.OneToOneField(User, on_delete=models.CASCADE, related_name='trainee_profile')
    coach  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='trainees', limit_choices_to={'role': 'coach'})
    weight = models.FloatField(null=True, blank=True, verbose_name='وزن (kg)')
    height = models.FloatField(null=True, blank=True, verbose_name='قد (cm)')
    age    = models.IntegerField(null=True, blank=True, verbose_name='سن')
    bmi    = models.FloatField(null=True, blank=True, verbose_name='BMI')
    bmi_status = models.CharField(max_length=15, choices=STATUS_CHOICES, blank=True, null=True)

    # برای ارسال پیامک یوزر/پسورد به شاگرد - فقط آخرین پسوردی که مربی/ادمین تنظیم کرده
    last_password_plain = models.CharField(max_length=128, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_bmi(self):
        if self.weight and self.height and self.height > 0:
            h_m = self.height / 100
            self.bmi = round(self.weight / (h_m ** 2), 1)
            if   self.bmi < 18.5: self.bmi_status = 'underweight'
            elif self.bmi < 25:   self.bmi_status = 'normal'
            elif self.bmi < 30:   self.bmi_status = 'overweight'
            else:                 self.bmi_status = 'obese'
        return self.bmi

    @property
    def ideal_weight_range(self):
        """بازه‌ی وزن سالم (BMI بین ۱۸.۵ تا ۲۵) بر اساس قد، به کیلوگرم."""
        if not self.height or self.height <= 0:
            return None
        h_m = self.height / 100
        low  = round(18.5 * (h_m ** 2), 1)
        high = round(24.9 * (h_m ** 2), 1)
        return (low, high)

    @property
    def weight_diff(self):
        """
        اختلاف وزن فعلی با بازه‌ی وزن سالم، به کیلوگرم.
        مثبت = اضافه وزن (چند کیلو باید کم کند) / منفی = کمبود وزن (چند کیلو باید اضافه کند) / صفر = وزن نرمال.
        """
        if not self.weight or not self.height:
            return None
        rng = self.ideal_weight_range
        if not rng:
            return None
        low, high = rng
        if self.weight < low:
            return round(self.weight - low, 1)
        if self.weight > high:
            return round(self.weight - high, 1)
        return 0.0

    @property
    def weight_diff_abs(self):
        """قدر مطلق اختلاف وزن با بازه‌ی سالم؛ برای نمایش در قالب‌ها."""
        diff = self.weight_diff
        return abs(diff) if diff is not None else None

    def save(self, *args, **kwargs):
        self.calculate_bmi()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'پروفایل شاگرد'
        verbose_name_plural = 'پروفایل‌های شاگرد'

    def __str__(self):
        return f"پروفایل {self.user.get_full_name() or self.user.username}"


class BodyMetricHistory(models.Model):
    trainee    = models.ForeignKey(TraineeProfile, on_delete=models.CASCADE, related_name='metric_history')
    weight     = models.FloatField(null=True, blank=True)
    height     = models.FloatField(null=True, blank=True)
    age        = models.IntegerField(null=True, blank=True)
    bmi        = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['recorded_at']
        verbose_name = 'تاریخچه اندازه‌گیری'
        verbose_name_plural = 'تاریخچه اندازه‌گیری‌ها'


class ActivityLog(models.Model):
    """
    گزارش هر تغییر مهمی که تو برنامه اتفاق می‌افته (چه کسی، چه کاری، کِی) —
    فقط برای ادمین قابل مشاهده‌ست. actor_name جدا از actor ذخیره میشه که
    اگر کاربر بعداً حذف شد، خود گزارش خوانا و کامل بمونه.
    """
    ACTION_CHOICES = [
        ('trainee_add',    'افزودن شاگرد'),
        ('trainee_edit',   'ویرایش شاگرد'),
        ('trainee_delete', 'حذف شاگرد'),
        ('trainee_toggle', 'فعال/غیرفعال کردن شاگرد'),
        ('program_create', 'ثبت برنامه تمرینی'),
        ('program_edit',   'ویرایش برنامه تمرینی'),
        ('program_copy',   'کپی برنامه تمرینی'),
        ('diet_create',    'ثبت رژیم غذایی'),
        ('diet_edit',      'ویرایش رژیم غذایی'),
        ('diet_copy',      'کپی رژیم غذایی'),
        ('coach_add',      'افزودن مربی'),
        ('coach_edit',     'ویرایش مربی'),
        ('coach_delete',   'حذف مربی'),
        ('coach_toggle',   'فعال/غیرفعال کردن مربی'),
        ('exercise_add',   'افزودن حرکت به بانک'),
        ('exercise_edit',  'ویرایش حرکت بانک'),
        ('exercise_delete','حذف حرکت از بانک'),
        ('food_add',       'افزودن آیتم به بانک غذایی'),
        ('food_edit',      'ویرایش آیتم بانک غذایی'),
        ('food_delete',    'حذف آیتم از بانک غذایی'),
    ]
    actor      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='activity_logs')
    actor_name = models.CharField(max_length=150, blank=True)
    actor_role = models.CharField(max_length=10, blank=True)
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'گزارش فعالیت'
        verbose_name_plural = 'گزارش فعالیت‌ها'

    def __str__(self):
        return f"{self.actor_name}: {self.description}"


class LoginAttempt(models.Model):
    """
    برای محدود کردن تعداد تلاش‌های ورود ناموفق (جلوگیری از حمله‌ی brute-force).
    فقط تلاش‌های ناموفق ثبت می‌شن؛ ردیف‌های قدیمی‌تر از یک بازه‌ی مشخص با
    دستور مدیریتی `cleanup_old_data` پاک می‌شن (نگاه کن به
    accounts/management/commands/cleanup_old_data.py).
    """
    ip_address     = models.GenericIPAddressField(db_index=True)
    username_tried = models.CharField(max_length=150, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']


class OTPChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_challenges')
    phone = models.CharField(max_length=11, db_index=True)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    delivered = models.BooleanField(default=False)


class OTPRateLimit(models.Model):
    key = models.CharField(max_length=80, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()
    next_allowed_at = models.DateTimeField()
