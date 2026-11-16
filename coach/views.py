from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.conf import settings
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
import json


def safe_json_dumps(data):
    """
    مثل json.dumps معمولی، ولی خروجی امنه که مستقیم داخل تگ <script> با
    فیلتر |safe چاپ بشه. json.dumps معمولی کاراکترهای </script> رو escape
    نمی‌کنه؛ اگه اسم یه حرکت یا غذا (که کاربر ساخته) شامل این رشته باشه،
    می‌تونه تگ اسکریپت رو زودتر از موقع ببنده و یه XSS ذخیره‌شده بسازه.
    """
    return (json.dumps(data, ensure_ascii=False)
            .replace('<', '\\u003c')
            .replace('>', '\\u003e')
            .replace('&', '\\u0026'))

from accounts.models import User, TraineeProfile, BodyMetricHistory
from coach.models import (Exercise, WorkoutProgram, WorkoutDay,
                           WorkoutExercise, Notification,
                           NutritionPlan, NutritionDay, Meal, FoodItem,
                           DAY_CHOICES, CATEGORY_CHOICES,
                           NUTRITION_DAY_CHOICES, MEAL_TYPE_CHOICES,
                           FOOD_CATEGORY_CHOICES)
from coach.sms import send_new_program_sms
from accounts.activity_log import log_activity


