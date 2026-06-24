from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


class RequireLoginMiddleware:
    """
    Require authentication for all app routes by default.
    Exempts login/logout/admin auth/static/media paths.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or "/"
        login_url = reverse("login")

        exempt_prefixes = [
            login_url,
            reverse("logout"),
            reverse("logged_out"),
            "/admin/",
        ]
        static_url = getattr(settings, "STATIC_URL", None)
        media_url = getattr(settings, "MEDIA_URL", None)
        for prefix in (static_url, media_url):
            # Guard against broad defaults like "/" that would exempt everything.
            if prefix and prefix != "/":
                exempt_prefixes.append(prefix)

        is_exempt = any(path.startswith(prefix) for prefix in exempt_prefixes)
        if not request.user.is_authenticated and not is_exempt:
            if path.startswith("/api/"):
                return JsonResponse(
                    {"error": "authentication_required", "detail": "Login required."},
                    status=401,
                )
            return redirect(f"{login_url}?next={path}")

        return self.get_response(request)
