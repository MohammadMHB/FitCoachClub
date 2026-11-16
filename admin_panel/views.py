from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.conf import settings

from accounts.models import User, TraineeProfile, ActivityLog
from accounts.activity_log import log_activity
from coach.models import (Exercise, WorkoutProgram, NutritionPlan, FoodItem,
                           CATEGORY_CHOICES, FOOD_CATEGORY_CHOICES, FOOD_UNIT_CHOICES)


def admin_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'admin':
            messages.error(request, 'دسترسی غیرمجاز.')
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def nutrition_required(view_func):
    """قابلیت رژیم غذایی فعلاً موقتاً غیرفعال است؛ دسترسی مستقیم به صفحاتش هم بسته می‌شود."""
    def wrapper(request, *args, **kwargs):
        if not settings.NUTRITION_ENABLED:
            messages.error(request, 'این قابلیت در دسترس نیست.')
            return redirect('admin_panel:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ======== DASHBOARD ========

@admin_required
def dashboard(request):
    return render(request, 'admin_panel/dashboard.html', {
        'coaches_count':   User.objects.filter(role='coach').count(),
        'trainees_count':  User.objects.filter(role='trainee').count(),
        'exercises_count': Exercise.objects.filter(is_public=True).count(),
        'programs_count':  WorkoutProgram.objects.count(),
        'recent_coaches':  User.objects.filter(role='coach').order_by('-date_joined')[:5],
        'recent_trainees': User.objects.filter(role='trainee').order_by('-date_joined')[:5],
    })


# ======== COACHES ========

@admin_required
def coach_list(request):
    coaches = User.objects.filter(role='coach').order_by('-date_joined')
    # اطمینان از اینکه هر مربی (حتی مربی‌های خیلی قدیمی) یه کد لینک داره
    for c in coaches:
        if not c.referral_code:
            c.ensure_referral_code()
    return render(request, 'admin_panel/coach_list.html', {'coaches': coaches})


@admin_required
def coach_add(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        if User.objects.filter(username=username).exists():
            messages.error(request, 'نام کاربری تکراری است.')
        else:
            first_name = request.POST.get('first_name', '').strip()
            last_name  = request.POST.get('last_name',  '').strip()
            password   = request.POST.get('password', '')
            new_coach = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role='coach',
                phone=request.POST.get('phone', '').strip(),
            )
            new_coach.last_password_plain = password
            new_coach.save(update_fields=['last_password_plain'])
            messages.success(request, 'مربی اضافه شد.')
            log_activity(request.user, 'coach_add',
                         f'{request.user.get_full_name() or request.user.username} مربی «{first_name} {last_name}» را اضافه کرد.')
            return redirect('admin_panel:coach_list')
    return render(request, 'admin_panel/coach_form.html', {'action': 'add'})


@admin_required
def coach_edit(request, pk):
    coach = get_object_or_404(User, pk=pk, role='coach')
    if request.method == 'POST':
        new_u = request.POST.get('username', '').strip()
        if new_u != coach.username and User.objects.filter(username=new_u).exists():
            messages.error(request, 'نام کاربری تکراری است.')
        else:
            coach.username   = new_u
            coach.first_name = request.POST.get('first_name', '').strip()
            coach.last_name  = request.POST.get('last_name',  '').strip()
            coach.phone      = request.POST.get('phone', '').strip()
            new_p = request.POST.get('password', '')
            if new_p:
                coach.set_password(new_p)
                coach.last_password_plain = new_p
            coach.save()
            messages.success(request, 'مربی ویرایش شد.')
            log_activity(request.user, 'coach_edit',
                         f'{request.user.get_full_name() or request.user.username} اطلاعات مربی «{coach.get_full_name() or coach.username}» را ویرایش کرد.')
            return redirect('admin_panel:coach_list')
    return render(request, 'admin_panel/coach_form.html', {'action': 'edit', 'coach': coach})


@admin_required
@require_POST
def coach_delete(request, pk):
    coach = get_object_or_404(User, pk=pk, role='coach')
    name = coach.get_full_name() or coach.username
    coach.delete()
    messages.success(request, 'مربی حذف شد.')
    log_activity(request.user, 'coach_delete',
                 f'{request.user.get_full_name() or request.user.username} مربی «{name}» را حذف کرد.')
    return redirect('admin_panel:coach_list')


@admin_required
@require_POST
def coach_toggle(request, pk):
    coach = get_object_or_404(User, pk=pk, role='coach')
    coach.is_active = not coach.is_active
    coach.save()
    messages.success(request, f'مربی {"فعال" if coach.is_active else "غیرفعال"} شد.')
    log_activity(request.user, 'coach_toggle',
                 f'{request.user.get_full_name() or request.user.username} مربی «{coach.get_full_name() or coach.username}» را '
                 f'{"فعال" if coach.is_active else "غیرفعال"} کرد.')
    return redirect('admin_panel:coach_list')


# ======== TRAINEES ========

@admin_required
def trainee_list(request):
    trainees_qs = TraineeProfile.objects.select_related('user', 'coach').order_by('-user__date_joined')
    filter_coach = None
    coach_pk = request.GET.get('coach')
    if coach_pk:
        filter_coach = get_object_or_404(User, pk=coach_pk, role='coach')
        trainees_qs = trainees_qs.filter(coach=filter_coach)

    search_query = request.GET.get('q', '').strip()
    if search_query:
        trainees_qs = trainees_qs.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__phone__icontains=search_query)
        )

    trainees = list(trainees_qs)

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
    return render(request, 'admin_panel/trainee_list.html', {
        'trainees': trainees,
        'filter_coach': filter_coach,
        'search_query': search_query,
    })