def coach_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'coach':
            messages.error(request, 'دسترسی غیرمجاز.')
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def nutrition_required(view_func):
    """قابلیت رژیم غذایی فعلاً موقتاً غیرفعال است؛ دسترسی مستقیم به صفحاتش هم بسته می‌شود."""
    def wrapper(request, *args, **kwargs):
        if not settings.NUTRITION_ENABLED:
            messages.error(request, 'این قابلیت در دسترس نیست.')
            return redirect('coach:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def _create_workout_days(program, days_json):
    """
    از روی days_json (خروجی فرم برنامه‌ریزی)، WorkoutDay و WorkoutExercise‌ها رو
    برای یک برنامه می‌سازه. برای جلوگیری از کند شدن ذخیره در برنامه‌هایی که
    ترکیبی از حرکات معمولی و سوپرست/تری‌ست/دراپ‌ست دارن (حرکات بیشتر = کوئری
    بیشتر)، همه‌ی حرکات با یک کوئری واحد واکشی می‌شن و همه‌ی ردیف‌ها با
    bulk_create یک‌جا ساخته می‌شن، به‌جای یک کوئری SELECT و یک INSERT جداگانه
    برای تک‌تک حرکات.
    """
    all_exercise_ids = {
        ex_data.get('exercise_id')
        for day_data in days_json.values()
        for ex_data in day_data.get('exercises', [])
    }
    exercises_by_id = Exercise.objects.in_bulk(id_list=[eid for eid in all_exercise_ids if eid is not None])

    new_workout_exercises = []
    for day_str, day_data in days_json.items():
        if not day_data.get('exercises'):
            continue
        wday = WorkoutDay.objects.create(
            program=program,
            day_number=int(day_str),
            notes=day_data.get('notes', ''),
        )
        for order, ex_data in enumerate(day_data['exercises']):
            ex = exercises_by_id.get(ex_data.get('exercise_id'))
            if ex is None:
                continue
            new_workout_exercises.append(WorkoutExercise(
                day=wday, exercise=ex,
                sets=int(ex_data.get('sets', 3)),
                reps=str(ex_data.get('reps', '12')),
                rest_seconds=int(ex_data.get('rest', 60)),
                set_type=ex_data.get('set_type', 'normal'),
                notes=ex_data.get('notes', ''),
                order=order,
                group_id=ex_data.get('group_id'),
                dropset_weights=ex_data.get('dropset_weights', '') or '',
            ))

    if new_workout_exercises:
        WorkoutExercise.objects.bulk_create(new_workout_exercises)


def get_unread(request):
    return Notification.objects.filter(recipient=request.user, is_read=False).count()


# ======== DASHBOARD ========

@coach_required
def dashboard(request):
    coach = request.user
    coach.ensure_referral_code()
    trainees      = TraineeProfile.objects.filter(coach=coach).select_related('user')
    active_count  = trainees.filter(user__is_active=True).count()
    total_programs = WorkoutProgram.objects.filter(coach=coach).count()
    unread        = get_unread(request)
    signup_link = request.build_absolute_uri(reverse('coach_signup', args=[coach.referral_code]))
    return render(request, 'coach/dashboard.html', {
        'trainees':             trainees,
        'active_trainees':      active_count,
        'total_programs':       total_programs,
        'unread_notifications': unread,
        'unread_count':         unread,
        'signup_link':          signup_link,
    })


# ======== TRAINEES ========

@coach_required
def trainee_list(request):
    trainees = list(
        TraineeProfile.objects.filter(coach=request.user)
        .select_related('user').order_by('-created_at')
    )

    # برای هر شاگرد، برنامه‌ی فعالش (اگر داشته باشد) رو پیدا می‌کنیم تا در لیست
    # وضعیت «برنامه دارد / ندارد / چقدر مانده» نمایش داده بشه — با دو کوئری
    # واحد به‌جای یک کوئری جدا برای هر شاگرد.
    active_programs = {
        wp.trainee_id: wp for wp in
        WorkoutProgram.objects.filter(trainee__in=trainees, is_active=True)
    }
    active_diets = {
        np.trainee_id: np for np in
        NutritionPlan.objects.filter(trainee__in=trainees, is_active=True)
    }
    for profile in trainees:
        profile.active_program_obj = active_programs.get(profile.pk)
        profile.active_diet_obj = active_diets.get(profile.pk)
    return render(request, 'coach/trainee_list.html', {
        'trainees':    trainees,
        'unread_count': get_unread(request),
    })


@coach_required
def trainee_add(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name',  '').strip()
        phone      = request.POST.get('phone',      '').strip()
        username   = request.POST.get('username',   '').strip()
        password   = request.POST.get('password',   '')
        weight     = request.POST.get('weight')
        height     = request.POST.get('height')
        age        = request.POST.get('age')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'این نام کاربری قبلاً استفاده شده است.')
            return render(request, 'coach/trainee_form.html',
                          {'action': 'add', 'unread_count': get_unread(request)})
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, password=password,
                    first_name=first_name, last_name=last_name,
                    role='trainee', phone=phone,
                )
                profile = TraineeProfile.objects.create(
                    user=user, coach=request.user,
                    weight=float(weight) if weight else None,
                    height=float(height) if height else None,
                    age=int(age) if age else None,
                    last_password_plain=password,
                )
                if weight or height:
                    BodyMetricHistory.objects.create(
                        trainee=profile,
                        weight=profile.weight, height=profile.height,
                        age=profile.age, bmi=profile.bmi,
                    )
            messages.success(request, f'شاگرد {first_name} {last_name} با موفقیت اضافه شد.')
            log_activity(request.user, 'trainee_add',
                         f'{request.user.get_full_name() or request.user.username} شاگرد «{first_name} {last_name}» را اضافه کرد.')
            return redirect('coach:trainee_list')
        except Exception as e:
            messages.error(request, f'خطا در ثبت: {e}')

    return render(request, 'coach/trainee_form.html',
                  {'action': 'add', 'unread_count': get_unread(request)})


