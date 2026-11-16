from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, TraineeProfile
from accounts.test_helpers import make_coach, make_trainee
from coach.models import (WorkoutProgram, NutritionPlan, NutritionDay, Meal,
                           NUTRITION_DAY_CHOICES, Notification)


class TraineeDashboardCountdownTests(TestCase):
    """تست نمایش بنر شمارش معکوس و نوتیف تمدید در پنل شاگرد"""

    def setUp(self):
        self.coach = make_coach()
        self.profile = make_trainee(self.coach, username='trainee_dash')
        self.program = WorkoutProgram.objects.create(
            trainee=self.profile, coach=self.coach,
            title='برنامه شاگرد', duration_days=30,
        )
        WorkoutProgram.objects.filter(pk=self.program.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=28)
        )
        self.client = Client()
        self.client.login(username='trainee_dash', password='pass12345')

    def test_dashboard_shows_countdown_and_triggers_notification(self):
        self.program.refresh_from_db()
        resp = self.client.get(reverse('trainee:dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn(str(self.program.days_remaining), content)
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 1)

    def test_my_program_page_shows_warning_banner(self):
        resp = self.client.get(reverse('trainee:my_program'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('badge-warning', content)  # نزدیک انقضا -> بج هشدار

    def test_notification_not_duplicated_across_pages(self):
        self.client.get(reverse('trainee:dashboard'))
        self.client.get(reverse('trainee:my_program'))
        self.client.get(reverse('trainee:dashboard'))
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 1)


@override_settings(NUTRITION_ENABLED=True)
class TraineeDietViewTests(TestCase):
    """تست صفحات رژیم غذایی نزد شاگرد (فعال، قبلی، جزئیات)"""

    def setUp(self):
        self.coach = make_coach()
        self.profile = make_trainee(self.coach, username='trainee_diet_view')
        self.plan = NutritionPlan.objects.create(
            trainee=self.profile, coach=self.coach, title='رژیم شاگرد', duration_days=30,
        )
        NutritionPlan.objects.filter(pk=self.plan.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=28)
        )
        self.plan.refresh_from_db()
        day = NutritionDay.objects.create(plan=self.plan, day_number=1)
        Meal.objects.create(day=day, meal_type='breakfast', content='صبحانه شاگرد', order=0)
        self.client = Client()
        self.client.login(username='trainee_diet_view', password='pass12345')

    def test_my_diet_shows_active_plan_and_countdown(self):
        resp = self.client.get(reverse('trainee:my_diet'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('صبحانه شاگرد', content)
        self.assertIn('badge-warning', content)  # نزدیک انقضا -> بج هشدار

    def test_my_diet_triggers_renewal_notification(self):
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 0)
        self.client.get(reverse('trainee:my_diet'))
        self.assertEqual(
            Notification.objects.filter(recipient=self.profile.user, notif_type='system').count(), 1
        )

    def test_my_diet_empty_state_when_no_plan(self):
        self.plan.delete()
        resp = self.client.get(reverse('trainee:my_diet'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('هنوز رژیم غذایی', resp.content.decode('utf-8'))

    def test_past_diets_lists_inactive_plans(self):
        self.plan.is_active = False
        self.plan.save()
        resp = self.client.get(reverse('trainee:past_diets'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('رژیم شاگرد', resp.content.decode('utf-8'))

    def test_diet_detail_shows_meals(self):
        resp = self.client.get(reverse('trainee:diet_detail', args=[self.plan.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('صبحانه شاگرد', resp.content.decode('utf-8'))

    def test_diet_detail_forbidden_for_other_trainee(self):
        other_profile = make_trainee(self.coach, username='other_trainee_diet')
        other_client = Client()
        other_client.login(username='other_trainee_diet', password='pass12345')
        resp = other_client.get(reverse('trainee:diet_detail', args=[self.plan.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_dashboard_shows_diet_card(self):
        resp = self.client.get(reverse('trainee:dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('رژیم غذایی', content)


# ===================== PDF رژیم غذایی =====================

@override_settings(NUTRITION_ENABLED=True)
class DietPDFTests(TestCase):
    """تست تولید و دانلود PDF رژیم غذایی"""

    def setUp(self):
        self.coach = make_coach(username='coach_pdf')
        self.profile = make_trainee(self.coach, username='trainee_pdf')
        self.plan = NutritionPlan.objects.create(
            trainee=self.profile, coach=self.coach, title='رژیم برای PDF', duration_days=30,
        )
        day1 = NutritionDay.objects.create(plan=self.plan, day_number=1, notes='روز سبک')
        Meal.objects.create(day=day1, meal_type='breakfast', content='۲ عدد تخم‌مرغ آب‌پز\nنان سنگک', order=0)
        Meal.objects.create(day=day1, meal_type='lunch', content='150 گرم سینه مرغ + برنج', order=1)
        day7 = NutritionDay.objects.create(plan=self.plan, day_number=7)
        Meal.objects.create(day=day7, meal_type='dinner', content='سوپ سبزیجات', order=0)
        self.client = Client()
        self.client.login(username='trainee_pdf', password='pass12345')

    def test_render_diet_pdf_returns_valid_pdf_bytes(self):
        from trainee.pdf_utils import render_diet_pdf
        pdf_bytes = render_diet_pdf(self.plan, self.profile)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 500)

    def test_render_diet_pdf_handles_plan_with_no_days(self):
        empty_plan = NutritionPlan.objects.create(
            trainee=self.profile, coach=self.coach, title='رژیم خالی', is_active=False,
        )
        from trainee.pdf_utils import render_diet_pdf
        pdf_bytes = render_diet_pdf(empty_plan, self.profile)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_render_diet_pdf_handles_long_multiline_content(self):
        long_day = NutritionDay.objects.create(plan=self.plan, day_number=2)
        long_content = '\n'.join([f'ماده غذایی شماره {i} با توضیحات کامل' for i in range(20)])
        Meal.objects.create(day=long_day, meal_type='lunch', content=long_content, order=0)
        from trainee.pdf_utils import render_diet_pdf
        pdf_bytes = render_diet_pdf(self.plan, self.profile)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_download_active_diet_pdf(self):
        resp = self.client.get(reverse('trainee:download_diet_pdf'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/octet-stream')
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.pdf', resp['Content-Disposition'])
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_download_specific_diet_pdf_by_pk(self):
        resp = self.client.get(reverse('trainee:download_diet_pdf_pk', args=[self.plan.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_download_diet_pdf_with_no_active_plan_redirects(self):
        self.plan.delete()
        resp = self.client.get(reverse('trainee:download_diet_pdf'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('trainee:my_diet'))

    def test_cannot_download_other_trainees_diet_pdf(self):
        other_profile = make_trainee(self.coach, username='other_trainee_pdf')
        other_client = Client()
        other_client.login(username='other_trainee_pdf', password='pass12345')
        resp = other_client.get(reverse('trainee:download_diet_pdf_pk', args=[self.plan.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_download_button_present_on_my_diet_page(self):
        resp = self.client.get(reverse('trainee:my_diet'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('دانلود PDF', content)
        self.assertIn('/diet/download/', content)

    def test_download_button_present_on_diet_detail_page(self):
        resp = self.client.get(reverse('trainee:diet_detail', args=[self.plan.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('دانلود PDF', resp.content.decode('utf-8'))

    def test_download_button_present_on_past_diets_page(self):
        self.plan.is_active = False
        self.plan.save()
        resp = self.client.get(reverse('trainee:past_diets'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('PDF', content)

    def test_download_button_present_on_dashboard(self):
        resp = self.client.get(reverse('trainee:dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('دانلود PDF رژیم', content)