@admin_required
def trainee_detail(request, pk):
    """
    نمای کامل و فقط-خواندنی از یک شاگرد برای ادمین: مشخصات، BMI، برنامه‌ی
    تمرینی فعال (با تمام حرکات)، رژیم غذایی فعال (با تمام وعده‌ها)، و
    آرشیو برنامه‌ها/رژیم‌های قبلی — بدون نیاز به رفتن سراغ پنل مربی.
    """
    profile = get_object_or_404(
        TraineeProfile.objects.select_related('user', 'coach'), pk=pk
    )
    active_program = (
        WorkoutProgram.objects.filter(trainee=profile, is_active=True)
        .prefetch_related('days__exercises__exercise').first()
    )
    past_programs = (
        WorkoutProgram.objects.filter(trainee=profile, is_active=False)
        .order_by('-created_at').prefetch_related('days__exercises__exercise')
    )
    active_diet = (
        NutritionPlan.objects.filter(trainee=profile, is_active=True)
        .prefetch_related('days__meals').first()
    )
    past_diets = (
        NutritionPlan.objects.filter(trainee=profile, is_active=False)
        .order_by('-created_at').prefetch_related('days__meals')
    )
    return render(request, 'admin_panel/trainee_detail.html', {
        'profile':        profile,
        'active_program': active_program,
        'past_programs':  past_programs,
        'active_diet':    active_diet,
        'past_diets':     past_diets,
    })


@admin_required
def trainee_edit(request, pk):
    profile = get_object_or_404(TraineeProfile, pk=pk)
    coaches = User.objects.filter(role='coach', is_active=True)
    if request.method == 'POST':
        profile.user.first_name = request.POST.get('first_name', '').strip()
        profile.user.last_name  = request.POST.get('last_name',  '').strip()
        profile.user.phone      = request.POST.get('phone', '').strip()
        new_p = request.POST.get('password', '')
        if new_p:
            profile.user.set_password(new_p)
            profile.last_password_plain = new_p
        profile.user.save()

        cid = request.POST.get('coach')
        profile.coach = User.objects.get(pk=cid) if cid else None
        w = request.POST.get('weight')
        h = request.POST.get('height')
        a = request.POST.get('age')
        if w: profile.weight = float(w)
        if h: profile.height = float(h)
        if a: profile.age    = int(a)
        profile.save()
        messages.success(request, 'شاگرد ویرایش شد.')
        log_activity(request.user, 'trainee_edit',
                     f'{request.user.get_full_name() or request.user.username} اطلاعات شاگرد «{profile.user.get_full_name() or profile.user.username}» را ویرایش کرد.')
        return redirect('admin_panel:trainee_list')
    return render(request, 'admin_panel/trainee_edit.html', {
        'profile': profile, 'coaches': coaches,
    })