@coach_required
def trainee_edit(request, pk):
    profile = get_object_or_404(TraineeProfile, pk=pk, coach=request.user)
    user = profile.user
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name  = request.POST.get('last_name',  '').strip()
        user.phone      = request.POST.get('phone',      '').strip()
        new_username    = request.POST.get('username',   '').strip()

        if new_username != user.username and User.objects.filter(username=new_username).exists():
            messages.error(request, 'این نام کاربری قبلاً استفاده شده است.')
            return render(request, 'coach/trainee_form.html',
                          {'action': 'edit', 'profile': profile, 'unread_count': get_unread(request)})

        user.username = new_username
        new_pass = request.POST.get('password', '')
        if new_pass:
            user.set_password(new_pass)
            profile.last_password_plain = new_pass
        user.save()

        old_weight = profile.weight
        w = request.POST.get('weight')
        h = request.POST.get('height')
        a = request.POST.get('age')
        if w: profile.weight = float(w)
        if h: profile.height = float(h)
        if a: profile.age    = int(a)
        profile.save()

        if profile.weight != old_weight:
            BodyMetricHistory.objects.create(
                trainee=profile,
                weight=profile.weight, height=profile.height,
                age=profile.age, bmi=profile.bmi,
            )
        messages.success(request, 'اطلاعات شاگرد ویرایش شد.')
        log_activity(request.user, 'trainee_edit',
                     f'{request.user.get_full_name() or request.user.username} اطلاعات شاگرد «{user.get_full_name() or user.username}» را ویرایش کرد.')
        return redirect('coach:trainee_list')

    return render(request, 'coach/trainee_form.html',
                  {'action': 'edit', 'profile': profile, 'unread_count': get_unread(request)})


@coach_required
def trainee_detail(request, pk):
    profile        = get_object_or_404(TraineeProfile, pk=pk, coach=request.user)
    active_program = WorkoutProgram.objects.filter(trainee=profile, is_active=True).first()
    past_programs  = WorkoutProgram.objects.filter(trainee=profile, is_active=False).order_by('-created_at')
    active_diet    = NutritionPlan.objects.filter(trainee=profile, is_active=True).first()
    past_diets     = NutritionPlan.objects.filter(trainee=profile, is_active=False).order_by('-created_at')
    history        = profile.metric_history.all()
    return render(request, 'coach/trainee_detail.html', {
        'profile':        profile,
        'active_program': active_program,
        'past_programs':  past_programs,
        'active_diet':    active_diet,
        'past_diets':     past_diets,
        'history':        history,
        'unread_count':   get_unread(request),
    })


@coach_required
@require_POST
def trainee_toggle(request, pk):
    profile = get_object_or_404(TraineeProfile, pk=pk, coach=request.user)
    profile.user.is_active = not profile.user.is_active
    profile.user.save()
    messages.success(request, f'شاگرد {"فعال" if profile.user.is_active else "غیرفعال"} شد.')
    log_activity(request.user, 'trainee_toggle',
                 f'{request.user.get_full_name() or request.user.username} شاگرد «{profile.user.get_full_name() or profile.user.username}» را '
                 f'{"فعال" if profile.user.is_active else "غیرفعال"} کرد.')
    return redirect('coach:trainee_list')


@coach_required
@require_POST
def trainee_delete(request, pk):
    profile = get_object_or_404(TraineeProfile, pk=pk, coach=request.user)
    name = profile.user.get_full_name()
    profile.user.delete()
    messages.success(request, f'شاگرد {name} حذف شد.')
    log_activity(request.user, 'trainee_delete',
                 f'{request.user.get_full_name() or request.user.username} شاگرد «{name}» را حذف کرد.')
    return redirect('coach:trainee_list')


# ======== EXERCISES ========

@coach_required
def exercise_list(request):
    exercises        = Exercise.objects.filter(coach=request.user)
    # حرکات عمومی (برای همه مربی‌ها) + حرکاتی که ادمین فقط برای این مربی مشخص کرده
    public_exercises_qs = Exercise.objects.filter(
        Q(is_public=True) | Q(visible_to_coach=request.user)
    )
    cat = request.GET.get('category', '')
    if cat:
        exercises            = exercises.filter(category=cat)
        public_exercises_qs  = public_exercises_qs.filter(category=cat)

    paginator = Paginator(public_exercises_qs, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'coach/exercise_list.html', {
        'exercises':        exercises,
        'public_exercises': page_obj,
        'page_obj':         page_obj,
        'category_filter':  cat,
        'category_filter_label': dict(CATEGORY_CHOICES).get(cat, ''),
        'cats':             CATEGORY_CHOICES,
        'unread_count':     get_unread(request),
    })


