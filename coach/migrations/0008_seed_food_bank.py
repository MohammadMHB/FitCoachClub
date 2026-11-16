from django.db import migrations


# (نام, دسته, واحد, مقدار پیشنهادی)
FOOD_ITEMS = [
    # ---- پروتئین ----
    ("سینه مرغ",            "protein", "gram",  "150"),
    ("ران مرغ",             "protein", "gram",  "150"),
    ("مرغ کبابی",           "protein", "gram",  "150"),
    ("گوشت گوسفند",         "protein", "gram",  "120"),
    ("گوشت گوساله",         "protein", "gram",  "120"),
    ("گوشت چرخ‌کرده",       "protein", "gram",  "120"),
    ("ماهی قزل‌آلا",        "protein", "gram",  "150"),
    ("ماهی سالمون",         "protein", "gram",  "150"),
    ("ماهی تن (کنسرو)",     "protein", "gram",  "100"),
    ("میگو",                "protein", "gram",  "120"),
    ("تخم‌مرغ",              "protein", "piece", "2"),
    ("سفیده تخم‌مرغ",       "protein", "piece", "3"),
    ("جگر مرغ",             "protein", "gram",  "100"),
    ("جگر گوساله",          "protein", "gram",  "100"),
    ("گوشت بوقلمون",        "protein", "gram",  "150"),
    ("سوسیس کم‌چرب",        "protein", "gram",  "60"),
    ("کالباس کم‌چرب",       "protein", "gram",  "50"),

    # ---- نان، غلات و نشاسته ----
    ("برنج سفید",           "carb", "gram", "150"),
    ("برنج قهوه‌ای",        "carb", "gram", "150"),
    ("نان سنگک",            "carb", "slice", "1"),
    ("نان لواش",            "carb", "slice", "2"),
    ("نان بربری",           "carb", "slice", "1"),
    ("نان تست",             "carb", "slice", "2"),
    ("ماکارونی",            "carb", "gram", "100"),
    ("پاستا سبوس‌دار",      "carb", "gram", "100"),
    ("سیب‌زمینی",           "carb", "gram", "150"),
    ("سیب‌زمینی پخته",      "carb", "piece", "1"),
    ("جو دوسر (اوتمیل)",   "carb", "cup",  "1"),
    ("کینوا",               "carb", "gram", "100"),
    ("نان جو",              "carb", "slice", "2"),
    ("ذرت مکزیکی",         "carb", "gram", "100"),

    # ---- لبنیات ----
    ("شیر کم‌چرب",          "dairy", "cup", "1"),
    ("ماست کم‌چرب",         "dairy", "cup", "1"),
    ("ماست یونانی",         "dairy", "cup", "1"),
    ("پنیر سفید",           "dairy", "gram", "30"),
    ("پنیر پیتزا",          "dairy", "gram", "30"),
    ("پنیر کاتیج",          "dairy", "gram", "100"),
    ("دوغ",                 "dairy", "cup", "1"),
    ("خامه",                "dairy", "tbsp", "1"),
    ("کره",                 "dairy", "tsp", "1"),

    # ---- سبزیجات ----
    ("خیار",                "vegetable", "piece", "1"),
    ("گوجه‌فرنگی",          "vegetable", "piece", "1"),
    ("کاهو",                "vegetable", "cup", "1"),
    ("فلفل دلمه‌ای",        "vegetable", "piece", "1"),
    ("هویج",                "vegetable", "piece", "1"),
    ("کدو سبز",             "vegetable", "piece", "1"),
    ("بادمجان",             "vegetable", "piece", "1"),
    ("اسفناج",              "vegetable", "cup", "1"),
    ("کلم بروکلی",          "vegetable", "cup", "1"),
    ("کلم پیچ",             "vegetable", "cup", "1"),
    ("پیاز",                "vegetable", "piece", "1"),
    ("سیر",                 "vegetable", "piece", "2"),
    ("قارچ",                "vegetable", "gram", "100"),
    ("ذرت شیرین",           "vegetable", "tbsp", "2"),
    ("لوبیا سبز",           "vegetable", "gram", "100"),
    ("سالاد فصل",           "vegetable", "plate", "1"),

    # ---- میوه‌ها ----
    ("سیب",                 "fruit", "piece", "1"),
    ("موز",                 "fruit", "piece", "1"),
    ("پرتقال",              "fruit", "piece", "1"),
    ("نارنگی",              "fruit", "piece", "1"),
    ("انگور",               "fruit", "cup", "1"),
    ("هندوانه",             "fruit", "slice", "1"),
    ("خربزه",               "fruit", "slice", "1"),
    ("توت‌فرنگی",           "fruit", "cup", "1"),
    ("کیوی",                "fruit", "piece", "1"),
    ("انبه",                "fruit", "piece", "1"),
    ("گلابی",               "fruit", "piece", "1"),
    ("آلبالو",              "fruit", "cup", "1"),
    ("هلو",                 "fruit", "piece", "1"),
    ("انار",                "fruit", "piece", "1"),
    ("خرما",                "fruit", "piece", "3"),
    ("کشمش",                "fruit", "tbsp", "2"),
    ("انجیر خشک",           "fruit", "piece", "2"),

    # ---- حبوبات ----
    ("عدس",                 "legume", "gram", "100"),
    ("لوبیا قرمز",          "legume", "gram", "100"),
    ("لوبیا چیتی",          "legume", "gram", "100"),
    ("نخود",                "legume", "gram", "100"),
    ("لپه",                 "legume", "gram", "100"),
    ("ماش",                 "legume", "gram", "100"),

    # ---- چربی‌ها و آجیل ----
    ("روغن زیتون",          "fat_nut", "tbsp", "1"),
    ("روغن کنجد",           "fat_nut", "tsp", "1"),
    ("کره بادام‌زمینی",     "fat_nut", "tbsp", "1"),
    ("بادام",               "fat_nut", "gram", "20"),
    ("گردو",                "fat_nut", "gram", "20"),
    ("پسته",                "fat_nut", "gram", "20"),
    ("بادام‌زمینی",         "fat_nut", "gram", "20"),
    ("فندق",                "fat_nut", "gram", "20"),
    ("دانه چیا",            "fat_nut", "tbsp", "1"),
    ("دانه کتان",           "fat_nut", "tbsp", "1"),
    ("تخمه آفتابگردان",     "fat_nut", "gram", "20"),
    ("آووکادو",             "fat_nut", "piece", "0.5"),

    # ---- نوشیدنی ----
    ("آب",                  "drink", "cup", "1"),
    ("چای",                 "drink", "cup", "1"),
    ("قهوه",                "drink", "cup", "1"),
    ("دمنوش گیاهی",        "drink", "cup", "1"),
    ("آب‌میوه طبیعی",       "drink", "cup", "1"),
    ("نوشابه رژیمی",        "drink", "cup", "1"),

    # ---- شیرینی و دسر ----
    ("عسل",                 "sweet", "tsp", "1"),
    ("مربا",                "sweet", "tbsp", "1"),
    ("شکلات تلخ",           "sweet", "gram", "20"),
    ("بیسکویت ساده",        "sweet", "piece", "2"),
    ("ژله رژیمی",           "sweet", "cup", "1"),

    # ---- ادویه و چاشنی ----
    ("نمک",                 "sauce_spice", "tsp", "0.25"),
    ("فلفل سیاه",           "sauce_spice", "tsp", "0.25"),
    ("زردچوبه",             "sauce_spice", "tsp", "0.5"),
    ("دارچین",              "sauce_spice", "tsp", "0.5"),
    ("لیمو ترش",            "sauce_spice", "piece", "1"),
    ("آبلیمو",              "sauce_spice", "tbsp", "1"),
    ("سرکه",                "sauce_spice", "tbsp", "1"),
    ("رب گوجه‌فرنگی",       "sauce_spice", "tbsp", "1"),
    ("سس گوجه",             "sauce_spice", "tbsp", "1"),

    # ---- مکمل ----
    ("پروتئین وی",          "supplement", "serving", "1"),
    ("کراتین",              "supplement", "gram", "5"),
    ("مولتی‌ویتامین",       "supplement", "piece", "1"),
    ("امگا۳",               "supplement", "piece", "1"),
    ("BCAA",                "supplement", "serving", "1"),

    # ---- فست‌فود و غذای آماده ----
    ("پیتزا",               "fast_food", "slice", "2"),
    ("همبرگر",              "fast_food", "piece", "1"),
    ("سیب‌زمینی سرخ‌کرده",  "fast_food", "serving", "1"),

    # ---- سوپ، آش و خورش ----
    ("سوپ جو",              "soup_stew", "cup", "1"),
    ("آش رشته",             "soup_stew", "cup", "1"),
    ("خورش قیمه",           "soup_stew", "serving", "1"),
    ("خورش قرمه‌سبزی",      "soup_stew", "serving", "1"),
    ("عدسی",                "soup_stew", "cup", "1"),
]


def seed_food_items(apps, schema_editor):
    FoodItem = apps.get_model('coach', 'FoodItem')
    existing_names = set(FoodItem.objects.values_list('name', flat=True))
    to_create = [
        FoodItem(name=name, category=cat, default_unit=unit, default_amount=amount)
        for name, cat, unit, amount in FOOD_ITEMS
        if name not in existing_names
    ]
    FoodItem.objects.bulk_create(to_create)


def remove_seeded_food_items(apps, schema_editor):
    FoodItem = apps.get_model('coach', 'FoodItem')
    seeded_names = [item[0] for item in FOOD_ITEMS]
    FoodItem.objects.filter(name__in=seeded_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('coach', '0007_fooditem'),
    ]

    operations = [
        migrations.RunPython(seed_food_items, remove_seeded_food_items),
    ]
