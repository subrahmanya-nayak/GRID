import csv

import requests

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import FormView, TemplateView

from .forms import QueryForm, QueryTemplateForm, SignUpForm
from .models import Query, QueryTemplate
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
        context['template_form'] = QueryTemplateForm()

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
                'resolution': query.resolution,
                'results': query.result_data or [],
                'error': query.error_message,
                'progress': query.progress,
                'stage': query.stage,
                'tags': query.tags or [],
                'router_rationale': query.router_rationale,
                'started_at': query.started_at.strftime('%Y-%m-%d %H:%M:%S') if query.started_at else None,
                'completed_at': query.completed_at.strftime('%Y-%m-%d %H:%M:%S') if query.completed_at else None,
                'duration_ms': query.duration_ms,
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
        context['templates'] = list(
            QueryTemplate.objects.filter(user=self.request.user).order_by('name')
        )
        context['templates_payload'] = [
            {
                'id': template.id,
                'name': template.name,
                'text': template.text,
                'classification': template.classification,
                'last_used_at': template.last_used_at.strftime('%Y-%m-%d %H:%M:%S') if template.last_used_at else None,
            }
            for template in context['templates']
        ]

        durations = [q.duration_ms for q in queries if q.duration_ms]
        avg_duration = sum(durations) / len(durations) if durations else 0
        context['metrics'] = {
            'avg_duration': avg_duration / 1000 if avg_duration else 0,
            'success_rate': (
                (status_counts.get('success', 0) / len(queries)) * 100 if queries else 0
            ),
            'total_queries': len(queries),
        }
        return context


@login_required
@require_POST
def submit_query(request):
    form = QueryForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    template = None
    template_id = request.POST.get('template_id')
    if template_id:
        template = QueryTemplate.objects.filter(pk=template_id, user=request.user).first()

    query = Query.objects.create(user=request.user, text=form.cleaned_data['text'], template=template)
    if template:
        template.last_used_at = timezone.now()
        template.save(update_fields=['last_used_at'])

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
        'resolution': query.resolution,
        'text': query.text,
        'results': query.result_data or [],
        'error': query.error_message,
        'created_at': query.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'progress': query.progress,
        'stage': query.stage,
        'tags': query.tags or [],
        'router_rationale': query.router_rationale,
        'started_at': query.started_at.strftime('%Y-%m-%d %H:%M:%S') if query.started_at else None,
        'completed_at': query.completed_at.strftime('%Y-%m-%d %H:%M:%S') if query.completed_at else None,
        'duration_ms': query.duration_ms,
    })


@login_required
@require_POST
def delete_query(request, pk: int):
    query = get_object_or_404(Query, pk=pk, user=request.user)
    query.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def update_tags(request, pk: int):
    query = get_object_or_404(Query, pk=pk, user=request.user)
    raw_tags = request.POST.get('tags', '')
    tags = [tag.strip() for tag in raw_tags.split(',') if tag.strip()]
    query.tags = tags
    query.save(update_fields=['tags'])
    return JsonResponse({'success': True, 'tags': tags})


@login_required
@require_POST
def rerun_query(request, pk: int):
    query = get_object_or_404(Query, pk=pk, user=request.user)
    new_query = Query.objects.create(
        user=request.user,
        text=query.text,
        template=query.template,
        tags=list(query.tags or []),
    )
    task = process_query.delay(new_query.id)
    new_query.task_id = task.id or ''
    new_query.save(update_fields=['task_id'])
    return JsonResponse({'success': True, 'query_id': new_query.id, 'task_id': new_query.task_id})


@login_required
@require_POST
def create_template(request):
    form = QueryTemplateForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    classification = request.POST.get('classification', '')
    template, created = QueryTemplate.objects.update_or_create(
        user=request.user,
        name=form.cleaned_data['name'],
        defaults={
            'text': form.cleaned_data['text'],
            'classification': classification,
            'last_used_at': None,
        }
    )

    return JsonResponse({
        'success': True,
        'id': template.id,
        'name': template.name,
        'text': template.text,
        'classification': template.classification,
        'created': created,
    })


@login_required
@require_POST
def delete_template(request, pk: int):
    template = get_object_or_404(QueryTemplate, pk=pk, user=request.user)
    template.delete()
    return JsonResponse({'success': True})


@login_required
def export_query_results(request, pk: int):
    query = get_object_or_404(Query, pk=pk, user=request.user)
    results = query.result_data or []
    if not results:
        return HttpResponse(status=204)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="query-{query.pk}-results.csv"'
    writer = csv.writer(response)
    writer.writerow(['Source', 'Title', 'Summary', 'Fields', 'Link'])
    for row in results:
        fields = row.get('fields') or []
        flattened = '; '.join(f"{item.get('label')}: {item.get('value')}" for item in fields if item.get('label'))
        writer.writerow([
            row.get('source', ''),
            row.get('title', ''),
            row.get('summary', ''),
            flattened,
            row.get('link', ''),
        ])
    return response


@login_required
def pipeline_health(request):
    celery_ok = True
    celery_error = ''
    try:
        inspector = process_query.app.control.inspect(timeout=1)
        ping = inspector.ping() if inspector else None
        celery_ok = bool(ping)
        if not celery_ok:
            celery_error = 'No active workers detected'
    except Exception as exc:  # pragma: no cover - safety net
        celery_ok = False
        celery_error = str(exc)

    checks = {}
    endpoints = {
        'clinical_trials': ('https://clinicaltrials.gov/api/info', {}),
        'open_targets': ('https://api.opentargets.io/v4/platform/publication', {'q': 'tp53', 'size': 1}),
    }
    for name, (url, params) in endpoints.items():
        try:
            response = requests.get(url, params=params, timeout=1)
            checks[name] = response.status_code < 500
            if not checks[name]:
                checks[f'{name}_status'] = response.status_code
        except Exception as exc:  # pragma: no cover - network may be unavailable
            checks[name] = False
            checks[f'{name}_error'] = str(exc)

    payload = {
        'timestamp': timezone.now().isoformat(),
        'celery_ok': celery_ok,
        'celery_error': celery_error,
        'checks': checks,
    }
    return JsonResponse(payload)
