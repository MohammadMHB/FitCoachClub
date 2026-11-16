import math
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from accounts.models import User, TraineeProfile


def validate_image_size(file):
    max_mb = 5
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f'حجم عکس نباید بیشتر از {max_mb} مگابایت باشد.')


def validate_video_size(file):
    max_mb = 50
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f'حجم ویدیو نباید بیشتر از {max_mb} مگابایت باشد.')


CATEGORY_CHOICES = [
    ('chest',       'سینه'),
    ('upper_chest', 'بالاسینه'),
    ('lower_chest', 'زیرسینه'),
    ('shoulder',    'سرشانه'),
    ('neck',        'گردن'),
    ('forearm',     'ساعد'),
    ('leg',         'پا'),
    ('tricep',      'پشت‌بازو'),
    ('bicep',       'جلوبازو'),
    ('arm',         'اصلاحی'),
    ('abs',         'شکم'),
    ('back',        'پشت'),
    ('lats',        'زیربغل'),
    ('home',        'منزل'),
]

DAY_CHOICES = [
    (1, 'شنبه'),
    (2, 'یکشنبه'),
    (3, 'دوشنبه'),
    (4, 'سه‌شنبه'),
    (5, 'چهارشنبه'),
    (6, 'پنجشنبه'),   # ← اضافه شد
]

# رژیم غذایی برخلاف برنامه تمرینی باید هر ۷ روز هفته (از جمله جمعه) رو پوشش بده
NUTRITION_DAY_CHOICES = DAY_CHOICES + [(7, 'جمعه')]

MEAL_TYPE_CHOICES = [
    ('breakfast',       'صبحانه'),
    ('morning_snack',   'میان‌وعده صبح'),
    ('lunch',           'ناهار'),
    ('afternoon_snack', 'میان‌وعده عصر'),
    ('dinner',          'شام'),
    ('evening_snack',   'میان‌وعده شب'),
]

# ===== بانک غذایی (برای انتخاب سریع مواد غذایی هنگام ثبت وعده) =====
FOOD_CATEGORY_CHOICES = [
    ('protein',     'پروتئین (گوشت، مرغ، ماهی، تخم‌مرغ)'),
    ('carb',        'نان، غلات و نشاسته'),
    ('dairy',       'لبنیات'),
    ('vegetable',   'سبزیجات'),
    ('fruit',       'میوه‌ها'),
    ('legume',      'حبوبات'),
    ('fat_nut',     'چربی‌ها و آجیل'),
    ('drink',       'نوشیدنی'),
    ('sweet',       'شیرینی و دسر'),
    ('sauce_spice', 'ادویه و چاشنی'),
    ('supplement',  'مکمل'),
    ('fast_food',   'فست‌فود و غذای آماده'),
    ('soup_stew',   'سوپ، آش و خورش'),
    ('other',       'سایر'),
]

FOOD_UNIT_CHOICES = [
    ('gram',    'گرم'),
    ('piece',   'عدد'),
    ('cup',     'لیوان'),
    ('tbsp',    'قاشق غذاخوری'),
    ('tsp',     'قاشق چایخوری'),
    ('slice',   'برش'),
    ('handful', 'مشت'),
    ('serving', 'پرس'),
    ('plate',   'بشقاب'),
]

SET_TYPE_CHOICES = [
    ('normal',    'معمولی'),
    ('superset',  'سوپرست'),
    ('triset',    'تری‌ست'),
    ('dropset',   'دراپ‌ست'),
]