@coach_required
def exercise_add(request):
    if request.method == 'POST':
        ex_name = request.POST.get('name', '').strip()
        exercise = Exercise(
            name=ex_name,
            category=request.POST.get('category', ''),
            description=request.POST.get('description', '').strip(),
            video_url=request.POST.get('video_url', '').strip() or None,
            image=request.FILES.get('image'),
            video=request.FILES.get('video'),
            coach=request.user,
            is_public=False,
        )
        try:
            exercise.full_clean()
        except ValidationError as e:
            for field_errors in e.message_dict.values():
                for msg in field_errors:
                    messages.error(request, msg)
            return render(request, 'coach/exercise_form.html',
                          {'action': 'add', 'categories': CATEGORY_CHOICES, 'unread_count': get_unread(request)})
        exercise.save()
        messages.success(request, 'حرکت اضافه شد.')
        log_activity(request.user, 'exercise_add',
                     f'{request.user.get_full_name() or request.user.username} حرکت «{ex_name}» را به بانک شخصی‌اش اضافه کرد.')
        return redirect('coach:exercise_list')
    return render(request, 'coach/exercise_form.html',
                  {'action': 'add', 'categories': CATEGORY_CHOICES, 'unread_count': get_unread(request)})


@coach_required
def exercise_edit(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk, coach=request.user)
    if request.method == 'POST':
        exercise.name        = request.POST.get('name', '').strip()
        exercise.category    = request.POST.get('category', '')
        exercise.description = request.POST.get('description', '').strip()
        exercise.video_url   = request.POST.get('video_url', '').strip() or None
        if request.FILES.get('image'): exercise.image = request.FILES['image']
        if request.FILES.get('video'): exercise.video = request.FILES['video']
        try:
            exercise.full_clean()
        except ValidationError as e:
            for field_errors in e.message_dict.values():
                for msg in field_errors:
                    messages.error(request, msg)
            return render(request, 'coach/exercise_form.html',
                          {'action': 'edit', 'exercise': exercise, 'categories': CATEGORY_CHOICES, 'unread_count': get_unread(request)})
        exercise.save()
        messages.success(request, 'حرکت ویرایش شد.')
        log_activity(request.user, 'exercise_edit',
                     f'{request.user.get_full_name() or request.user.username} حرکت «{exercise.name}» را ویرایش کرد.')
        return redirect('coach:exercise_list')
    return render(request, 'coach/exercise_form.html',
                  {'action': 'edit', 'exercise': exercise, 'categories': CATEGORY_CHOICES, 'unread_count': get_unread(request)})


@coach_required
@require_POST
def exercise_delete(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk, coach=request.user)
    ex_name = exercise.name
    exercise.delete()
    messages.success(request, 'حرکت حذف شد.')
    log_activity(request.user, 'exercise_delete',
                 f'{request.user.get_full_name() or request.user.username} حرکت «{ex_name}» را از بانک شخصی‌اش حذف کرد.')
    return redirect('coach:exercise_list')


# ======== PROGRAMS ========

def _build_exercise_list(coach_user):
    """
    لیست حرکات قابل انتخاب برای یک مربی (شخصی + عمومی)، همراه با آدرس
    تصویر (اگر داشته باشد) برای نمایش thumbnail کوچک تو پیکر انتخاب حرکت.
    """
    fields = ('id', 'name', 'category', 'image')
    mine   = list(Exercise.objects.filter(coach=coach_user).values(*fields))
    public = list(Exercise.objects.filter(Q(is_public=True) | Q(visible_to_coach=coach_user)).values(*fields))
    seen   = {e['id'] for e in mine}
    all_ex = mine + [e for e in public if e['id'] not in seen]
    for e in all_ex:
        e['image_url'] = (settings.MEDIA_URL + e['image']) if e.get('image') else ''
        e.pop('image', None)
    return all_ex