@admin_required
@require_POST
def trainee_delete(request, pk):
    profile = get_object_or_404(TraineeProfile, pk=pk)
    name = profile.user.get_full_name() or profile.user.username
    profile.user.delete()
    messages.success(request, 'شاگرد حذف شد.')
    log_activity(request.user, 'trainee_delete',
                 f'{request.user.get_full_name() or request.user.username} شاگرد «{name}» را حذف کرد.')
    return redirect('admin_panel:trainee_list')


# ======== PUBLIC EXERCISES ========

@admin_required
def exercise_list(request):
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('q', '').strip()
    # همه‌ی حرکاتی که ادمین ساخته: هم عمومی (برای همه مربی‌ها) و هم اختصاصی یک مربی خاص
    exercises = Exercise.objects.filter(coach__isnull=True).select_related('visible_to_coach')
    if category_filter:
        exercises = exercises.filter(category=category_filter)
    if search_query:
        exercises = exercises.filter(name__icontains=search_query)
    exercises = exercises.order_by('category', 'name')
    paginator = Paginator(exercises, 24)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/exercise_list.html', {
        'exercises':       page_obj,
        'page_obj':        page_obj,
        'cats':            CATEGORY_CHOICES,
        'category_filter': category_filter,
        'category_filter_label': dict(CATEGORY_CHOICES).get(category_filter, ''),
        'search_query':    search_query,
    })


@admin_required
def exercise_add(request):
    coaches = User.objects.filter(role='coach', is_active=True).order_by('first_name', 'last_name')
    if request.method == 'POST':
        target_coach_id = request.POST.get('visible_to_coach', '').strip()
        target_coach = None
        if target_coach_id:
            target_coach = get_object_or_404(User, pk=target_coach_id, role='coach')

        exercise = Exercise(
            name=request.POST.get('name', '').strip(),
            category=request.POST.get('category', ''),
            description=request.POST.get('description', '').strip(),
            video_url=request.POST.get('video_url', '').strip() or None,
            image=request.FILES.get('image'),
            video=request.FILES.get('video'),
            coach=None,
            is_public=target_coach is None,
            visible_to_coach=target_coach,
        )
        ex_name = request.POST.get('name', '').strip()
        try:
            exercise.full_clean()
        except ValidationError as e:
            for field_errors in e.message_dict.values():
                for msg in field_errors:
                    messages.error(request, msg)
            return render(request, 'admin_panel/exercise_form.html', {
                'action': 'add', 'category_choices': CATEGORY_CHOICES, 'coaches': coaches,
            })
        exercise.save()
        if target_coach:
            messages.success(request, f'حرکت اضافه شد و فقط برای {target_coach.get_full_name() or target_coach.username} نمایش داده می‌شود.')
        else:
            messages.success(request, 'حرکت عمومی اضافه شد.')
        log_activity(request.user, 'exercise_add',
                     f'{request.user.get_full_name() or request.user.username} حرکت «{ex_name}» را به بانک عمومی اضافه کرد.')
        return redirect('admin_panel:exercise_list')
    return render(request, 'admin_panel/exercise_form.html', {
        'action': 'add', 'category_choices': CATEGORY_CHOICES, 'coaches': coaches,
    })


@admin_required
def exercise_edit(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk, coach__isnull=True)
    coaches = User.objects.filter(role='coach', is_active=True).order_by('first_name', 'last_name')
    if request.method == 'POST':
        target_coach_id = request.POST.get('visible_to_coach', '').strip()
        target_coach = None
        if target_coach_id:
            target_coach = get_object_or_404(User, pk=target_coach_id, role='coach')

        exercise.name        = request.POST.get('name', '').strip()
        exercise.category    = request.POST.get('category', '')
        exercise.description = request.POST.get('description', '').strip()
        exercise.video_url   = request.POST.get('video_url', '').strip() or None
        exercise.visible_to_coach = target_coach
        exercise.is_public   = target_coach is None
        if request.FILES.get('image'): exercise.image = request.FILES['image']
        if request.POST.get('clear_video') and exercise.video:
            exercise.video.delete(save=False)
            exercise.video = None
        if request.FILES.get('video'):
            exercise.video = request.FILES['video']
        try:
            exercise.full_clean()
        except ValidationError as e:
            for field_errors in e.message_dict.values():
                for msg in field_errors:
                    messages.error(request, msg)
            return render(request, 'admin_panel/exercise_form.html', {
                'action': 'edit', 'exercise': exercise, 'category_choices': CATEGORY_CHOICES, 'coaches': coaches,
            })
        exercise.save()
        messages.success(request, 'حرکت ویرایش شد.')
        log_activity(request.user, 'exercise_edit',
                     f'{request.user.get_full_name() or request.user.username} حرکت «{exercise.name}» را ویرایش کرد.')
        return redirect('admin_panel:exercise_list')
    return render(request, 'admin_panel/exercise_form.html', {
        'action': 'edit', 'exercise': exercise, 'category_choices': CATEGORY_CHOICES, 'coaches': coaches,
    })


