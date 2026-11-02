"""
URL configuration for airport_project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from boarding import views as boarding_views
from flights import views as flight_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin-panel/', include('gate.admin_urls')),
    path('', include('accounts.urls')),
    path('flights/', include('flights.urls')),
    path('booking/<int:booking_id>/confirm/', flight_views.booking_confirmation, name='booking_confirmation'),
    path('booking/<int:booking_id>/cancel/', flight_views.cancel_booking, name='cancel_booking'),
    path('my-bookings/', flight_views.my_bookings, name='my_bookings'),
    path('checkin/<int:booking_id>/', boarding_views.check_in, name='check_in'),
    path('boarding-pass/<int:pass_id>/print/', boarding_views.boarding_pass_print, name='boarding_pass_print'),
    path('boarding-pass/<int:pass_id>/qr/', boarding_views.boarding_pass_qr, name='boarding_pass_qr'),
    path('boarding-pass/<int:pass_id>/pdf/', boarding_views.boarding_pass_pdf, name='boarding_pass_pdf'),
    path('boarding-pass/<int:pass_id>/', boarding_views.boarding_pass_detail, name='boarding_pass_detail'),
    path('boarding/', include('boarding.urls')),
    path('gate/', include('gate.urls')),
]

# Serve media files during development.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
