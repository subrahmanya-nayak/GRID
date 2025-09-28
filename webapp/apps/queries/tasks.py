from celery import shared_task
from django.db import transaction

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
    query.save(update_fields=['status', 'task_id'])

    result = execute_biomedical_query(query.text)

    if result.get('error'):
        query.status = Query.Status.FAILED
        query.error_message = result['error']
    else:
        query.status = Query.Status.SUCCESS
        query.result_data = result.get('results', [])
        query.classification = result.get('classification') or ''
        query.error_message = ''

    with transaction.atomic():
        query.save()

    return {
        'status': query.status,
        'classification': query.classification,
    }
