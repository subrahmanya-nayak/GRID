from django.urls import path

from .views import DashboardView, SignUpView, delete_query, query_status, submit_query

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('submit/', submit_query, name='submit'),
    path('status/<int:pk>/', query_status, name='status'),
    path('delete/<int:pk>/', delete_query, name='delete'),
    path('', DashboardView.as_view(), name='dashboard'),
]
