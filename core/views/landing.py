from django.shortcuts import render
from django.db.models import Sum, Count
from core.models import Stall, Tenant, RentalContract, Billing, SystemSetting


def landing_view(request):
    if request.user.is_authenticated:
        # Authenticated users can still see landing but we provide dashboard shortcut
        pass

    settings = SystemSetting.objects.first()
    total_stalls = Stall.objects.count() or 120
    total_tenants = Tenant.objects.filter(status='Active').count() or 86
    occupied = Stall.objects.filter(status='Occupied').count() or 86
    vacant = Stall.objects.filter(status='Vacant').count() or 34
    occupancy_rate = round((occupied / total_stalls * 100) if total_stalls else 0, 1)

    # Fallback demo numbers if DB empty
    if total_stalls == 0:
        total_stalls = 128
        total_tenants = 94
        occupied = 94
        vacant = 34
        occupancy_rate = 73.4

    context = {
        'system_settings': settings,
        'total_stalls': total_stalls,
        'total_tenants': total_tenants,
        'occupied': occupied,
        'vacant': vacant,
        'occupancy_rate': occupancy_rate,
    }
    return render(request, 'landing.html', context)
