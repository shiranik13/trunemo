from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "home.html")


def about(request):
    return render(request, "about.html", {"github_profile_url": settings.GITHUB_PROFILE_URL})


@login_required
def profile(request):
    return render(request, "registration/profile.html")
