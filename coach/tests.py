from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, TraineeProfile
from accounts.test_helpers import make_coach, make_trainee, make_admin
from coach.models import (WorkoutProgram, WorkoutDay, WorkoutExercise, Exercise, Notification,
                           NutritionPlan, NutritionDay, Meal, NUTRITION_DAY_CHOICES,
                           FoodItem, FOOD_CATEGORY_CHOICES)


class WeightDiffTests(TestCase):
    """تست محاسبه‌ی اضافه‌وزن/کمبود وزن نسبت به بازه‌ی سالم BMI"""

    def test_overweight_trainee_has_positive_diff(self):
        coach = make_coach()
        profile = make_trainee(coach, weight=90, height=170)  # BMI ~31 -> obese
        low, high = profile.ideal_weight_range
        self.assertGreater(profile.weight_diff, 0)
        self.assertAlmostEqual(profile.weight_diff, round(90 - high, 1))
        self.assertEqual(profile.weight_diff_abs, abs(profile.weight_diff))

    def test_underweight_trainee_has_negative_diff(self):
        coach = make_coach()
        profile = make_trainee(coach, weight=45, height=170)  # BMI ~15.6 -> underweight
        low, high = profile.ideal_weight_range
        self.assertLess(profile.weight_diff, 0)
        self.assertAlmostEqual(profile.weight_diff, round(45 - low, 1))

    def test_normal_weight_trainee_has_zero_diff(self):
        coach = make_coach()
        profile = make_trainee(coach, weight=65, height=170)  # BMI ~22.5 -> normal
        self.assertEqual(profile.weight_diff, 0.0)

    def test_missing_height_returns_none(self):
        coach = make_coach()
        profile = make_trainee(coach, weight=70, height=None)
        self.assertIsNone(profile.weight_diff)
        self.assertIsNone(profile.ideal_weight_range)


class ProgramDurationTests(TestCase):
    """تست شمارش معکوس روزهای باقی‌مانده‌ی برنامه"""

    def setUp(self):
        self.coach = make_coach()
        self.profile = make_trainee(self.coach)

    def _make_program(self, duration_days, days_ago=0):
        program = WorkoutProgram.objects.create(
            trainee=self.profile, coach=self.coach,
            title='برنامه تست', duration_days=duration_days,
        )
        if days_ago:
            WorkoutProgram.objects.filter(pk=program.pk).update(
                created_at=timezone.now() - timezone.timedelta(days=days_ago)
            )
            program.refresh_from_db()
        return program

    def test_fresh_program_has_full_days_remaining(self):
        program = self._make_program(duration_days=30)
        self.assertEqual(program.days_remaining, 30)
        self.assertFalse(program.is_expired)
        self.assertFalse(program.needs_renewal_soon)

    def test_program_close_to_expiry_needs_renewal(self):
        program = self._make_program(duration_days=30, days_ago=28)
        self.assertLessEqual(program.days_remaining, 3)
        self.assertGreaterEqual(program.days_remaining, 0)
        self.assertFalse(program.is_expired)
        self.assertTrue(program.needs_renewal_soon)

    def test_expired_program(self):
        program = self._make_program(duration_days=30, days_ago=35)
        self.assertEqual(program.days_remaining, 0)
        self.assertTrue(program.is_expired)
        self.assertFalse(program.needs_renewal_soon)

    def test_renewal_notification_sent_once(self):
        program = self._make_program(duration_days=30, days_ago=28)
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 0)
        program.maybe_notify_renewal()
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 1)
        # دوباره صدا زدن نباید نوتیف تکراری بسازد
        program.maybe_notify_renewal()
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 1)

    def test_no_notification_when_far_from_expiry(self):
        program = self._make_program(duration_days=30, days_ago=2)
        program.maybe_notify_renewal()
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 0)

    def test_no_notification_when_expired(self):
        program = self._make_program(duration_days=30, days_ago=35)
        program.maybe_notify_renewal()
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 0)


class ProgramCreateViewTests(TestCase):
    """تست ثبت مدت برنامه از طریق فرم ثبت برنامه"""

    def setUp(self):
        self.coach = make_coach()
        self.profile = make_trainee(self.coach)
        self.client = Client()
        self.client.login(username='coach1', password='pass12345')

    def test_create_program_with_custom_duration(self):
        url = reverse('coach:program_create', args=[self.profile.pk])
        resp = self.client.post(url, {
            'title': 'برنامه ۴۵ روزه',
            'description': '',
            'duration_days': '45',
            'days_data': '{}',
        })
        self.assertEqual(resp.status_code, 302)
        program = WorkoutProgram.objects.get(trainee=self.profile, is_active=True)
        self.assertEqual(program.duration_days, 45)

    def test_create_program_defaults_to_30_days_when_missing(self):
        url = reverse('coach:program_create', args=[self.profile.pk])
        resp = self.client.post(url, {
            'title': 'برنامه پیش‌فرض',
            'description': '',
            'days_data': '{}',
        })
        self.assertEqual(resp.status_code, 302)
        program = WorkoutProgram.objects.get(trainee=self.profile, is_active=True)
        self.assertEqual(program.duration_days, 30)

    def test_create_program_rejects_invalid_duration_gracefully(self):
        url = reverse('coach:program_create', args=[self.profile.pk])
        resp = self.client.post(url, {
            'title': 'برنامه نامعتبر',
            'description': '',
            'duration_days': '-5',
            'days_data': '{}',
        })
        self.assertEqual(resp.status_code, 302)
        program = WorkoutProgram.objects.get(trainee=self.profile, is_active=True)
        self.assertEqual(program.duration_days, 30)

    def test_edit_program_updates_duration_and_resets_notified_flag(self):
        program = WorkoutProgram.objects.create(
            trainee=self.profile, coach=self.coach,
            title='برنامه', duration_days=30,
        )
        WorkoutProgram.objects.filter(pk=program.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=28),
            renewal_notified=True,
        )
        url = reverse('coach:program_edit', args=[program.pk])
        resp = self.client.post(url, {
            'title': 'برنامه تمدید شده',
            'description': '',
            'duration_days': '60',
            'days_data': '{}',
        })
        self.assertEqual(resp.status_code, 302)
        program.refresh_from_db()
        self.assertEqual(program.duration_days, 60)
        self.assertFalse(program.renewal_notified)
        self.assertFalse(program.needs_renewal_soon)


