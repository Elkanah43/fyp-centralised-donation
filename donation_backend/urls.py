from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from donation.views import home_view, robots_view, sitemap_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('robots.txt', robots_view, name='robots'),
    path('sitemap.xml', sitemap_view, name='sitemap'),
    path('api/', include('donation.urls')),
]
