from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Query
from .services import execute_biomedical_query


@shared_task(bind=True)
def process_query(self, query_id: int):
    try:
        query = Query.objects.get(pk=query_id)
    except Query.DoesNotExist:
        return {'status': 'missing'}

    query.status = Query.Status.RUNNING
    query.task_id = self.request.id
    query.started_at = timezone.now()
    query.stage = 'Queued'
    query.progress = 5
    query.save(update_fields=['status', 'task_id', 'started_at', 'stage', 'progress'])

    def update_progress(value: int, stage: str):
        Query.objects.filter(pk=query.pk).update(progress=value, stage=stage)

    result = execute_biomedical_query(query.text, progress_callback=update_progress)

    if result.get('error'):
        query.status = Query.Status.FAILED
        query.error_message = result['error']
        query.stage = 'Failed'
        query.progress = 100
    else:
        query.status = Query.Status.SUCCESS
        query.result_data = result.get('results', [])
        query.classification = result.get('classification') or ''
        query.resolution = result.get('resolution') or ''
        query.router_rationale = result.get('rationale') or ''
        query.error_message = ''
        query.stage = 'Completed'
        query.progress = 100

    completed_at = timezone.now()
    query.completed_at = completed_at
    if query.started_at:
        query.duration_ms = int((completed_at - query.started_at).total_seconds() * 1000)

    with transaction.atomic():
        query.save()

    return {
        'status': query.status,
        'classification': query.classification,
        'resolution': query.resolution,
    }