@coach_required
def program_create(request, trainee_pk):
    profile = get_object_or_404(TraineeProfile, pk=trainee_pk, coach=request.user)

    all_ex = _build_exercise_list(request.user)

    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        days_raw    = request.POST.get('days_data', '')
        try:
            days_json = json.loads(days_raw) if days_raw else {}
        except Exception:
            days_json = {}

        try:
            duration_days = int(request.POST.get('duration_days', '30'))
            if duration_days <= 0:
                duration_days = 30
        except (TypeError, ValueError):
            duration_days = 30

        with transaction.atomic():
            WorkoutProgram.objects.filter(trainee=profile, is_active=True).update(is_active=False)

            program = WorkoutProgram.objects.create(
                trainee=profile, coach=request.user,
                title=title or f'برنامه {profile.user.get_full_name()}',
                description=description, is_active=True,
                duration_days=duration_days,
            )

            _create_workout_days(program, days_json)

            Notification.objects.create(
                recipient=profile.user,
                sender=request.user,
                notif_type='program_ready',
                title='برنامه تمرینی جدید',
                message=f'مربی {request.user.get_full_name() or request.user.username} برنامه جدیدی برای شما تنظیم کرد.',
            )

        # ── ارسال پیامک به شاگرد ──────────────────────────────
        try:
            send_new_program_sms(profile, request.user)
        except Exception:
            pass  # خطای پیامک نباید فرایند ثبت برنامه را مختل کند

        messages.success(request, 'برنامه تمرینی با موفقیت ثبت شد.')
        log_activity(request.user, 'program_create',
                     f'{request.user.get_full_name() or request.user.username} برنامه تمرینی «{program.title}» را برای «{profile.user.get_full_name() or profile.user.username}» ثبت کرد.')
        return redirect('coach:trainee_detail', pk=trainee_pk)

    return render(request, 'coach/program_create.html', {
        'profile':          profile,
        'exercises_json':   safe_json_dumps(all_ex),
        'day_choices':      DAY_CHOICES,
        'category_choices': CATEGORY_CHOICES,
        'category_choices_json': safe_json_dumps(dict(CATEGORY_CHOICES)),
        'unread_count':     get_unread(request),
    })


@coach_required
def program_view(request, pk):
    program = get_object_or_404(WorkoutProgram, pk=pk, coach=request.user)
    return render(request, 'coach/program_view.html', {
        'program':      program,
        'unread_count': get_unread(request),
    })


@coach_required
def program_copy(request, pk):
    """کپی کردن یک برنامه‌ی تمرینی (همراه با تمام روزها و حرکات) برای شاگرد دیگر."""
    program = get_object_or_404(WorkoutProgram, pk=pk, coach=request.user)

    if request.method == 'POST':
        target_pk = request.POST.get('target_trainee')
        target = get_object_or_404(TraineeProfile, pk=target_pk, coach=request.user)

        with transaction.atomic():
            WorkoutProgram.objects.filter(trainee=target, is_active=True).update(is_active=False)

            new_program = WorkoutProgram.objects.create(
                trainee=target, coach=request.user,
                title=program.title, description=program.description,
                is_active=True, duration_days=program.duration_days,
            )
            for day in program.days.all():
                new_day = WorkoutDay.objects.create(
                    program=new_program, day_number=day.day_number, notes=day.notes,
                )
                for wex in day.exercises.all():
                    WorkoutExercise.objects.create(
                        day=new_day, exercise=wex.exercise, sets=wex.sets, reps=wex.reps,
                        rest_seconds=wex.rest_seconds, set_type=wex.set_type, notes=wex.notes,
                        order=wex.order, group_id=wex.group_id, dropset_weights=wex.dropset_weights,
                    )

            Notification.objects.create(
                recipient=target.user, sender=request.user, notif_type='program_ready',
                title='برنامه تمرینی جدید',
                message=f'مربی {request.user.get_full_name() or request.user.username} یک برنامه تمرینی برای شما تنظیم کرد.',
            )

        messages.success(request, f'برنامه با موفقیت برای {target.user.get_full_name()} کپی شد.')
        log_activity(request.user, 'program_copy',
                     f'{request.user.get_full_name() or request.user.username} برنامه «{program.title}» را از «{program.trainee.user.get_full_name() or program.trainee.user.username}» برای «{target.user.get_full_name() or target.user.username}» کپی کرد.')
        return redirect('coach:trainee_detail', pk=target.pk)

    trainees = (TraineeProfile.objects.filter(coach=request.user)
                .exclude(pk=program.trainee.pk).select_related('user'))
    for t in trainees:
        t.active_program_obj = WorkoutProgram.objects.filter(trainee=t, is_active=True).first()
    return render(request, 'coach/program_copy.html', {
        'program':      program,
        'trainees':     trainees,
        'unread_count': get_unread(request),
    })