@admin_required
@require_POST
def exercise_delete(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk, coach__isnull=True)
    ex_name = exercise.name
    exercise.delete()
    messages.success(request, 'حرکت حذف شد.')
    log_activity(request.user, 'exercise_delete',
                 f'{request.user.get_full_name() or request.user.username} حرکت «{ex_name}» را از بانک عمومی حذف کرد.')
    return redirect('admin_panel:exercise_list')


# ======== بانک غذایی ========

@admin_required
@nutrition_required
def food_list(request):
    category_filter = request.GET.get('category', '')
    q = request.GET.get('q', '').strip()
    items = FoodItem.objects.all()
    if category_filter:
        items = items.filter(category=category_filter)
    if q:
        items = items.filter(name__icontains=q)
    items = items.order_by('category', 'name')
    return render(request, 'admin_panel/food_list.html', {
        'items':           items,
        'cats':            FOOD_CATEGORY_CHOICES,
        'category_filter': category_filter,
        'q':               q,
        'total_count':     FoodItem.objects.count(),
    })


@admin_required
@nutrition_required
def food_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'نام آیتم الزامی است.')
        else:
            FoodItem.objects.create(
                name=name,
                category=request.POST.get('category', ''),
                default_unit=request.POST.get('default_unit', 'gram'),
                default_amount=request.POST.get('default_amount', '').strip(),
            )
            messages.success(request, 'آیتم به بانک غذایی اضافه شد.')
            log_activity(request.user, 'food_add',
                         f'{request.user.get_full_name() or request.user.username} آیتم «{name}» را به بانک غذایی اضافه کرد.')
            return redirect('admin_panel:food_list')
    return render(request, 'admin_panel/food_form.html', {
        'action': 'add',
        'category_choices': FOOD_CATEGORY_CHOICES,
        'unit_choices': FOOD_UNIT_CHOICES,
    })


@admin_required
@nutrition_required
def food_edit(request, pk):
    item = get_object_or_404(FoodItem, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'نام آیتم الزامی است.')
        else:
            item.name = name
            item.category = request.POST.get('category', '')
            item.default_unit = request.POST.get('default_unit', 'gram')
            item.default_amount = request.POST.get('default_amount', '').strip()
            item.save()
            messages.success(request, 'آیتم ویرایش شد.')
            log_activity(request.user, 'food_edit',
                         f'{request.user.get_full_name() or request.user.username} آیتم «{item.name}» را در بانک غذایی ویرایش کرد.')
            return redirect('admin_panel:food_list')
    return render(request, 'admin_panel/food_form.html', {
        'action': 'edit', 'item': item,
        'category_choices': FOOD_CATEGORY_CHOICES,
        'unit_choices': FOOD_UNIT_CHOICES,
    })


@admin_required
@nutrition_required
@require_POST
def food_delete(request, pk):
    item = get_object_or_404(FoodItem, pk=pk)
    item_name = item.name
    item.delete()
    messages.success(request, 'آیتم از بانک غذایی حذف شد.')
    log_activity(request.user, 'food_delete',
                 f'{request.user.get_full_name() or request.user.username} آیتم «{item_name}» را از بانک غذایی حذف کرد.')
    return redirect('admin_panel:food_list')


# ======== گزارش فعالیت (ACTIVITY LOG) ========

@admin_required
def activity_log(request):
    logs = ActivityLog.objects.select_related('actor').all()

    action_filter = request.GET.get('action', '')
    if action_filter:
        logs = logs.filter(action=action_filter)

    paginator = Paginator(logs, 30)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'admin_panel/activity_log.html', {
        'page_obj': page_obj,
        'action_choices': ActivityLog.ACTION_CHOICES,
        'action_filter': action_filter,
        'total_count': ActivityLog.objects.count(),
    })
