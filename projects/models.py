from django.utils import timezone
from django.db import models


LANG = [
    ("fr", "French"),
    ("ar", "Arabic"),
]


# Create your models here.
class ProjectProfile(models.Model):
    id = models.AutoField(primary_key=True)
    project_name = models.CharField(max_length=255)
    sector = models.CharField(max_length=120, blank=True, null=True)
    lang_preference = models.CharField(choices=LANG)
    self_assessed_stage = models.PositiveSmallIntegerField(blank=True, null=True)
    current_stage = models.PositiveSmallIntegerField(blank=True, null=True)

    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


ENGINES = [
    ('intake', 'Intake Engine'),
    ('diagnostic', 'Diagnostic Engine'),
    ('market', 'Market Scoring Engine'),
    ('commercial', 'Commercial Scoring Engine'),
    ('innovation', 'Innovation Scoring Engine'),
    ('scaling', 'Scaling Scoring Engine'),
    ('green', 'Green Scoring Engine'),
    ('unifier', 'Unified Assessment Layer'),
    ('roadmap', 'Roadmap Engine'),
    ('assistant', 'Grounded Assistant')
]

class ProfileLog(models.Model):
    project = models.ForeignKey(ProjectProfile, on_delete=models.CASCADE, related_name="logs")
    author = models.CharField(max_length=30, choices=ENGINES)
    timestamp = models.DateTimeField(auto_now_add=True)
    field_name = models.CharField(max_length=200)

    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.project_name} - {self.author}"
    class Meta:
        ordering = ['-timestamp'] #So when you do NewsArticle.objects.all() in a view, you automatically get them newest-to-oldest