@coach_required
def program_edit(request, pk):
    program = get_object_or_404(WorkoutProgram, pk=pk, coach=request.user)
    profile = program.trainee

    all_ex = _build_exercise_list(request.user)

    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        days_raw    = request.POST.get('days_data', '')
        try:
            days_json = json.loads(days_raw) if days_raw else {}
        except Exception:
            days_json = {}

        try:
            duration_days = int(request.POST.get('duration_days', program.duration_days))
            if duration_days <= 0:
                duration_days = program.duration_days
        except (TypeError, ValueError):
            duration_days = program.duration_days

        with transaction.atomic():
            program.title       = title or program.title
            program.description = description
            if duration_days != program.duration_days:
                program.duration_days = duration_days
                # مدت جدید یعنی احتمالاً باید دوباره امکان یادآوری تمدید فعال بشه
                program.renewal_notified = False
            program.save()

            # پاک کردن روزهای قبلی و ساختن دوباره
            program.days.all().delete()

            _create_workout_days(program, days_json)

        messages.success(request, 'برنامه تمرینی ویرایش شد.')
        log_activity(request.user, 'program_edit',
                     f'{request.user.get_full_name() or request.user.username} برنامه «{program.title}» متعلق به «{profile.user.get_full_name() or profile.user.username}» را ویرایش کرد.')
        return redirect('coach:program_view', pk=program.pk)

    # ساختن days_json از برنامه فعلی برای پر کردن فرم
    existing_days = {}
    for day in program.days.all():
        exercises = []
        for wex in day.exercises.all():
            exercises.append({
                'uid':         wex.pk,
                'exercise_id': wex.exercise.pk,
                'name':        wex.exercise.name,
                'category':    wex.exercise.category,
                'sets':        wex.sets,
                'reps':        wex.reps,
                'rest':        wex.rest_seconds,
                'set_type':    wex.set_type,
                'notes':       wex.notes or '',
                'group_id':    wex.group_id or '',
                'drops':       [],
                'dropset_weights': wex.dropset_weights or '',
            })
        existing_days[str(day.day_number)] = {
            'exercises': exercises,
            'notes':     day.notes or '',
        }

    return render(request, 'coach/program_create.html', {
        'profile':        profile,
        'exercises_json': safe_json_dumps(all_ex),
        'day_choices':    DAY_CHOICES,
        'category_choices': CATEGORY_CHOICES,
        'category_choices_json': safe_json_dumps(dict(CATEGORY_CHOICES)),
        'unread_count':   get_unread(request),
        'edit_mode':      True,
        'program':        program,
        'existing_days_json': safe_json_dumps(existing_days),
    })


# ======== NUTRITION (رژیم غذایی) ========

