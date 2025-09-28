from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import FormView, TemplateView

from .forms import QueryForm, SignUpForm
from .models import Query
from .tasks import process_query


class SignUpView(FormView):
    template_name = 'registration/signup.html'
    form_class = SignUpForm
    success_url = reverse_lazy('queries:dashboard')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, 'Welcome! Your account has been created.')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'queries/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = QueryForm()

        queries = list(
            Query.objects.filter(user=self.request.user).order_by('-created_at')
        )
        context['queries_payload'] = [
            {
                'id': query.id,
                'text': query.text,
                'created_at': query.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'status': query.status,
                'classification': query.classification,
                'results': query.result_data or [],
                'error': query.error_message,
            }
            for query in queries
        ]
        context['history'] = queries
        status_counts = {'pending': 0, 'running': 0, 'success': 0, 'failed': 0}
        for query in queries:
            status_counts[query.status] = status_counts.get(query.status, 0) + 1
        context['status_counts'] = status_counts
        context['active_count'] = status_counts.get('pending', 0) + status_counts.get('running', 0)
        context['last_activity'] = queries[0].created_at if queries else None
        return context


@login_required
@require_POST
def submit_query(request):
    form = QueryForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    query = Query.objects.create(user=request.user, text=form.cleaned_data['text'])
    task = process_query.delay(query.id)
    query.task_id = task.id or ''
    query.save(update_fields=['task_id'])

    return JsonResponse({'success': True, 'query_id': query.id, 'task_id': query.task_id})


@login_required
def query_status(request, pk: int):
    query = get_object_or_404(Query, pk=pk, user=request.user)
    return JsonResponse({
        'id': query.id,
        'status': query.status,
        'classification': query.classification,
        'results': query.result_data or [],
        'error': query.error_message,
        'created_at': query.created_at.strftime('%Y-%m-%d %H:%M:%S'),
    })


@login_required
@require_POST
def delete_query(request, pk: int):
    query = get_object_or_404(Query, pk=pk, user=request.user)
    query.delete()
    return JsonResponse({'success': True})
