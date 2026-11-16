import re


class DemoNoticeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (response.status_code == 200 and not response.streaming
                and response.get('Content-Type', '').startswith('text/html')
                and not response.get('Content-Encoding')):
            notice = ('<div role="note" dir="rtl" style="position:relative;z-index:10000;'
                      'text-align:center;background:#664700;color:white;padding:12px">'
                      'نسخهٔ آزمایشی موقت — اطلاعات ممکن است پاک شوند؛ '
                      'از اطلاعات واقعی استفاده نکنید.</div>').encode('utf-8')
            response.content = re.sub(rb'(<body\b[^>]*>)',
                                      lambda match: match[0] + notice,
                                      response.content, count=1, flags=re.I)
            if response.has_header('Content-Length'):
                response['Content-Length'] = str(len(response.content))
        return response
