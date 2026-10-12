"""Backdate the seeded demo account so its commitments and projects look lived-in.

Commitments only count time logged after they were created, and projects start
on the day they were made, so straight after seed_demo.py every goal shows 0%.
Run this inside the throwaway AutumnWeb (never a real database), from the
AutumnWeb checkout:

    python manage.py shell < ../Autumn/scripts/demo/backdate_demo.py
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.db.models import Min

from core.models import Commitment, CommitmentRevision, Projects, Sessions

for commitment in Commitment.objects.all():
    anchor = datetime.combine(commitment.start_date, time(), ZoneInfo(commitment.timezone))
    commitment.ledger_start_at = anchor
    commitment.needs_recompute = True
    commitment.balance = 0
    commitment.save(update_fields=["ledger_start_at", "needs_recompute", "balance"])
    CommitmentRevision.objects.filter(commitment=commitment).update(effective_from_instant=anchor)

for project in Projects.objects.all():
    first = Sessions.objects.filter(project=project).aggregate(first=Min("start_time"))["first"]
    if first:
        Projects.objects.filter(pk=project.pk).update(start_date=first)

print("Backdated commitments and project start dates.")