class Exercise(models.Model):
    name        = models.CharField(max_length=200)
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    image       = models.ImageField(upload_to='exercises/images/', null=True, blank=True,
                                     validators=[validate_image_size])
    video       = models.FileField(upload_to='exercises/videos/', null=True, blank=True,
                                    validators=[
                                        FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'webm', 'avi', 'mkv']),
                                        validate_video_size,
                                    ])
    video_url   = models.URLField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    coach       = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='exercises', limit_choices_to={'role': 'coach'})
    is_public   = models.BooleanField(default=False)
    # وقتی ادمین حرکت اضافه می‌کند و می‌خواهد فقط برای یک مربی خاص نمایش داده شود
    # (به‌جای همه‌ی مربی‌ها). اگر خالی باشد و is_public=True باشد، برای همه نمایش داده می‌شود.
    visible_to_coach = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                          related_name='exclusive_exercises',
                                          limit_choices_to={'role': 'coach'},
                                          verbose_name='مخصوص مربی')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class FoodItem(models.Model):
    """
    آیتم بانک غذایی - برای انتخاب سریع مواد غذایی توسط مربی هنگام ثبت رژیم.
    فقط ادمین این بانک را مدیریت می‌کند (افزودن/ویرایش/حذف).
    """
    name           = models.CharField(max_length=150)
    category       = models.CharField(max_length=20, choices=FOOD_CATEGORY_CHOICES)
    default_unit   = models.CharField(max_length=20, choices=FOOD_UNIT_CHOICES, default='gram')
    default_amount = models.CharField(max_length=20, blank=True, default='',
                                       verbose_name='مقدار پیشنهادی',
                                       help_text='مثلاً 150 برای گرم یا 1 برای عدد')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'آیتم بانک غذایی'
        verbose_name_plural = 'بانک غذایی'

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class WorkoutProgram(models.Model):
    trainee     = models.ForeignKey(TraineeProfile, on_delete=models.CASCADE, related_name='programs')
    coach       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_programs')
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    is_active   = models.BooleanField(default=True)
    # مدت زمان اعتبار برنامه به روز (مثلاً برنامه ۳۰ روزه)
    duration_days = models.PositiveIntegerField(default=30, verbose_name='مدت برنامه (روز)')
    # برای جلوگیری از ارسال چندباره‌ی نوتیف یادآوری تمدید
    renewal_notified = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['trainee', 'is_active'], name='wp_trainee_active_idx'),
        ]

    def __str__(self):
        return f"{self.title} - {self.trainee.user.get_full_name()}"

    @property
    def end_date(self):
        """تاریخ پایان اعتبار برنامه بر اساس تاریخ ثبت + مدت برنامه."""
        return self.created_at + timezone.timedelta(days=self.duration_days)

    @property
    def days_remaining(self):
        """تعداد روزهای باقی‌مانده تا پایان برنامه (هیچ‌وقت منفی نمی‌شود)."""
        delta_seconds = (self.end_date - timezone.now()).total_seconds()
        if delta_seconds <= 0:
            return 0
        return math.ceil(delta_seconds / 86400)

    @property
    def is_expired(self):
        return timezone.now() >= self.end_date

    @property
    def needs_renewal_soon(self):
        """۳ روز یا کمتر مانده و هنوز منقضی نشده."""
        return (not self.is_expired) and self.days_remaining <= 3

    def maybe_notify_renewal(self):
        """اگر مانده به انقضا ۳ روز یا کمتر باشد و قبلاً نوتیف نرفته، برای شاگرد نوتیف بساز."""
        if self.is_active and self.needs_renewal_soon and not self.renewal_notified:
            Notification.objects.create(
                recipient=self.trainee.user,
                sender=self.coach,
                notif_type='system',
                title='وقت تمدید برنامه‌ست',
                message=f'برنامه «{self.title}» شما {self.days_remaining} روز دیگر تمام می‌شود. برای ادامه، از مربی خود بخواهید برنامه را تمدید کند.',
            )
            self.renewal_notified = True
            self.save(update_fields=['renewal_notified'])


class WorkoutDay(models.Model):
    program    = models.ForeignKey(WorkoutProgram, on_delete=models.CASCADE, related_name='days')
    day_number = models.IntegerField(choices=DAY_CHOICES)
    notes      = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['day_number']
        unique_together = ['program', 'day_number']

    def __str__(self):
        return f"{self.get_day_number_display()} - {self.program.title}"


