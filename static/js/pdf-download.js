/**
 * دانلود مستقیم PDF برنامه‌ی تمرینی — بدون باز شدن تب جدید و بدون دیالوگ چاپ.
 *
 * چطور کار می‌کنه:
 *   1. آدرس صفحه‌ی طراحی‌شده (همون تمپلیت pdf_print.html سمت سرور) رو با fetch
 *      می‌گیریم (بدون navigate کردن مرورگر، پس هیچ تب/صفحه‌ای باز نمی‌شه).
 *   2. بخش ".sheet" (خودِ برگه‌ی طراحی‌شده) رو از HTML برگشتی جدا می‌کنیم و
 *      بیرون از دید کاربر (position: fixed با left منفی) به صفحه اضافه می‌کنیم.
 *   3. با html2pdf.js (که خودش html2canvas + jsPDF رو ترکیب می‌کنه) از همون
 *      المان یک اسکرین‌شات باکیفیت می‌گیریم و به PDF تبدیلش می‌کنیم.
 *   4. چون این روش رنگ/بک‌گراند رو مستقیماً از DOM واقعی می‌خونه (نه از موتور
 *      چاپ مرورگر)، به تنظیم "Background graphics" مرورگر وابسته نیست و رنگ‌ها
 *      و استایل همیشه درست دانلود می‌شن.
 *   5. دانلود از طریق یک لینک Blob داخلی انجام می‌شه، پس هیچ تب/پنجره‌ی جدیدی
 *      باز نمی‌شه — فقط فایل مستقیم دانلود می‌شه.
 *
 * اگه به هر دلیلی (مثلاً عدم دسترسی به CDN) کتابخونه‌ی html2pdf لود نشده باشه،
 * به‌صورت خودکار به روش قدیمی (باز شدن صفحه‌ی چاپ در مرورگر) برمی‌گردیم تا
 * دانلود همیشه یه راه‌ِ جایگزین داشته باشه.
 */
function downloadProgramPDF(event, url, filename) {
  if (typeof html2pdf === 'undefined') {
    // کتابخونه لود نشده؛ به روش قدیمی (صفحه‌ی چاپ) برگرد
    return true;
  }

  event.preventDefault();
  const btn = event.currentTarget;
  const originalHTML = btn.innerHTML;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> در حال ساخت PDF...';
  btn.style.pointerEvents = 'none';
  btn.style.opacity = '0.7';

  const restore = () => {
    btn.innerHTML = originalHTML;
    btn.style.pointerEvents = '';
    btn.style.opacity = '';
  };

  fetch(url)
    .then((res) => {
      if (!res.ok) throw new Error('server-error');
      return res.text();
    })
    .then((html) => {
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const sheet = doc.querySelector('.sheet');
      const fontStyle = doc.querySelector('style');
      if (!sheet) throw new Error('sheet-not-found');

      // ظرف مخفی خارج از دید کاربر (نه display:none، چون در اون حالت
      // html2canvas نمی‌تونه المان رو رندر کنه)
      const holder = document.createElement('div');
      holder.style.position = 'fixed';
      holder.style.left = '-99999px';
      holder.style.top = '0';
      holder.style.background = '#fff';

      if (fontStyle) holder.appendChild(fontStyle.cloneNode(true));

      // حذف سایه/مارجین مخصوص پیش‌نمایش روی صفحه (اینا فقط برای toolbar بودن)
      sheet.style.margin = '0';
      sheet.style.boxShadow = 'none';
      sheet.style.maxWidth = 'none';
      holder.appendChild(sheet);
      document.body.appendChild(holder);

      const fontsReady = (document.fonts && document.fonts.ready)
        ? document.fonts.ready
        : Promise.resolve();

      return fontsReady
        .then(() => new Promise((r) => setTimeout(r, 150))) // اطمینان از رندر کامل فونت
        .then(() => html2pdf().set({
          margin: 0,
          filename: filename,
          image: { type: 'jpeg', quality: 0.98 },
          html2canvas: { scale: 2, useCORS: true, backgroundColor: '#ffffff' },
          jsPDF: { unit: 'cm', format: 'a4', orientation: 'portrait' },
          // نکته‌ی مهم: بدون این تنظیم، html2pdf صفحه رو در ارتفاع ثابتی
          // "می‌بُرد" بدون توجه به محتوا — یعنی ممکنه دقیقاً وسط یک جدول
          // قطع کنه و بقیه‌ی همون صفحه خالی بمونه. با این تنظیم، هر
          // ".day-card" به‌صورت یک واحد کامل در نظر گرفته می‌شه و اگر جا
          // نشه، کاملاً به صفحه‌ی بعد منتقل می‌شه.
          pagebreak: { mode: ['avoid-all', 'css', 'legacy'], avoid: '.day-card' },
        }).from(sheet).save())
        .finally(() => {
          document.body.removeChild(holder);
        });
    })
    .catch(() => {
      // اگه هر مرحله‌ای خطا داد، به روش قدیمی (صفحه‌ی چاپ) برگرد
      window.location.href = url;
    })
    .finally(restore);

  return false;
}
