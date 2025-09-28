from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('queries/', include(('apps.queries.urls', 'queries'), namespace='queries')),
    path('', RedirectView.as_view(pattern_name='queries:dashboard', permanent=False)),
]