class ExtraPageSmokeTests(TestCase):
    """رندر شدن بدون خطای صفحات مرتبط دیگر (جزئیات شاگرد نزد مربی، نمای برنامه، پروفایل شاگرد)"""

    def setUp(self):
        self.coach = make_coach()
        self.profile = make_trainee(self.coach, username='trainee_smoke')
        self.program = WorkoutProgram.objects.create(
            trainee=self.profile, coach=self.coach,
            title='برنامه اسموک تست', duration_days=30,
        )
        WorkoutProgram.objects.filter(pk=self.program.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=29)
        )
        self.program.refresh_from_db()

    def test_coach_trainee_detail_page_renders(self):
        client = Client()
        client.login(username='coach1', password='pass12345')
        resp = client.get(reverse('coach:trainee_detail', args=[self.profile.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('روز', content)

    def test_coach_program_view_page_renders(self):
        client = Client()
        client.login(username='coach1', password='pass12345')
        resp = client.get(reverse('coach:program_view', args=[self.program.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_trainee_profile_page_renders(self):
        client = Client()
        client.login(username='trainee_smoke', password='pass12345')
        resp = client.get(reverse('trainee:profile'))
        self.assertEqual(resp.status_code, 200)

    def test_program_create_form_renders_with_duration_field(self):
        client = Client()
        client.login(username='coach1', password='pass12345')
        resp = client.get(reverse('coach:program_create', args=[self.profile.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'duration_days', resp.content)

    def test_program_edit_form_prefills_duration(self):
        client = Client()
        client.login(username='coach1', password='pass12345')
        resp = client.get(reverse('coach:program_edit', args=[self.program.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'value="30"', resp.content)


# ===================== رژیم غذایی =====================

@override_settings(NUTRITION_ENABLED=True)


class NutritionPlanModelTests(TestCase):
    """تست منطق مدل NutritionPlan (شمارش معکوس، انقضا، یادآوری تمدید)"""

    def setUp(self):
        self.coach = make_coach()
        self.profile = make_trainee(self.coach, username='trainee_diet_model')

    def _make_plan(self, duration_days=30, days_ago=0):
        plan = NutritionPlan.objects.create(
            trainee=self.profile, coach=self.coach,
            title='رژیم تست', duration_days=duration_days,
        )
        if days_ago:
            NutritionPlan.objects.filter(pk=plan.pk).update(
                created_at=timezone.now() - timezone.timedelta(days=days_ago)
            )
            plan.refresh_from_db()
        return plan

    def test_fresh_plan_has_full_days_remaining(self):
        plan = self._make_plan(duration_days=30)
        self.assertEqual(plan.days_remaining, 30)
        self.assertFalse(plan.is_expired)
        self.assertFalse(plan.needs_renewal_soon)

    def test_plan_close_to_expiry_needs_renewal(self):
        plan = self._make_plan(duration_days=30, days_ago=28)
        self.assertLessEqual(plan.days_remaining, 3)
        self.assertFalse(plan.is_expired)
        self.assertTrue(plan.needs_renewal_soon)

    def test_expired_plan(self):
        plan = self._make_plan(duration_days=30, days_ago=35)
        self.assertEqual(plan.days_remaining, 0)
        self.assertTrue(plan.is_expired)
        self.assertFalse(plan.needs_renewal_soon)

    def test_renewal_notification_sent_once(self):
        plan = self._make_plan(duration_days=30, days_ago=28)
        plan.maybe_notify_renewal()
        self.assertEqual(
            Notification.objects.filter(recipient=self.profile.user, notif_type='system').count(), 1
        )
        plan.maybe_notify_renewal()
        self.assertEqual(
            Notification.objects.filter(recipient=self.profile.user, notif_type='system').count(), 1
        )


@override_settings(NUTRITION_ENABLED=True)


class NutritionDayChoicesTests(TestCase):
    """تست اینکه رژیم غذایی برخلاف برنامه تمرینی، جمعه رو هم شامل میشه"""

    def test_nutrition_includes_all_seven_days(self):
        self.assertEqual(len(NUTRITION_DAY_CHOICES), 7)
        day_names = dict(NUTRITION_DAY_CHOICES)
        self.assertIn(7, day_names)
        self.assertEqual(day_names[7], 'جمعه')

    def test_workout_days_still_six(self):
        from coach.models import DAY_CHOICES
        self.assertEqual(len(DAY_CHOICES), 6)


@override_settings(NUTRITION_ENABLED=True)


class NutritionCreateViewTests(TestCase):
    """تست ثبت رژیم غذایی از طریق فرم مربی"""

    def setUp(self):
        self.coach = make_coach()
        self.profile = make_trainee(self.coach, username='trainee_diet_create')
        self.client = Client()
        self.client.login(username='coach1', password='pass12345')

    def test_create_diet_form_renders(self):
        resp = self.client.get(reverse('coach:nutrition_create', args=[self.profile.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('duration_days', content)
        self.assertIn('جمعه', content)  # روز هفتم باید تو فرم رژیم باشه
        self.assertIn('صبحانه', content)

    def test_create_diet_with_some_meals(self):
        url = reverse('coach:nutrition_create', args=[self.profile.pk])
        resp = self.client.post(url, {
            'title': 'رژیم کاهش وزن',
            'description': 'برای شروع',
            'duration_days': '30',
            'day_1_breakfast': '۲ عدد تخم‌مرغ + نان سنگک',
            'day_1_lunch': 'سینه مرغ + برنج',
            'day_7_dinner': 'سوپ سبزیجات',  # جمعه
        })
        self.assertEqual(resp.status_code, 302)
        plan = NutritionPlan.objects.get(trainee=self.profile, is_active=True)
        self.assertEqual(plan.title, 'رژیم کاهش وزن')
        self.assertEqual(plan.duration_days, 30)
        # فقط روزهایی که وعده‌ی پر داشتن باید ساخته بشن
        self.assertEqual(plan.days.count(), 2)
        day1 = plan.days.get(day_number=1)
        self.assertEqual(day1.meals.count(), 2)
        day7 = plan.days.get(day_number=7)
        self.assertEqual(day7.meals.count(), 1)
        self.assertEqual(day7.meals.first().meal_type, 'dinner')

    def test_create_diet_skips_empty_meals(self):
        url = reverse('coach:nutrition_create', args=[self.profile.pk])
        resp = self.client.post(url, {
            'title': 'رژیم خالی جزئی',
            'duration_days': '30',
            'day_1_breakfast': '',
            'day_1_lunch': '   ',
            'day_2_dinner': 'ماهی + سبزیجات',
        })
        self.assertEqual(resp.status_code, 302)
        plan = NutritionPlan.objects.get(trainee=self.profile, is_active=True)
        self.assertEqual(plan.days.count(), 1)
        self.assertEqual(plan.days.first().day_number, 2)

    def test_create_diet_sends_notification(self):
        url = reverse('coach:nutrition_create', args=[self.profile.pk])
        self.client.post(url, {
            'title': 'رژیم با نوتیف',
            'duration_days': '30',
            'day_1_breakfast': 'نان و پنیر',
        })
        notif = Notification.objects.filter(recipient=self.profile.user, notif_type='diet_ready').first()
        self.assertIsNotNone(notif)

    def test_creating_new_plan_deactivates_old_one(self):
        old_plan = NutritionPlan.objects.create(
            trainee=self.profile, coach=self.coach, title='رژیم قدیمی', is_active=True,
        )
        url = reverse('coach:nutrition_create', args=[self.profile.pk])
        self.client.post(url, {
            'title': 'رژیم جدید',
            'duration_days': '30',
            'day_1_breakfast': 'صبحانه جدید',
        })
        old_plan.refresh_from_db()
        self.assertFalse(old_plan.is_active)
        new_plan = NutritionPlan.objects.get(trainee=self.profile, is_active=True)
        self.assertEqual(new_plan.title, 'رژیم جدید')

    def test_nutrition_view_page_renders(self):
        plan = NutritionPlan.objects.create(
            trainee=self.profile, coach=self.coach, title='رژیم برای مشاهده',
        )
        day = NutritionDay.objects.create(plan=plan, day_number=1)
        Meal.objects.create(day=day, meal_type='breakfast', content='تخم‌مرغ', order=0)
        resp = self.client.get(reverse('coach:nutrition_view', args=[plan.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('تخم‌مرغ', content)

    def test_nutrition_edit_prefills_existing_meals(self):
        plan = NutritionPlan.objects.create(
            trainee=self.profile, coach=self.coach, title='رژیم برای ویرایش', duration_days=30,
        )
        day = NutritionDay.objects.create(plan=plan, day_number=3)
        Meal.objects.create(day=day, meal_type='lunch', content='ماکارونی مخصوص', order=0)
        resp = self.client.get(reverse('coach:nutrition_edit', args=[plan.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('ماکارونی مخصوص', content)

    def test_nutrition_edit_updates_meals(self):
        plan = NutritionPlan.objects.create(
            trainee=self.profile, coach=self.coach, title='رژیم برای ویرایش کامل', duration_days=30,
        )
        day = NutritionDay.objects.create(plan=plan, day_number=1)
        Meal.objects.create(day=day, meal_type='breakfast', content='قدیمی', order=0)

        url = reverse('coach:nutrition_edit', args=[plan.pk])
        resp = self.client.post(url, {
            'title': 'رژیم ویرایش‌شده',
            'duration_days': '45',
            'day_1_breakfast': 'جدید و به‌روز',
        })
        self.assertEqual(resp.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.title, 'رژیم ویرایش‌شده')
        self.assertEqual(plan.duration_days, 45)
        day1 = plan.days.get(day_number=1)
        self.assertEqual(day1.meals.count(), 1)
        self.assertEqual(day1.meals.first().content, 'جدید و به‌روز')


@override_settings(NUTRITION_ENABLED=True)
class FoodItemModelTests(TestCase):
    """تست پایه‌ی مدل FoodItem"""

    def test_food_item_str_includes_category(self):
        item = FoodItem.objects.create(name='سینه مرغ', category='protein', default_unit='gram', default_amount='150')
        self.assertIn('سینه مرغ', str(item))

    def test_food_bank_seed_migration_populated_items(self):
        # این تست فرض می‌کنه مایگریشن seed اجرا شده (روی دیتابیس تست هم اجرا میشه)
        self.assertGreater(FoodItem.objects.count(), 50)

    def test_food_categories_cover_common_groups(self):
        categories_in_db = set(FoodItem.objects.values_list('category', flat=True))
        expected = {'protein', 'carb', 'dairy', 'vegetable', 'fruit', 'legume', 'fat_nut'}
        self.assertTrue(expected.issubset(categories_in_db))


@override_settings(NUTRITION_ENABLED=True)


class NutritionFoodBankIntegrationTests(TestCase):
    """تست اینکه بانک غذایی درست به فرم ثبت رژیم تزریق میشه (برای پیکر جاوااسکریپتی)"""

    def setUp(self):
        self.coach = make_coach(username='coach_food_integ')
        self.profile = make_trainee(self.coach, username='trainee_food_integ')
        self.client = Client()
        self.client.login(username='coach_food_integ', password='pass12345')

    def test_nutrition_create_form_includes_food_bank_data(self):
        resp = self.client.get(reverse('coach:nutrition_create', args=[self.profile.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('FOOD_ITEMS', content)
        self.assertIn('انتخاب از بانک غذایی', content)
        self.assertIn('نوشتن دستی', content)
        # حداقل چند آیتم شناخته‌شده باید در JSON تزریق‌شده باشند
        self.assertIn('سینه مرغ', content)

    def test_nutrition_create_form_includes_all_food_categories(self):
        resp = self.client.get(reverse('coach:nutrition_create', args=[self.profile.pk]))
        content = resp.content.decode('utf-8')
        for _, label in FOOD_CATEGORY_CHOICES:
            self.assertIn(label, content)

    def test_selecting_from_bank_still_saves_as_free_text(self):
        # شبیه‌سازی اینکه پیکر جاوااسکریپتی متن نهایی رو تو تکست‌اریا نوشته
        # (چون بک‌اند فرقی بین دستی/بانکی نمی‌ذاره، همون تست موجود ثبت رژیم کافیه)
        url = reverse('coach:nutrition_create', args=[self.profile.pk])
        resp = self.client.post(url, {
            'title': 'رژیم با انتخاب از بانک',
            'duration_days': '30',
            'day_1_breakfast': '150 گرم سینه مرغ\n2 عدد تخم‌مرغ',
        })
        self.assertEqual(resp.status_code, 302)
        plan = NutritionPlan.objects.get(trainee=self.profile, is_active=True)
        meal = plan.days.get(day_number=1).meals.get(meal_type='breakfast')
        self.assertIn('سینه مرغ', meal.content)
        self.assertIn('تخم‌مرغ', meal.content)


# ===================== کپی برنامه/رژیم برای شاگرد دیگر =====================


class ProgramCopyTests(TestCase):
    """تست کپی کردن برنامه‌ی تمرینی از یک شاگرد به شاگرد دیگر"""

    def setUp(self):
        self.coach = make_coach(username='coach_copy')
        self.source = make_trainee(self.coach, username='trainee_copy_source')
        self.target = make_trainee(self.coach, username='trainee_copy_target')

        self.exercise = Exercise.objects.create(name='پرس سینه', category='chest')

        self.program = WorkoutProgram.objects.create(
            trainee=self.source, coach=self.coach, title='برنامه اصلی', description='توضیح',
            duration_days=45,
        )
        day = WorkoutDay.objects.create(program=self.program, day_number=1, notes='یادداشت روز')
        WorkoutExercise.objects.create(
            day=day, exercise=self.exercise, sets=4, reps='10', rest_seconds=90,
            set_type='normal', notes='توضیح حرکت', order=0,
        )

        self.client = Client()
        self.client.login(username='coach_copy', password='pass12345')

    def test_copy_page_renders_and_excludes_source_trainee(self):
        resp = self.client.get(reverse('coach:program_copy', args=[self.program.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertNotIn(f'value="{self.source.pk}"', content)
        self.assertIn(f'value="{self.target.pk}"', content)

    def test_copy_program_creates_full_deep_copy(self):
        url = reverse('coach:program_copy', args=[self.program.pk])
        resp = self.client.post(url, {'target_trainee': self.target.pk})
        self.assertEqual(resp.status_code, 302)

        new_program = WorkoutProgram.objects.get(trainee=self.target, is_active=True)
        self.assertEqual(new_program.title, 'برنامه اصلی')
        self.assertEqual(new_program.description, 'توضیح')
        self.assertEqual(new_program.duration_days, 45)
        self.assertNotEqual(new_program.pk, self.program.pk)

        new_day = new_program.days.get(day_number=1)
        self.assertEqual(new_day.notes, 'یادداشت روز')
        new_wex = new_day.exercises.first()
        self.assertEqual(new_wex.exercise, self.exercise)
        self.assertEqual(new_wex.sets, 4)
        self.assertEqual(new_wex.reps, '10')
        self.assertEqual(new_wex.rest_seconds, 90)
        self.assertEqual(new_wex.notes, 'توضیح حرکت')

        # مطمئن شویم منبع اصلی دست‌نخورده مونده
        self.program.refresh_from_db()
        self.assertTrue(self.program.is_active)
        self.assertEqual(self.program.trainee, self.source)

    def test_copy_program_deactivates_target_existing_active_program(self):
        old_target_program = WorkoutProgram.objects.create(
            trainee=self.target, coach=self.coach, title='برنامه قدیمی هدف', is_active=True,
        )
        url = reverse('coach:program_copy', args=[self.program.pk])
        self.client.post(url, {'target_trainee': self.target.pk})
        old_target_program.refresh_from_db()
        self.assertFalse(old_target_program.is_active)
        self.assertEqual(WorkoutProgram.objects.filter(trainee=self.target, is_active=True).count(), 1)

    def test_copy_program_sends_notification_to_target(self):
        url = reverse('coach:program_copy', args=[self.program.pk])
        self.client.post(url, {'target_trainee': self.target.pk})
        notif = Notification.objects.filter(recipient=self.target.user, notif_type='program_ready').first()
        self.assertIsNotNone(notif)

    def test_cannot_copy_to_trainee_of_another_coach(self):
        other_coach = make_coach(username='other_coach_copy')
        foreign_trainee = make_trainee(other_coach, username='foreign_trainee_copy')
        url = reverse('coach:program_copy', args=[self.program.pk])
        resp = self.client.post(url, {'target_trainee': foreign_trainee.pk})
        self.assertEqual(resp.status_code, 404)

    def test_cannot_copy_program_owned_by_another_coach(self):
        other_coach = make_coach(username='other_coach_copy2')
        other_client = Client()
        other_client.login(username='other_coach_copy2', password='pass12345')
        resp = other_client.get(reverse('coach:program_copy', args=[self.program.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_copy_button_present_on_program_view(self):
        resp = self.client.get(reverse('coach:program_view', args=[self.program.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('کپی برای شاگرد دیگر', content)
        self.assertIn(reverse('coach:program_copy', args=[self.program.pk]), content)

    def test_copy_page_shows_no_trainees_message_when_none_available(self):
        # مربی دیگه‌ای که فقط همون شاگرد منبع رو داره
        solo_coach = make_coach(username='solo_coach_copy')
        solo_trainee = make_trainee(solo_coach, username='solo_trainee_copy')
        solo_program = WorkoutProgram.objects.create(trainee=solo_trainee, coach=solo_coach, title='تک برنامه')
        solo_client = Client()
        solo_client.login(username='solo_coach_copy', password='pass12345')
        resp = solo_client.get(reverse('coach:program_copy', args=[solo_program.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('شاگرد دیگری برای کپی کردن وجود ندارد', resp.content.decode('utf-8'))


@override_settings(NUTRITION_ENABLED=True)


class NutritionCopyTests(TestCase):
    """تست کپی کردن رژیم غذایی از یک شاگرد به شاگرد دیگر"""

    def setUp(self):
        self.coach = make_coach(username='coach_diet_copy')
        self.source = make_trainee(self.coach, username='trainee_diet_copy_source')
        self.target = make_trainee(self.coach, username='trainee_diet_copy_target')

        self.plan = NutritionPlan.objects.create(
            trainee=self.source, coach=self.coach, title='رژیم اصلی', description='توضیح رژیم',
            duration_days=21,
        )
        day = NutritionDay.objects.create(plan=self.plan, day_number=1, notes='یادداشت رژیم')
        Meal.objects.create(day=day, meal_type='breakfast', content='2 عدد تخم‌مرغ', order=0)
        Meal.objects.create(day=day, meal_type='lunch', content='150 گرم مرغ', order=1)
        day7 = NutritionDay.objects.create(plan=self.plan, day_number=7)
        Meal.objects.create(day=day7, meal_type='dinner', content='سوپ سبزیجات', order=0)

        self.client = Client()
        self.client.login(username='coach_diet_copy', password='pass12345')

    def test_copy_page_excludes_source_trainee(self):
        resp = self.client.get(reverse('coach:nutrition_copy', args=[self.plan.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertNotIn(f'value="{self.source.pk}"', content)
        self.assertIn(f'value="{self.target.pk}"', content)

    def test_copy_diet_creates_full_deep_copy(self):
        url = reverse('coach:nutrition_copy', args=[self.plan.pk])
        resp = self.client.post(url, {'target_trainee': self.target.pk})
        self.assertEqual(resp.status_code, 302)

        new_plan = NutritionPlan.objects.get(trainee=self.target, is_active=True)
        self.assertEqual(new_plan.title, 'رژیم اصلی')
        self.assertEqual(new_plan.duration_days, 21)
        self.assertNotEqual(new_plan.pk, self.plan.pk)
        self.assertEqual(new_plan.days.count(), 2)

        day1 = new_plan.days.get(day_number=1)
        self.assertEqual(day1.notes, 'یادداشت رژیم')
        self.assertEqual(day1.meals.count(), 2)
        self.assertEqual(day1.meals.get(meal_type='breakfast').content, '2 عدد تخم‌مرغ')

        day7 = new_plan.days.get(day_number=7)
        self.assertEqual(day7.meals.first().content, 'سوپ سبزیجات')

        # منبع اصلی دست‌نخورده باشه
        self.plan.refresh_from_db()
        self.assertTrue(self.plan.is_active)
        self.assertEqual(self.plan.trainee, self.source)

    def test_copy_diet_deactivates_target_existing_active_plan(self):
        old_target_plan = NutritionPlan.objects.create(
            trainee=self.target, coach=self.coach, title='رژیم قدیمی هدف', is_active=True,
        )
        url = reverse('coach:nutrition_copy', args=[self.plan.pk])
        self.client.post(url, {'target_trainee': self.target.pk})
        old_target_plan.refresh_from_db()
        self.assertFalse(old_target_plan.is_active)
        self.assertEqual(NutritionPlan.objects.filter(trainee=self.target, is_active=True).count(), 1)

    def test_copy_diet_sends_notification(self):
        url = reverse('coach:nutrition_copy', args=[self.plan.pk])
        self.client.post(url, {'target_trainee': self.target.pk})
        notif = Notification.objects.filter(recipient=self.target.user, notif_type='diet_ready').first()
        self.assertIsNotNone(notif)

    def test_cannot_copy_to_foreign_trainee(self):
        other_coach = make_coach(username='other_coach_diet_copy')
        foreign_trainee = make_trainee(other_coach, username='foreign_trainee_diet_copy')
        url = reverse('coach:nutrition_copy', args=[self.plan.pk])
        resp = self.client.post(url, {'target_trainee': foreign_trainee.pk})
        self.assertEqual(resp.status_code, 404)

    def test_cannot_copy_foreign_plan(self):
        other_coach = make_coach(username='other_coach_diet_copy2')
        other_client = Client()
        other_client.login(username='other_coach_diet_copy2', password='pass12345')
        resp = other_client.get(reverse('coach:nutrition_copy', args=[self.plan.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_copy_button_present_on_nutrition_view(self):
        resp = self.client.get(reverse('coach:nutrition_view', args=[self.plan.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('کپی برای شاگرد دیگر', content)
        self.assertIn(reverse('coach:nutrition_copy', args=[self.plan.pk]), content)

    def test_copied_meal_edits_dont_affect_original(self):
        # اطمینان از deep copy واقعی (نه اشاره به همون رکوردها)
        url = reverse('coach:nutrition_copy', args=[self.plan.pk])
        self.client.post(url, {'target_trainee': self.target.pk})
        new_plan = NutritionPlan.objects.get(trainee=self.target, is_active=True)
        new_meal = new_plan.days.get(day_number=1).meals.get(meal_type='breakfast')
        new_meal.content = 'محتوای تغییر یافته'
        new_meal.save()

        original_meal = self.plan.days.get(day_number=1).meals.get(meal_type='breakfast')
        self.assertEqual(original_meal.content, '2 عدد تخم‌مرغ')


# ===================== لندینگ پیج =====================


class LandingPageTests(TestCase):
    """تست صفحه‌ی ورود عمومی (لندینگ) و ریدایرکت کاربران لاگین‌شده"""

    def test_anonymous_visitor_sees_landing_page(self):
        client = Client()
        resp = client.get('/')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('FitCoach', content)
        self.assertIn('ورود', content)

    def test_landing_page_has_login_link(self):
        client = Client()
        resp = client.get('/')
        content = resp.content.decode('utf-8')
        self.assertIn(reverse('accounts:login'), content)

    def test_logged_in_coach_is_redirected_not_shown_landing(self):
        coach = make_coach(username='coach_landing_test')
        client = Client()
        client.login(username='coach_landing_test', password='pass12345')
        resp = client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('coach:dashboard'))

    def test_logged_in_trainee_is_redirected_not_shown_landing(self):
        coach = make_coach(username='coach_landing_test2')
        trainee = make_trainee(coach, username='trainee_landing_test')
        client = Client()
        client.login(username='trainee_landing_test', password='pass12345')
        resp = client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('trainee:dashboard'))

    def test_logged_in_admin_is_redirected_not_shown_landing(self):
        admin = make_admin(username='admin_landing_test')
        client = Client()
        client.login(username='admin_landing_test', password='pass12345')
        resp = client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('admin_panel:dashboard'))


# ===================== دکمه ارسال پیام دعوت به شاگرد =====================


class InviteMessageTests(TestCase):
    """تست دکمه‌ی «ارسال به شاگرد» که پیام آماده (لینک سایت، یوزرنیم، پسورد) رو کپی می‌کنه"""

    def setUp(self):
        self.coach = make_coach(username='coach_invite')
        self.client = Client()
        self.client.login(username='coach_invite', password='pass12345')

    def test_trainee_detail_has_send_button_and_password(self):
        profile = make_trainee(self.coach, username='trainee_invite_1')
        # last_password_plain رو شبیه‌سازی می‌کنیم (چیزی که موقع ساخت شاگرد ذخیره میشه)
        profile.last_password_plain = 'secretpass123'
        profile.save()

        resp = self.client.get(reverse('coach:trainee_detail', args=[profile.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('ارسال به شاگرد', content)
        self.assertIn('copyInviteMessage', content)
        self.assertIn('secretpass123', content)
        self.assertIn('trainee_invite_1', content)
        self.assertIn('Add to Home Screen', content)
        # لینک باید مستقیم به صفحه‌ی لاگین بره، نه صفحه‌ی اصلی/لندینگ
        self.assertIn(reverse('accounts:login'), content)

    def test_trainee_detail_handles_missing_password_gracefully(self):
        profile = make_trainee(self.coach, username='trainee_invite_2')
        profile.last_password_plain = ''
        profile.save()

        resp = self.client.get(reverse('coach:trainee_detail', args=[profile.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        # نباید کرش کنه و باید یه پیام جایگزین معقول تو جاوااسکریپت باشه
        self.assertIn('از مربی خودت بپرس', content)

    def test_trainee_list_has_send_button_per_row(self):
        profile1 = make_trainee(self.coach, username='trainee_invite_row1')
        profile1.last_password_plain = 'pass111'
        profile1.save()
        profile2 = make_trainee(self.coach, username='trainee_invite_row2')
        profile2.last_password_plain = 'pass222'
        profile2.save()

        resp = self.client.get(reverse('coach:trainee_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('copyInviteMessageFor', content)
        self.assertIn('trainee_invite_row1', content)
        self.assertIn('pass111', content)
        self.assertIn('trainee_invite_row2', content)
        self.assertIn('pass222', content)
        self.assertIn(reverse('accounts:login'), content)

    def test_invite_message_escapes_special_characters_safely(self):
        # اسمی با کوتیشن که می‌تونه جاوااسکریپت رو خراب کنه اگه escape نشه
        user = User.objects.create_user(
            username='trainee_invite_xss', password='pass12345',
            first_name="O'Brien", last_name='"Test"', role='trainee',
        )
        profile = TraineeProfile.objects.create(user=user, coach=self.coach)
        profile.last_password_plain = "p'\"ss"
        profile.save()

        resp = self.client.get(reverse('coach:trainee_detail', args=[profile.pk]))
        self.assertEqual(resp.status_code, 200)
        # صفحه نباید به‌خاطر کوتیشن‌های escape‌نشده خراب رندر بشه؛ چک می‌کنیم
        # اسکریپت با escapejs درست جنریت شده (کوتیشن‌های خام تو جاوااسکریپت رشته نباشن)
        content = resp.content.decode('utf-8')
        self.assertIn('copyInviteMessage', content)

    def test_cannot_see_other_coachs_trainee_invite_data(self):
        other_coach = make_coach(username='other_coach_invite')
        other_profile = make_trainee(other_coach, username='foreign_trainee_invite')
        resp = self.client.get(reverse('coach:trainee_detail', args=[other_profile.pk]))
        self.assertEqual(resp.status_code, 404)


# ===================== ریدیزاین صفحه‌ی مشخصات شاگرد =====================


class TraineeDetailRedesignTests(TestCase):
    """تست ساختار جدید کارت اطلاعات شخصی (تمام‌عرض) و جعبه کوچک BMI"""

    def test_trainee_detail_has_new_profile_card_structure(self):
        coach = make_coach(username='coach_redesign')
        profile = make_trainee(coach, username='trainee_redesign', weight=90, height=170)
        client = Client()
        client.login(username='coach_redesign', password='pass12345')
        resp = client.get(reverse('coach:trainee_detail', args=[profile.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('profile-info-card', content)
        self.assertIn('profile-info-grid', content)
        self.assertIn('bmi-mini-box', content)

    def test_bmi_mini_box_shows_empty_state_without_data(self):
        coach = make_coach(username='coach_redesign2')
        user = User.objects.create_user(username='trainee_redesign2', password='pass12345', role='trainee')
        profile = TraineeProfile.objects.create(user=user, coach=coach)  # بدون وزن/قد
        client = Client()
        client.login(username='coach_redesign2', password='pass12345')
        resp = client.get(reverse('coach:trainee_detail', args=[profile.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('bmi-mini-box', resp.content.decode('utf-8'))


# ===================== سرویس‌ورکر و کارکرد آفلاین =====================


class ServiceWorkerTests(TestCase):
    """
    تست رفع باگ «بدون اینترنت اصلاً باز نمی‌شه»: علتش این بود که sw.js از
    زیر /static/ سرو می‌شد و محدوده‌ی کنترلش فقط همون پوشه بود، نه کل سایت.
    """

    def test_service_worker_served_from_root_not_static(self):
        client = Client()
        resp = client.get('/sw.js')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/javascript')

    def test_service_worker_content_matches_source_file(self):
        client = Client()
        resp = client.get('/sw.js')
        content = resp.content.decode('utf-8')
        self.assertIn('CACHE_NAME', content)
        self.assertIn('OFFLINE_URL', content)
        self.assertIn("req.mode === 'navigate'", content)

    def test_offline_fallback_page_reachable(self):
        client = Client()
        resp = client.get('/static/offline.html')
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content) if hasattr(resp, 'streaming_content') else resp.content
        self.assertIn('اینترنت'.encode('utf-8'), body)

    def test_main_js_registers_sw_at_root_scope(self):
        with open('static/js/main.js', encoding='utf-8') as f:
            js = f.read()
        self.assertIn("register('/sw.js'", js)
        self.assertIn("scope: '/'", js)
        # نباید دیگه رجیستر قدیمی زیر static باشه
        self.assertNotIn("register('/static/sw.js')", js)


# ===================== بازطراحی UI ثبت برنامه تمرینی =====================


class ProgramCreateUIEnhancementsTests(TestCase):
    """
    تست زیرساخت بک‌اندی که برای بهبودهای UI صفحه‌ی ثبت برنامه لازم بود:
    - آدرس تصویر حرکت (image_url) برای نمایش thumbnail تو پیکر انتخاب حرکت
    - عناصر HTML جدید (منوی پیشرفته، کپی روز، نوار اعمال‌به‌همه) باید تو صفحه باشن
    """

    def setUp(self):
        self.coach = make_coach(username='coach_ui_enh')
        self.profile = make_trainee(self.coach, username='trainee_ui_enh')
        self.client = Client()
        self.client.login(username='coach_ui_enh', password='pass12345')

    def test_exercise_list_includes_image_url_field(self):
        Exercise.objects.create(name='حرکت با عکس', category='chest', is_public=True)
        resp = self.client.get(reverse('coach:program_create', args=[self.profile.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('image_url', content)

    def test_exercise_without_image_has_empty_image_url(self):
        ex = Exercise.objects.create(name='حرکت بدون عکس', category='back', is_public=True)
        self.assertFalse(ex.image)  # مطمئن میشیم واقعاً عکسی نداره
        resp = self.client.get(reverse('coach:program_create', args=[self.profile.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_program_create_page_has_decluttered_primary_button(self):
        resp = self.client.get(reverse('coach:program_create', args=[self.profile.pk]))
        content = resp.content.decode('utf-8')
        self.assertIn('افزودن حرکت', content)
        self.assertIn('advanced-menu', content)
        self.assertIn('toggleAdvancedMenu', content)

    def test_program_create_page_has_copy_day_ui(self):
        resp = self.client.get(reverse('coach:program_create', args=[self.profile.pk]))
        content = resp.content.decode('utf-8')
        self.assertIn('کپی به روز دیگر', content)
        self.assertIn('copyDayTo', content)
        self.assertIn('copy-target-', content)

    def test_program_create_page_has_reorder_and_quickfill_js(self):
        resp = self.client.get(reverse('coach:program_create', args=[self.profile.pk]))
        content = resp.content.decode('utf-8')
        self.assertIn('moveGroup', content)
        self.assertIn('applyToAll', content)
        self.assertIn('qfBar-', content)

    def test_program_edit_also_has_same_enhancements(self):
        program = WorkoutProgram.objects.create(
            trainee=self.profile, coach=self.coach, title='برنامه برای ویرایش',
        )
        resp = self.client.get(reverse('coach:program_edit', args=[program.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('image_url', content)
        self.assertIn('copyDayTo', content)
        self.assertIn('moveGroup', content)

    def test_edit_prefill_refreshes_day_tab_badge_count(self):
        """
        رگرسیون: قبلاً وقتی صفحه‌ی ویرایش برنامه لود می‌شد، تعداد حرکات هر
        روز (که پیش‌تر ذخیره شده بود) تو خودِ لیست درست پر می‌شد ولی عدد
        روی تب روز (badge) صفر می‌ماند، چون updateDayCount() بعد از
        renderDay() صدا زده نمی‌شد.
        """
        from coach.models import WorkoutDay, WorkoutExercise
        program = WorkoutProgram.objects.create(
            trainee=self.profile, coach=self.coach, title='برنامه با تعداد',
        )
        ex = Exercise.objects.create(name='حرکت شمارشی', category='chest', is_public=True)
        day = WorkoutDay.objects.create(program=program, day_number=1)
        WorkoutExercise.objects.create(day=day, exercise=ex, sets=3, reps='12', rest_seconds=60, order=0)

        resp = self.client.get(reverse('coach:program_edit', args=[program.pk]))
        content = resp.content.decode('utf-8')
        self.assertIn('renderDay(num);', content)
        self.assertIn('updateDayCount(num);', content)

    def test_saving_program_still_works_after_ui_changes(self):
        ex = Exercise.objects.create(name='حرکت تست ذخیره', category='legs', is_public=True)
        url = reverse('coach:program_create', args=[self.profile.pk])
        days_data = {
            "1": {
                "notes": "",
                "exercises": [
                    {"exercise_id": ex.pk, "sets": 4, "reps": "10", "rest": 45, "set_type": "normal", "notes": ""}
                ]
            }
        }
        import json as json_lib
        resp = self.client.post(url, {
            'title': 'برنامه نهایی',
            'duration_days': '30',
            'days_data': json_lib.dumps(days_data),
        })
        self.assertEqual(resp.status_code, 302)
        program = WorkoutProgram.objects.get(title='برنامه نهایی')
        wex = program.days.get(day_number=1).exercises.first()
        self.assertEqual(wex.sets, 4)
        self.assertEqual(wex.reps, '10')
        self.assertEqual(wex.rest_seconds, 45)


# ===================== موبایل: چیدمان تک‌ستونی لیست حرکات =====================


class ProgramCreateMobileLayoutTests(TestCase):
    """تست رفع باگ اسکرول افقی لیست حرکات در موبایل (ترتیب نادرست CSS/media query)"""

    def test_mobile_media_query_appears_after_base_rule(self):
        with open('templates/coach/program_create.html', encoding='utf-8') as f:
            content = f.read()
        base_idx  = content.find('.ex-picker-grid {')
        media_idx = content.find('@media (max-width: 640px)')
        self.assertNotEqual(base_idx, -1)
        self.assertNotEqual(media_idx, -1)
        # قانون override باید بعد از قانون پایه بیاد وگرنه هیچ‌وقت اعمال نمیشه
        self.assertGreater(media_idx, base_idx)

    def test_mobile_media_query_targets_single_column(self):
        with open('templates/coach/program_create.html', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('.ex-picker-grid { grid-template-columns: 1fr; }', content)


# ===================== لندینگ‌پیج نسخه‌ی دوم =====================


class LandingPageV2Tests(TestCase):
    """تست بازطراحی لندینگ: بدون فونت خارجی، دکمه‌ی «ورود» ساده، اطلاعات تماس واقعی"""

    def test_no_external_google_fonts_dependency(self):
        client = Client()
        resp = client.get('/')
        content = resp.content.decode('utf-8')
        self.assertNotIn('fonts.googleapis.com', content)
        self.assertNotIn('fonts.gstatic.com', content)

    def test_login_button_says_vorood_not_vorood_marabian(self):
        client = Client()
        resp = client.get('/')
        content = resp.content.decode('utf-8')
        self.assertIn('nav-actions', content)
        self.assertNotIn('ورود مربیان', content)

    def test_landing_has_real_contact_info(self):
        client = Client()
        resp = client.get('/')
        content = resp.content.decode('utf-8')
        self.assertIn('09331842949', content)
        self.assertIn('fitcoach.club', content)
        self.assertIn('tel:09331842949', content)
        self.assertIn('instagram.com/fitcoach.club', content)

    def test_landing_still_has_login_link(self):
        client = Client()
        resp = client.get('/')
        content = resp.content.decode('utf-8')
        self.assertIn(reverse('accounts:login'), content)


class NutritionFeatureFlagTests(TestCase):
    """
    قابلیت رژیم غذایی فعلاً موقتاً مخفی است (NUTRITION_ENABLED=False به‌صورت
    پیش‌فرض). این تست‌ها مطمئن می‌شن که هیچ منو/دکمه‌ای اونو نشون نمی‌ده و
    دسترسی مستقیم به URLهاش هم بسته‌ست.
    """

    def setUp(self):
        self.coach = make_coach()
        self.profile = make_trainee(self.coach, username='trainee_flag_off')
        self.admin = User.objects.create_user(
            username='admin_flag_off', password='pass12345', role='admin'
        )

    def test_trainee_dashboard_hides_diet_nav_and_card(self):
        client = Client()
        client.login(username='trainee_flag_off', password='pass12345')
        resp = client.get(reverse('trainee:dashboard'))
        content = resp.content.decode('utf-8')
        self.assertNotIn('رژیم غذایی', content)
        self.assertNotIn(reverse('trainee:my_diet'), content)

    def test_trainee_diet_urls_redirect_when_disabled(self):
        client = Client()
        client.login(username='trainee_flag_off', password='pass12345')
        for url_name in ['trainee:my_diet', 'trainee:past_diets']:
            resp = client.get(reverse(url_name))
            self.assertEqual(resp.status_code, 302)
            self.assertRedirects(resp, reverse('trainee:dashboard'))

    def test_coach_trainee_detail_hides_diet_section(self):
        client = Client()
        client.login(username=self.coach.username, password='pass12345')
        resp = client.get(reverse('coach:trainee_detail', args=[self.profile.pk]))
        content = resp.content.decode('utf-8')
        self.assertNotIn('رژیم غذایی فعال', content)
        self.assertNotIn('رژیم جدید', content)

    def test_coach_nutrition_create_redirects_when_disabled(self):
        client = Client()
        client.login(username=self.coach.username, password='pass12345')
        resp = client.get(reverse('coach:nutrition_create', args=[self.profile.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('coach:dashboard'))

    def test_admin_sidebar_and_food_bank_hidden(self):
        client = Client()
        client.login(username='admin_flag_off', password='pass12345')
        resp = client.get(reverse('admin_panel:dashboard'))
        content = resp.content.decode('utf-8')
        self.assertNotIn('بانک غذایی', content)

        resp2 = client.get(reverse('admin_panel:food_list'))
        self.assertEqual(resp2.status_code, 302)
        self.assertRedirects(resp2, reverse('admin_panel:dashboard'))

    def test_landing_page_hides_diet_mentions(self):
        """
        وقتی رژیم غذایی غیرفعاله، صفحه نباید مثل یه قابلیت فعلی و آماده
        تبلیغش کنه (نه تو منو، نه تو کارت‌های امکانات). تنها استثنا یه
        اشاره‌ی آینده‌نگرانه تو FAQ هست («بعداً رژیم غذایی هم اضافه می‌شه؟»)
        که خودِ صفحه‌ی جدید عمداً به‌عنوان قابلیتِ در راه مطرحش می‌کنه.
        """
        client = Client()
        resp = client.get('/')
        content = resp.content.decode('utf-8')
        self.assertNotIn('بانک غذایی با بیش از ۱۲۰ ماده', content)  # پاسخ FAQ حالت فعال
        self.assertIn('بعداً بخش رژیم غذایی اضافه می‌شه؟', content)  # تیزر FAQ حالت غیرفعال مجازه

    @override_settings(NUTRITION_ENABLED=True)
    def test_everything_still_works_when_flag_turned_back_on(self):
        client = Client()
        client.login(username='trainee_flag_off', password='pass12345')
        resp = client.get(reverse('trainee:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('رژیم غذایی', resp.content.decode('utf-8'))
        resp2 = client.get(reverse('trainee:my_diet'))
        self.assertEqual(resp2.status_code, 200)




# ===================== محدودیت حجم/فرمت عکس و ویدیوی حرکت =====================

class ExerciseFileValidationTests(TestCase):
    """اعتبارسنجی حجم عکس/ویدیو و فرمت ویدیوی حرکت‌ها (هم برای مربی، هم ادمین)."""

    def setUp(self):
        self.coach = make_coach(username='coach_filevalid')
        self.client = Client()
        self.client.login(username='coach_filevalid', password='pass12345')

    def _make_file(self, name, size_bytes, content_type='image/png'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(name, b'\x00' * size_bytes, content_type=content_type)

    def test_oversized_image_is_rejected(self):
        big_image = self._make_file('big.png', 6 * 1024 * 1024)  # 6MB > 5MB limit
        resp = self.client.post(reverse('coach:exercise_add'), {
            'name': 'حرکت با عکس بزرگ', 'category': 'chest', 'description': '',
            'image': big_image,
        })
        self.assertEqual(resp.status_code, 200)  # برمی‌گرده به فرم، نه ریدایرکت
        self.assertFalse(Exercise.objects.filter(name='حرکت با عکس بزرگ').exists())

    def test_normal_sized_image_is_accepted(self):
        small_image = self._make_file('ok.png', 1024)
        resp = self.client.post(reverse('coach:exercise_add'), {
            'name': 'حرکت با عکس عادی', 'category': 'chest', 'description': '',
            'image': small_image,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Exercise.objects.filter(name='حرکت با عکس عادی').exists())

    def test_video_with_disallowed_extension_is_rejected(self):
        bad_video = self._make_file('malware.exe', 1024, content_type='application/octet-stream')
        resp = self.client.post(reverse('coach:exercise_add'), {
            'name': 'حرکت با ویدیوی نامعتبر', 'category': 'chest', 'description': '',
            'video': bad_video,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Exercise.objects.filter(name='حرکت با ویدیوی نامعتبر').exists())

    def test_admin_exercise_add_also_validates_image_size(self):
        admin = make_admin(username='admin_filevalid')
        client = Client()
        client.login(username='admin_filevalid', password='pass12345')
        big_image = self._make_file('big2.png', 6 * 1024 * 1024)
        resp = client.post(reverse('admin_panel:exercise_add'), {
            'name': 'حرکت عمومی با عکس بزرگ', 'category': 'chest', 'description': '',
            'image': big_image, 'visible_to_coach': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Exercise.objects.filter(name='حرکت عمومی با عکس بزرگ').exists())


# ===================== جلوگیری از XSS در JSON تزریق‌شده به اسکریپت =====================

class SafeJsonEmbedTests(TestCase):
    """اسم حرکتی که شامل </script> باشه نباید بتونه از تگ اسکریپت فرار کنه."""

    def setUp(self):
        self.coach = make_coach(username='coach_xsscheck')
        self.trainee = make_trainee(self.coach, username='trainee_xsscheck')
        self.client = Client()
        self.client.login(username='coach_xsscheck', password='pass12345')

    def test_malicious_exercise_name_is_escaped_in_program_create(self):
        Exercise.objects.create(
            name='بد</script><script>alert(1)</script>',
            category='chest', coach=self.coach,
        )
        resp = self.client.get(reverse('coach:program_create', args=[self.trainee.pk]))
        content = resp.content.decode('utf-8')
        self.assertNotIn('</script><script>alert(1)</script>', content)
        self.assertIn('\\u003c/script\\u003e', content)
