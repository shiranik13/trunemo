from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import get_language


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    language = (get_language() or "en").split("-")[0]
    demo_amounts = {
        "he": ("₪2,500", "₪1,200", "₪800", "₪500"),
        "en": ("$2,500", "$1,200", "$800", "$500"),
        "ru": ("2 500 ₽", "1 200 ₽", "800 ₽", "500 ₽"),
    }
    return render(request, "home.html", {
        "demo_amounts": demo_amounts.get(language, demo_amounts["en"]),
    })


def about(request):
    return render(request, "about.html", {"github_profile_url": settings.GITHUB_PROFILE_URL})


@login_required
def profile(request):
    return render(request, "registration/profile.html")
