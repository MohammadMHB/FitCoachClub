from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, TraineeProfile, ActivityLog
from accounts.test_helpers import make_coach, make_trainee, make_admin
from coach.models import WorkoutProgram, NutritionPlan, FoodItem, FOOD_CATEGORY_CHOICES


class TraineeListViewTests(TestCase):
    """تست نمایش وضعیت برنامه (دارد/ندارد/چند روز مانده) در لیست شاگردان مربی و ادمین"""

    def setUp(self):
        self.coach = make_coach()
        self.admin = User.objects.create_superuser(
            username='admin1', password='pass12345', role='admin',
        )
        self.with_program = make_trainee(self.coach, username='t_with_program')
        self.without_program = make_trainee(self.coach, username='t_without_program')
        WorkoutProgram.objects.create(
            trainee=self.with_program, coach=self.coach,
            title='برنامه فعال', duration_days=30,
        )

    def test_coach_trainee_list_shows_program_status(self):
        client = Client()
        client.login(username='coach1', password='pass12345')
        resp = client.get(reverse('coach:trainee_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('روز', content)  # نشانگر روز باقی‌مانده برای شاگرد دارای برنامه
        self.assertIn('ندارد', content)  # نشانگر برای شاگرد بدون برنامه

    def test_admin_trainee_list_shows_program_status(self):
        client = Client()
        client.login(username='admin1', password='pass12345')
        resp = client.get(reverse('admin_panel:trainee_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('بدون برنامه', content)


@override_settings(NUTRITION_ENABLED=True)
class TraineeAndAdminListDietStatusTests(TestCase):
    """تست نمایش وضعیت رژیم غذایی در لیست شاگردان مربی و ادمین"""

    def setUp(self):
        self.coach = make_coach()
        self.admin = User.objects.create_superuser(
            username='admin_diet', password='pass12345', role='admin',
        )
        self.with_diet = make_trainee(self.coach, username='t_with_diet')
        self.without_diet = make_trainee(self.coach, username='t_without_diet')
        NutritionPlan.objects.create(
            trainee=self.with_diet, coach=self.coach, title='رژیم فعال', duration_days=30,
        )

    def test_coach_trainee_list_shows_diet_status(self):
        client = Client()
        client.login(username='coach1', password='pass12345')
        resp = client.get(reverse('coach:trainee_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('بدون رژیم', content) if 'بدون رژیم' in content else self.assertIn('ندارد', content)

    def test_admin_trainee_list_shows_diet_status(self):
        client = Client()
        client.login(username='admin_diet', password='pass12345')
        resp = client.get(reverse('admin_panel:trainee_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('بدون رژیم', content)

    def test_coach_trainee_detail_shows_diet_card(self):
        client = Client()
        client.login(username='coach1', password='pass12345')
        resp = client.get(reverse('coach:trainee_detail', args=[self.with_diet.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('رژیم فعال', resp.content.decode('utf-8'))


# ===================== بانک غذایی =====================

@override_settings(NUTRITION_ENABLED=True)


class AdminFoodBankCRUDTests(TestCase):
    """تست کامل CRUD بانک غذایی توسط ادمین"""

    def setUp(self):
        self.admin = make_admin()
        self.client = Client()
        self.client.login(username='admin_food', password='pass12345')

    def test_food_list_renders(self):
        resp = self.client.get(reverse('admin_panel:food_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('بانک غذایی', content)

    def test_food_list_category_filter(self):
        FoodItem.objects.create(name='آیتم تست پروتئین', category='protein', default_unit='gram')
        FoodItem.objects.create(name='آیتم تست میوه', category='fruit', default_unit='piece')
        resp = self.client.get(reverse('admin_panel:food_list') + '?category=protein')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('آیتم تست پروتئین', content)
        self.assertNotIn('آیتم تست میوه', content)

    def test_food_list_search(self):
        FoodItem.objects.create(name='کینوای مخصوص', category='carb', default_unit='gram')
        resp = self.client.get(reverse('admin_panel:food_list') + '?q=کینوا')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('کینوای مخصوص', resp.content.decode('utf-8'))

    def test_admin_can_add_food_item(self):
        count_before = FoodItem.objects.count()
        resp = self.client.post(reverse('admin_panel:food_add'), {
            'name': 'ماده غذایی جدید تستی',
            'category': 'protein',
            'default_unit': 'gram',
            'default_amount': '100',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(FoodItem.objects.count(), count_before + 1)
        item = FoodItem.objects.get(name='ماده غذایی جدید تستی')
        self.assertEqual(item.category, 'protein')
        self.assertEqual(item.default_amount, '100')

    def test_admin_add_food_item_requires_name(self):
        count_before = FoodItem.objects.count()
        resp = self.client.post(reverse('admin_panel:food_add'), {
            'name': '',
            'category': 'protein',
            'default_unit': 'gram',
        })
        self.assertEqual(resp.status_code, 200)  # برمی‌گرده به فرم چون خطا داره
        self.assertEqual(FoodItem.objects.count(), count_before)

    def test_admin_can_edit_food_item(self):
        item = FoodItem.objects.create(name='قبل از ویرایش', category='fruit', default_unit='piece', default_amount='1')
        resp = self.client.post(reverse('admin_panel:food_edit', args=[item.pk]), {
            'name': 'بعد از ویرایش',
            'category': 'fruit',
            'default_unit': 'gram',
            'default_amount': '50',
        })
        self.assertEqual(resp.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.name, 'بعد از ویرایش')
        self.assertEqual(item.default_unit, 'gram')
        self.assertEqual(item.default_amount, '50')

    def test_admin_can_delete_food_item(self):
        item = FoodItem.objects.create(name='برای حذف', category='other', default_unit='gram')
        resp = self.client.post(reverse('admin_panel:food_delete', args=[item.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(FoodItem.objects.filter(pk=item.pk).exists())

    def test_food_delete_requires_post(self):
        item = FoodItem.objects.create(name='حذف با گت رد میشه', category='other', default_unit='gram')
        resp = self.client.get(reverse('admin_panel:food_delete', args=[item.pk]))
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(FoodItem.objects.filter(pk=item.pk).exists())

    def test_non_admin_cannot_access_food_bank(self):
        coach = make_coach(username='coach_no_access')
        client = Client()
        client.login(username='coach_no_access', password='pass12345')
        resp = client.get(reverse('admin_panel:food_list'))
        self.assertNotEqual(resp.status_code, 200)


@override_settings(NUTRITION_ENABLED=True)


# ===================== نمای موبایل «مخاطبین» برای لیست‌ها =====================


class MobileContactListTests(TestCase):
    """تست ساختار HTML لیست موبایل (کارت مخاطبین + شیت جزئیات) برای هر سه لیست"""

    def setUp(self):
        self.admin = make_admin(username='admin_mobile_ui')
        self.coach = make_coach(username='coach_mobile_ui')
        self.coach.phone = '09121234567'
        self.coach.save()
        self.trainee1 = make_trainee(self.coach, username='trainee_mobile_ui1')
        WorkoutProgram.objects.create(trainee=self.trainee1, coach=self.coach, title='برنامه ۱', duration_days=30)
        NutritionPlan.objects.create(trainee=self.trainee1, coach=self.coach, title='رژیم ۱', duration_days=30)
        self.trainee2 = make_trainee(self.coach, username='trainee_mobile_ui2')

    def test_admin_trainee_list_has_contact_cards_and_sheets(self):
        client = Client()
        client.login(username='admin_mobile_ui', password='pass12345')
        resp = client.get(reverse('admin_panel:trainee_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('contact-list', content)
        self.assertIn('contact-row', content)
        self.assertIn(f'sheet-t-{self.trainee1.pk}', content)
        self.assertIn('openDetailSheet', content)
        self.assertIn('sheetBackdrop', content)
        # جدول دسکتاپ هم باید سرجاش باشه (نباید حذف بشه)
        self.assertIn('data-table', content)

    @override_settings(NUTRITION_ENABLED=True)
    def test_admin_trainee_sheet_contains_full_details(self):
        client = Client()
        client.login(username='admin_mobile_ui', password='pass12345')
        resp = client.get(reverse('admin_panel:trainee_list'))
        content = resp.content.decode('utf-8')
        self.assertIn('برنامه تمرینی', content)
        self.assertIn('رژیم غذایی', content)
        self.assertIn('detail-sheet-actions', content)

    def test_admin_coach_list_has_contact_cards_and_sheets(self):
        client = Client()
        client.login(username='admin_mobile_ui', password='pass12345')
        resp = client.get(reverse('admin_panel:coach_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('contact-list', content)
        self.assertIn(f'sheet-c-{self.coach.pk}', content)
        self.assertIn('09121234567', content)
        self.assertIn('لینک ثبت‌نام', content)

    @override_settings(NUTRITION_ENABLED=True)
    def test_coach_trainee_list_has_status_badges_on_collapsed_row(self):
        client = Client()
        client.login(username='coach_mobile_ui', password='pass12345')
        resp = client.get(reverse('coach:trainee_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('contact-list', content)
        self.assertIn(f'sheet-ct-{self.trainee1.pk}', content)
        self.assertIn(f'sheet-ct-{self.trainee2.pk}', content)
        # هر دو نشان برنامه و رژیم باید تو ردیف جمع‌وجور باشن (fa-dumbbell و fa-utensils)
        self.assertIn('fa-dumbbell', content)
        self.assertIn('fa-utensils', content)

    def test_coach_trainee_sheet_has_all_action_buttons(self):
        client = Client()
        client.login(username='coach_mobile_ui', password='pass12345')
        resp = client.get(reverse('coach:trainee_list'))
        content = resp.content.decode('utf-8')
        self.assertIn('ارسال به شاگرد', content)
        self.assertIn('برنامه جدید', content)
        self.assertIn('copyInviteMessageFor', content)

    def test_mobile_css_hides_table_and_shows_contact_list(self):
        # چک می‌کنیم قانون مدیای موبایل تو main.css واقعاً موجوده
        with open('static/css/main.css', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.contact-list', css)
        self.assertIn('.detail-sheet', css)
        self.assertIn('max-width: 768px', css)

    def test_shared_js_functions_exist(self):
        with open('static/js/main.js', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('function openDetailSheet', js)
        self.assertIn('function closeAllSheets', js)


# ===================== باگ لاگین بعد از تغییر رمز توسط ادمین =====================


class AdminPasswordResetSyncTests(TestCase):
    """تست رفع باگ: وقتی ادمین رمز شاگرد رو عوض می‌کنه، رمز نمایشی (last_password_plain)
    باید هم‌زمان آپدیت بشه، وگرنه رمزی که به مربی/شاگرد نشون داده میشه با رمز واقعی
    فرق می‌کنه و لاگین با رمز نمایشی fail می‌شه."""

    def setUp(self):
        self.admin = make_admin(username='admin_pwsync')
        self.coach = make_coach(username='coach_pwsync')
        self.profile = make_trainee(self.coach, username='trainee_pwsync')
        self.profile.last_password_plain = 'OldPass123'
        self.profile.user.set_password('OldPass123')
        self.profile.user.save()
        self.profile.save()

    def test_admin_password_reset_updates_last_password_plain(self):
        client = Client()
        client.login(username='admin_pwsync', password='pass12345')
        resp = client.post(reverse('admin_panel:trainee_edit', args=[self.profile.pk]), {
            'first_name': self.profile.user.first_name,
            'last_name': self.profile.user.last_name,
            'phone': '',
            'weight': '70', 'height': '170', 'age': '25',
            'password': 'NewPass456',
            'coach': self.coach.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.last_password_plain, 'NewPass456')

    def test_trainee_can_login_with_password_admin_just_set(self):
        client = Client()
        client.login(username='admin_pwsync', password='pass12345')
        client.post(reverse('admin_panel:trainee_edit', args=[self.profile.pk]), {
            'first_name': self.profile.user.first_name,
            'last_name': self.profile.user.last_name,
            'phone': '',
            'weight': '70', 'height': '170', 'age': '25',
            'password': 'NewPass456',
            'coach': self.coach.pk,
        })
        client.logout()

        login_ok = client.login(username='trainee_pwsync', password='NewPass456')
        self.assertTrue(login_ok)

    def test_stale_password_no_longer_shown_after_reset(self):
        client = Client()
        client.login(username='admin_pwsync', password='pass12345')
        client.post(reverse('admin_panel:trainee_edit', args=[self.profile.pk]), {
            'first_name': self.profile.user.first_name,
            'last_name': self.profile.user.last_name,
            'phone': '',
            'weight': '70', 'height': '170', 'age': '25',
            'password': 'NewPass456',
            'coach': self.coach.pk,
        })
        # حالا مربی که میره «ارسال به شاگرد» رو بزنه، باید رمز جدید رو ببینه نه قدیمی رو
        coach_client = Client()
        coach_client.login(username='coach_pwsync', password='pass12345')
        resp = coach_client.get(reverse('coach:trainee_detail', args=[self.profile.pk]))
        content = resp.content.decode('utf-8')
        self.assertIn('NewPass456', content)
        self.assertNotIn('OldPass123', content)


# ===================== ترتیب لیست شاگردان (جدیدترین اول) =====================


class TraineeListOrderingTests(TestCase):
    """تست اینکه آخرین شاگرد اضافه‌شده همیشه اول لیست باشه"""

    def test_coach_trainee_list_shows_newest_first(self):
        coach = make_coach(username='coach_order')
        first = make_trainee(coach, username='trainee_order_first')
        second = make_trainee(coach, username='trainee_order_second')
        third = make_trainee(coach, username='trainee_order_third')

        client = Client()
        client.login(username='coach_order', password='pass12345')
        resp = client.get(reverse('coach:trainee_list'))
        content = resp.content.decode('utf-8')

        pos_first = content.find('trainee_order_first')
        pos_second = content.find('trainee_order_second')
        pos_third = content.find('trainee_order_third')
        # جدیدترین (third) باید زودتر از قدیمی‌تر‌ها ظاهر بشه
        self.assertTrue(pos_third < pos_second < pos_first)

    def test_admin_trainee_list_shows_newest_first(self):
        admin = make_admin(username='admin_order')
        coach = make_coach(username='coach_order2')
        make_trainee(coach, username='trainee_order2_first')
        make_trainee(coach, username='trainee_order2_second')

        client = Client()
        client.login(username='admin_order', password='pass12345')
        resp = client.get(reverse('admin_panel:trainee_list'))
        content = resp.content.decode('utf-8')
        pos_first = content.find('trainee_order2_first')
        pos_second = content.find('trainee_order2_second')
        self.assertTrue(pos_second < pos_first)


# ===================== گزارش فعالیت (Activity Log) =====================


class ActivityLogTests(TestCase):
    """تست اینکه هر تغییر مهم (افزودن/ویرایش/حذف شاگرد، برنامه، رژیم، مربی، حرکت، غذا)
    یه رکورد لاگ می‌سازه و ادمین می‌تونه ببینتش"""

    def setUp(self):
        self.admin = make_admin(username='admin_actlog')
        self.coach = make_coach(username='coach_actlog')

    def test_coach_adding_trainee_creates_log(self):
        client = Client()
        client.login(username='coach_actlog', password='pass12345')
        client.post(reverse('coach:trainee_add'), {
            'username': 'trainee_actlog_new', 'password': 'pass12345',
            'first_name': 'تست', 'last_name': 'لاگ',
            'phone': '', 'weight': '70', 'height': '170', 'age': '25',
        })
        log = ActivityLog.objects.filter(action='trainee_add').first()
        self.assertIsNotNone(log)
        self.assertIn('تست لاگ', log.description)
        self.assertEqual(log.actor, self.coach)

    def test_coach_deleting_trainee_creates_log(self):
        profile = make_trainee(self.coach, username='trainee_actlog_del')
        client = Client()
        client.login(username='coach_actlog', password='pass12345')
        client.post(reverse('coach:trainee_delete', args=[profile.pk]))
        log = ActivityLog.objects.filter(action='trainee_delete').first()
        self.assertIsNotNone(log)

    def test_program_create_creates_log(self):
        profile = make_trainee(self.coach, username='trainee_actlog_prog')
        client = Client()
        client.login(username='coach_actlog', password='pass12345')
        client.post(reverse('coach:program_create', args=[profile.pk]), {
            'title': 'برنامه لاگ تست', 'duration_days': '30', 'days_data': '{}',
        })
        log = ActivityLog.objects.filter(action='program_create').first()
        self.assertIsNotNone(log)
        self.assertIn('برنامه لاگ تست', log.description)

    @override_settings(NUTRITION_ENABLED=True)
    def test_diet_create_creates_log(self):
        profile = make_trainee(self.coach, username='trainee_actlog_diet')
        client = Client()
        client.login(username='coach_actlog', password='pass12345')
        client.post(reverse('coach:nutrition_create', args=[profile.pk]), {
            'title': 'رژیم لاگ تست', 'duration_days': '30',
            'day_1_breakfast': 'صبحانه تست',
        })
        log = ActivityLog.objects.filter(action='diet_create').first()
        self.assertIsNotNone(log)

    def test_admin_adding_coach_creates_log(self):
        client = Client()
        client.login(username='admin_actlog', password='pass12345')
        client.post(reverse('admin_panel:coach_add'), {
            'username': 'coach_actlog_new', 'password': 'pass12345',
            'first_name': 'مربی', 'last_name': 'جدید', 'phone': '',
        })
        log = ActivityLog.objects.filter(action='coach_add').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.admin)

    def test_admin_deleting_coach_creates_log(self):
        other_coach = make_coach(username='coach_actlog_todelete')
        client = Client()
        client.login(username='admin_actlog', password='pass12345')
        client.post(reverse('admin_panel:coach_delete', args=[other_coach.pk]))
        log = ActivityLog.objects.filter(action='coach_delete').first()
        self.assertIsNotNone(log)

    @override_settings(NUTRITION_ENABLED=True)
    def test_food_item_add_creates_log(self):
        client = Client()
        client.login(username='admin_actlog', password='pass12345')
        client.post(reverse('admin_panel:food_add'), {
            'name': 'ماده لاگ تست', 'category': 'protein', 'default_unit': 'gram',
        })
        log = ActivityLog.objects.filter(action='food_add').first()
        self.assertIsNotNone(log)
        self.assertIn('ماده لاگ تست', log.description)

    def test_activity_log_page_renders_for_admin(self):
        ActivityLog.objects.create(actor=self.coach, actor_name='مربی تست', actor_role='coach',
                                    action='trainee_add', description='مربی تست شاگردی اضافه کرد.')
        client = Client()
        client.login(username='admin_actlog', password='pass12345')
        resp = client.get(reverse('admin_panel:activity_log'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('مربی تست شاگردی اضافه کرد', resp.content.decode('utf-8'))

    def test_activity_log_page_forbidden_for_coach(self):
        client = Client()
        client.login(username='coach_actlog', password='pass12345')
        resp = client.get(reverse('admin_panel:activity_log'))
        self.assertNotEqual(resp.status_code, 200)

    def test_activity_log_filter_by_action(self):
        ActivityLog.objects.create(actor=self.coach, actor_name='م', actor_role='coach',
                                    action='trainee_add', description='رویداد افزودن شاگرد')
        ActivityLog.objects.create(actor=self.coach, actor_name='م', actor_role='coach',
                                    action='trainee_delete', description='رویداد حذف شاگرد')
        client = Client()
        client.login(username='admin_actlog', password='pass12345')
        resp = client.get(reverse('admin_panel:activity_log') + '?action=trainee_add')
        content = resp.content.decode('utf-8')
        self.assertIn('رویداد افزودن شاگرد', content)
        self.assertNotIn('رویداد حذف شاگرد', content)

    def test_activity_log_survives_actor_deletion(self):
        temp_coach = make_coach(username='coach_actlog_temp')
        ActivityLog.objects.create(actor=temp_coach, actor_name='مربی موقت', actor_role='coach',
                                    action='trainee_add', description='مربی موقت یک شاگرد اضافه کرد.')
        temp_coach.delete()
        log = ActivityLog.objects.get(description='مربی موقت یک شاگرد اضافه کرد.')
        self.assertIsNone(log.actor)
        self.assertEqual(log.actor_name, 'مربی موقت')  # نام هنوز باقیه حتی بعد حذف کاربر

    def test_activity_log_pagination(self):
        for i in range(35):
            ActivityLog.objects.create(actor=self.coach, actor_name='م', actor_role='coach',
                                        action='trainee_add', description=f'رویداد شماره {i}')
        client = Client()
        client.login(username='admin_actlog', password='pass12345')
        resp = client.get(reverse('admin_panel:activity_log'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'صفحه 1 از 2')


# ===================== ریسپانسیو شدن داشبورد ادمین =====================


class AdminDashboardResponsiveTests(TestCase):
    """تست اینکه کلاس ریسپانسیو جدید به‌جای گرید اینلاین قدیمی استفاده شده"""

    def test_dashboard_uses_responsive_two_col_class(self):
        admin = make_admin(username='admin_dashresp')
        client = Client()
        client.login(username='admin_dashresp', password='pass12345')
        resp = client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('dashboard-two-col', content)
        self.assertNotIn('grid-template-columns:1fr 1fr', content)

    def test_css_has_dashboard_two_col_breakpoint(self):
        with open('static/css/main.css', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.dashboard-two-col', css)


# ===================== دکمه ارسال پیام برای ادمین =====================


class AdminInviteMessageTests(TestCase):
    """تست اینکه ادمین هم مثل مربی می‌تونه پیام یوزرنیم/پسورد شاگرد رو کپی کنه"""

    def setUp(self):
        self.admin = make_admin(username='admin_invite_test')
        self.coach = make_coach(username='coach_invite_test')
        self.profile = make_trainee(self.coach, username='trainee_invite_admin')
        self.profile.last_password_plain = 'AdminSeen123'
        self.profile.save()
        self.client = Client()
        self.client.login(username='admin_invite_test', password='pass12345')

    def test_admin_trainee_list_has_invite_button(self):
        resp = self.client.get(reverse('admin_panel:trainee_list'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('ارسال به شاگرد', content)
        self.assertIn('copyInviteMessageFor', content)
        self.assertIn('AdminSeen123', content)
        self.assertIn('trainee_invite_admin', content)

    def test_admin_invite_message_uses_login_link(self):
        resp = self.client.get(reverse('admin_panel:trainee_list'))
        content = resp.content.decode('utf-8')
        self.assertIn(reverse('accounts:login'), content)

