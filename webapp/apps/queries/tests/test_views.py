from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.queries.models import Query, QueryTemplate


class DashboardViewTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='alice', email='alice@example.com', password='password123'
        )
        self.client.force_login(self.user)

    def test_dashboard_includes_structured_results(self) -> None:
        query = Query.objects.create(
            user=self.user,
            text='BRCA1 clinical trials',
            status=Query.Status.SUCCESS,
            classification='clinical_trials',
            resolution='clinical_trials',
            router_rationale='Routed to clinical trials dataset.',
            result_data=[
                {
                    'source': 'ClinicalTrials.gov',
                    'title': 'Trial A',
                    'summary': 'Important summary',
                    'fields': [
                        {'label': 'Trial phase', 'value': 'Phase 2'},
                        {'label': 'Condition', 'value': 'Oncology'},
                        {'label': 'Evidence score', 'value': '0.8'},
                    ],
                    'link': 'https://clinicaltrials.gov/trial-a',
                }
            ],
            progress=100,
            stage='Completed',
            started_at=timezone.now() - timedelta(minutes=5),
            completed_at=timezone.now() - timedelta(minutes=1),
            duration_ms=240000,
            tags=['oncology'],
        )
        QueryTemplate.objects.create(
            user=self.user,
            name='BRCA template',
            text='Investigate BRCA1 trials',
            classification='clinical_trials',
            last_used_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(reverse('queries:dashboard'))
        self.assertContains(response, 'Latest results')
        payload = response.context['queries_payload'][0]
        self.assertEqual(payload['id'], query.id)
        self.assertEqual(payload['results'][0]['fields'][0]['label'], 'Trial phase')
        self.assertIn('avg_duration', response.context['metrics'])
        self.assertEqual(response.context['templates'][0].name, 'BRCA template')

    @patch('apps.queries.views.process_query.delay')
    def test_submit_query_creates_task(self, mock_delay: MagicMock) -> None:
        mock_delay.return_value = MagicMock(id='task-123')
        response = self.client.post(reverse('queries:submit'), {'text': 'Find TP53 evidence'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        query = Query.objects.get(pk=payload['query_id'])
        self.assertEqual(query.status, Query.Status.PENDING)
        mock_delay.assert_called_once_with(query.id)

    def test_query_status_endpoint(self) -> None:
        query = Query.objects.create(
            user=self.user,
            text='BRCA1 clinical trials',
            status=Query.Status.RUNNING,
            progress=50,
            stage='Fetching',
            router_rationale='Testing',
        )
        response = self.client.get(reverse('queries:status', args=[query.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['progress'], 50)
        self.assertEqual(payload['stage'], 'Fetching')

    def test_export_results_generates_csv(self) -> None:
        query = Query.objects.create(
            user=self.user,
            text='Exportable query',
            status=Query.Status.SUCCESS,
            result_data=[
                {
                    'source': 'ClinicalTrials.gov',
                    'title': 'Trial 1',
                    'summary': 'Summary',
                    'fields': [{'label': 'Phase', 'value': 'II'}],
                    'link': 'https://example.com/trial-1',
                }
            ],
        )
        response = self.client.get(reverse('queries:export', args=[query.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('ClinicalTrials.gov', response.content.decode())

    @patch('apps.queries.views.process_query.delay')
    def test_rerun_query_clones_existing(self, mock_delay: MagicMock) -> None:
        original = Query.objects.create(user=self.user, text='Original query', tags=['a'])
        mock_delay.return_value = MagicMock(id='task-456')
        response = self.client.post(reverse('queries:rerun', args=[original.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(Query.objects.filter(pk=payload['query_id']).exists())
        self.assertNotEqual(payload['query_id'], original.id)
        mock_delay.assert_called_once()

    def test_update_tags(self) -> None:
        query = Query.objects.create(user=self.user, text='Tag me')
        response = self.client.post(reverse('queries:update-tags', args=[query.id]), {'tags': 'one, two'})
        self.assertEqual(response.status_code, 200)
        query.refresh_from_db()
        self.assertEqual(query.tags, ['one', 'two'])

    def test_pipeline_health_endpoint(self) -> None:
        with patch('apps.queries.views.process_query') as mock_task, patch('apps.queries.views.requests.get') as mock_get:
            inspector = MagicMock()
            inspector.ping.return_value = {'worker': 'pong'}
            mock_task.app.control.inspect.return_value = inspector
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            response = self.client.get(reverse('queries:health'))
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload['celery_ok'])
            self.assertTrue(payload['checks']['clinical_trials'])
            self.assertTrue(payload['checks']['open_targets'])


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class TemplateWorkflowTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='bob', email='bob@example.com', password='password123'
        )
        self.client.force_login(self.user)

    @patch('apps.queries.views.process_query.delay')
    def test_create_and_run_template(self, mock_delay: MagicMock) -> None:
        mock_delay.return_value = MagicMock(id='task-789')
        create_response = self.client.post(
            reverse('queries:template-create'),
            {'name': 'Repeatable prompt', 'text': 'Investigate TP53'}
        )
        self.assertEqual(create_response.status_code, 200)
        template_id = create_response.json()['id']

        run_response = self.client.post(reverse('queries:submit'), {'text': 'Investigate TP53', 'template_id': template_id})
        self.assertEqual(run_response.status_code, 200)
        self.assertTrue(Query.objects.filter(template_id=template_id).exists())
        mock_delay.assert_called()