def _food_items_json():
    """لیست بانک غذایی به‌صورت JSON برای استفاده در جاوااسکریپت فرم ثبت رژیم."""
    items = []
    for item in FoodItem.objects.all().order_by('category', 'name'):
        items.append({
            'id':       item.pk,
            'name':     item.name,
            'category': item.category,
            'category_label': item.get_category_display(),
            'unit_label':      item.get_default_unit_display(),
            'amount':   item.default_amount or '',
        })
    return safe_json_dumps(items)


@coach_required
@nutrition_required
def nutrition_create(request, trainee_pk):
    profile = get_object_or_404(TraineeProfile, pk=trainee_pk, coach=request.user)

    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        try:
            duration_days = int(request.POST.get('duration_days', '30'))
            if duration_days <= 0:
                duration_days = 30
        except (TypeError, ValueError):
            duration_days = 30

        with transaction.atomic():
            NutritionPlan.objects.filter(trainee=profile, is_active=True).update(is_active=False)

            plan = NutritionPlan.objects.create(
                trainee=profile, coach=request.user,
                title=title or f'رژیم غذایی {profile.user.get_full_name()}',
                description=description, is_active=True,
                duration_days=duration_days,
            )

            for day_num, _ in NUTRITION_DAY_CHOICES:
                meals_for_day = []
                for meal_type, _ in MEAL_TYPE_CHOICES:
                    content = request.POST.get(f'day_{day_num}_{meal_type}', '').strip()
                    if content:
                        meals_for_day.append((meal_type, content))
                if not meals_for_day:
                    continue
                nday = NutritionDay.objects.create(plan=plan, day_number=day_num)
                for order, (meal_type, content) in enumerate(meals_for_day):
                    Meal.objects.create(day=nday, meal_type=meal_type, content=content, order=order)

            Notification.objects.create(
                recipient=profile.user,
                sender=request.user,
                notif_type='diet_ready',
                title='رژیم غذایی جدید',
                message=f'مربی {request.user.get_full_name() or request.user.username} رژیم غذایی جدیدی برای شما تنظیم کرد.',
            )

        messages.success(request, 'رژیم غذایی با موفقیت ثبت شد.')
        log_activity(request.user, 'diet_create',
                     f'{request.user.get_full_name() or request.user.username} رژیم غذایی «{plan.title}» را برای «{profile.user.get_full_name() or profile.user.username}» ثبت کرد.')
        return redirect('coach:trainee_detail', pk=trainee_pk)

    return render(request, 'coach/nutrition_create.html', {
        'profile':        profile,
        'nutrition_day_choices': NUTRITION_DAY_CHOICES,
        'meal_type_choices':     MEAL_TYPE_CHOICES,
        'food_category_choices': FOOD_CATEGORY_CHOICES,
        'food_items_json':       _food_items_json(),
        'unread_count':   get_unread(request),
    })


@coach_required
@nutrition_required
def nutrition_view(request, pk):
    plan = get_object_or_404(NutritionPlan, pk=pk, coach=request.user)
    return render(request, 'coach/nutrition_view.html', {
        'plan':         plan,
        'unread_count': get_unread(request),
    })


