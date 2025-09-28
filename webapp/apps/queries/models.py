from django.conf import settings
from django.db import models
from django.utils import timezone


class Query(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        SUCCESS = 'success', 'Completed'
        FAILED = 'failed', 'Failed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='queries')
    text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    classification = models.CharField(max_length=50, blank=True)
    resolution = models.CharField(max_length=50, blank=True)
    router_rationale = models.TextField(blank=True)
    result_data = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    task_id = models.CharField(max_length=255, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    stage = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    template = models.ForeignKey('QueryTemplate', null=True, blank=True, on_delete=models.SET_NULL, related_name='queries')

    class Meta:
        ordering = ['-created_at']

    def short_text(self):
        return (self.text[:75] + '...') if len(self.text) > 75 else self.text

    def __str__(self):
        return f"Query #{self.pk} by {self.user}"


class QueryTemplate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='query_templates')
    name = models.CharField(max_length=120)
    text = models.TextField()
    classification = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.user})"
