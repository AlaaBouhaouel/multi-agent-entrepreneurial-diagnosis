from django.db import models


LANG = [
    ("fr", "French"),
    ("ar", "Arabic"),
]


# Create your models here.
class ProjectProfile(models.Model):
    id = models.AutoField(primary_key=True)
    sector = models.CharField(max_length=120, blank=True, null=True)
    lang_preference = models.CharField(choices=LANG)
    self_assessed_stage = models.PositiveSmallIntegerField(blank=True, null=True)

    # Validated against projects.schemas.ProjectProfileData before writing.
    # Latest diagnosed stage is read from ProfileLog (author="diagnostic") — not stored here.
    metadata = models.JSONField(default=dict)

    # Latest roadmap snapshot (Feature 3): self-contained {diagnostic, scores,
    # roadmap, generated_at}. The grounded presenter reads its whole context from
    # here, and future roadmap animations consume this clean JSON.
    roadmap = models.JSONField(default=dict, blank=True)

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
    # Labels what this log entry contains: "diagnosis_result", "score.market", etc.
    # One entry per engine run — the full output lives in metadata.
    output_type = models.CharField(max_length=200, blank=True, default="")

    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Project #{self.project_id} - {self.author} ({self.output_type})"

    class Meta:
        ordering = ['-timestamp']