class WorkoutExercise(models.Model):
    day          = models.ForeignKey(WorkoutDay, on_delete=models.CASCADE, related_name='exercises')
    exercise     = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    sets         = models.IntegerField(default=3)
    reps         = models.CharField(max_length=50, default='12')
    rest_seconds = models.IntegerField(default=60)
    set_type     = models.CharField(max_length=10, choices=SET_TYPE_CHOICES, default='normal')
    notes        = models.TextField(blank=True, null=True)
    order        = models.IntegerField(default=0)
    # برای سوپرست/تری‌ست: حرکات هم‌گروه یک group_id مشترک دارند
    group_id     = models.IntegerField(null=True, blank=True)
    # برای دراپ‌ست: وزن‌های هر دراپ
    dropset_weights = models.CharField(max_length=200, blank=True, null=True,
                                        help_text='وزن‌های دراپ‌ست با کاما، مثلاً: 80,70,60')

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.exercise.name} - {self.sets}x{self.reps}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('new_trainee',     'شاگرد جدید'),
        ('program_ready',   'برنامه آماده شد'),
        ('diet_ready',      'رژیم غذایی آماده شد'),
        ('system',          'سیستم'),
    ]
    recipient       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='sent_notifications')
    notif_type      = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title           = models.CharField(max_length=200)
    message         = models.TextField()
    is_read         = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# ===================== رژیم غذایی =====================

class NutritionPlan(models.Model):
    """
    برنامه‌ی غذایی یک شاگرد - از نظر ساختار شبیه WorkoutProgram است (مدت‌دار،
    شمارش معکوس تا پایان، یادآوری تمدید)، اما محتوایش متن آزاد هر وعده است
    نه لیست ساختاریافته‌ی آیتم غذایی.
    """
    trainee     = models.ForeignKey(TraineeProfile, on_delete=models.CASCADE, related_name='nutrition_plans')
    coach       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_nutrition_plans')
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    is_active   = models.BooleanField(default=True)
    duration_days = models.PositiveIntegerField(default=30, verbose_name='مدت رژیم (روز)')
    renewal_notified = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'برنامه غذایی'
        verbose_name_plural = 'برنامه‌های غذایی'
        indexes = [
            models.Index(fields=['trainee', 'is_active'], name='np_trainee_active_idx'),
        ]

    def __str__(self):
        return f"{self.title} - {self.trainee.user.get_full_name()}"

    @property
    def end_date(self):
        return self.created_at + timezone.timedelta(days=self.duration_days)

    @property
    def days_remaining(self):
        delta_seconds = (self.end_date - timezone.now()).total_seconds()
        if delta_seconds <= 0:
            return 0
        return math.ceil(delta_seconds / 86400)

    @property
    def is_expired(self):
        return timezone.now() >= self.end_date

    @property
    def needs_renewal_soon(self):
        return (not self.is_expired) and self.days_remaining <= 3

    def maybe_notify_renewal(self):
        if self.is_active and self.needs_renewal_soon and not self.renewal_notified:
            Notification.objects.create(
                recipient=self.trainee.user,
                sender=self.coach,
                notif_type='system',
                title='وقت تمدید رژیم غذایی‌ست',
                message=f'رژیم غذایی «{self.title}» شما {self.days_remaining} روز دیگر تمام می‌شود. برای ادامه، از مربی خود بخواهید رژیم را تمدید کند.',
            )
            self.renewal_notified = True
            self.save(update_fields=['renewal_notified'])


class NutritionDay(models.Model):
    plan       = models.ForeignKey(NutritionPlan, on_delete=models.CASCADE, related_name='days')
    day_number = models.IntegerField(choices=NUTRITION_DAY_CHOICES)
    notes      = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['day_number']
        unique_together = ['plan', 'day_number']

    def __str__(self):
        return f"{self.get_day_number_display()} - {self.plan.title}"


class Meal(models.Model):
    day       = models.ForeignKey(NutritionDay, on_delete=models.CASCADE, related_name='meals')
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES)
    content   = models.TextField(verbose_name='محتوای وعده')
    order     = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ['day', 'meal_type']

    def __str__(self):
        return f"{self.get_meal_type_display()} - {self.day}"
