from django.urls import path

from .views import (
    DashboardView,
    SignUpView,
    create_template,
    delete_query,
    delete_template,
    export_query_results,
    pipeline_health,
    query_status,
    rerun_query,
    submit_query,
    update_tags,
)

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('submit/', submit_query, name='submit'),
    path('status/<int:pk>/', query_status, name='status'),
    path('delete/<int:pk>/', delete_query, name='delete'),
    path('tags/<int:pk>/', update_tags, name='update-tags'),
    path('rerun/<int:pk>/', rerun_query, name='rerun'),
    path('templates/create/', create_template, name='template-create'),
    path('templates/<int:pk>/delete/', delete_template, name='template-delete'),
    path('export/<int:pk>/', export_query_results, name='export'),
    path('health/', pipeline_health, name='health'),
    path('', DashboardView.as_view(), name='dashboard'),
]
