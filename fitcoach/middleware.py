from django.utils.cache import add_never_cache_headers


class OnlineOnlyPagesMiddleware:
    """Keep application HTML out of the browser's HTTP cache."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.get('Content-Type', '').split(';')[0] == 'text/html':
            add_never_cache_headers(response)
        return response