@coach_required
@nutrition_required
def nutrition_copy(request, pk):
    """کپی کردن یک رژیم غذایی (همراه با تمام روزها و وعده‌ها) برای شاگرد دیگر."""
    plan = get_object_or_404(NutritionPlan, pk=pk, coach=request.user)

    if request.method == 'POST':
        target_pk = request.POST.get('target_trainee')
        target = get_object_or_404(TraineeProfile, pk=target_pk, coach=request.user)

        with transaction.atomic():
            NutritionPlan.objects.filter(trainee=target, is_active=True).update(is_active=False)

            new_plan = NutritionPlan.objects.create(
                trainee=target, coach=request.user,
                title=plan.title, description=plan.description,
                is_active=True, duration_days=plan.duration_days,
            )
            for day in plan.days.all():
                new_day = NutritionDay.objects.create(
                    plan=new_plan, day_number=day.day_number, notes=day.notes,
                )
                for meal in day.meals.all():
                    Meal.objects.create(
                        day=new_day, meal_type=meal.meal_type,
                        content=meal.content, order=meal.order,
                    )

            Notification.objects.create(
                recipient=target.user, sender=request.user, notif_type='diet_ready',
                title='رژیم غذایی جدید',
                message=f'مربی {request.user.get_full_name() or request.user.username} یک رژیم غذایی برای شما تنظیم کرد.',
            )

        messages.success(request, f'رژیم با موفقیت برای {target.user.get_full_name()} کپی شد.')
        log_activity(request.user, 'diet_copy',
                     f'{request.user.get_full_name() or request.user.username} رژیم «{plan.title}» را از «{plan.trainee.user.get_full_name() or plan.trainee.user.username}» برای «{target.user.get_full_name() or target.user.username}» کپی کرد.')
        return redirect('coach:trainee_detail', pk=target.pk)

    trainees = (TraineeProfile.objects.filter(coach=request.user)
                .exclude(pk=plan.trainee.pk).select_related('user'))
    for t in trainees:
        t.active_diet_obj = NutritionPlan.objects.filter(trainee=t, is_active=True).first()
    return render(request, 'coach/nutrition_copy.html', {
        'plan':         plan,
        'trainees':     trainees,
        'unread_count': get_unread(request),
    })


@coach_required
def nutrition_edit(request, pk):
    plan = get_object_or_404(NutritionPlan, pk=pk, coach=request.user)
    profile = plan.trainee

    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        try:
            duration_days = int(request.POST.get('duration_days', plan.duration_days))
            if duration_days <= 0:
                duration_days = plan.duration_days
        except (TypeError, ValueError):
            duration_days = plan.duration_days

        with transaction.atomic():
            plan.title       = title or plan.title
            plan.description = description
            if duration_days != plan.duration_days:
                plan.duration_days = duration_days
                plan.renewal_notified = False
            plan.save()

            plan.days.all().delete()

            for day_num, _ in NUTRITION_DAY_CHOICES:
                meals_for_day = []
                for meal_type, _ in MEAL_TYPE_CHOICES:
                    content = request.POST.get(f'day_{day_num}_{meal_type}', '').strip()
                    if content:
                        meals_for_day.append((meal_type, content))
                if not meals_for_day:
                    continue
                nday = NutritionDay.objects.create(plan=plan, day_number=day_num)
                for order, (meal_type, content) in enumerate(meals_for_day):
                    Meal.objects.create(day=nday, meal_type=meal_type, content=content, order=order)

        messages.success(request, 'رژیم غذایی ویرایش شد.')
        log_activity(request.user, 'diet_edit',
                     f'{request.user.get_full_name() or request.user.username} رژیم «{plan.title}» متعلق به «{profile.user.get_full_name() or profile.user.username}» را ویرایش کرد.')
        return redirect('coach:nutrition_view', pk=plan.pk)

    existing_meals = {}
    for day in plan.days.all():
        for meal in day.meals.all():
            existing_meals[f'{day.day_number}_{meal.meal_type}'] = meal.content

    return render(request, 'coach/nutrition_create.html', {
        'profile':        profile,
        'nutrition_day_choices': NUTRITION_DAY_CHOICES,
        'meal_type_choices':     MEAL_TYPE_CHOICES,
        'food_category_choices': FOOD_CATEGORY_CHOICES,
        'food_items_json':       _food_items_json(),
        'unread_count':   get_unread(request),
        'edit_mode':      True,
        'plan':           plan,
        'existing_meals': existing_meals,
    })



# ======== NOTIFICATIONS ========

@coach_required
def notifications(request):
    notifs   = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, 'coach/notifications.html', {
        'notifications':    notifs,
        'unread_count':     0,
    })
