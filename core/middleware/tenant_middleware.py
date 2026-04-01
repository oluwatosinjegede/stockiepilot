class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        user = getattr(request, 'user', None)

        if user and user.is_authenticated:
            request.company = getattr(user, 'company', None)
        else:
            request.company = None

        return self.get_response(request)