from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def snapshot_end_times(apps, schema_editor):
    Appointment = apps.get_model("booking", "Appointment")
    Slot = apps.get_model("booking", "Slot")
    alias = schema_editor.connection.alias
    slot_end = Slot.objects.using(alias).filter(pk=OuterRef("slot_id")).values("end_time")
    Appointment.objects.using(alias).update(end_time=Subquery(slot_end))


class Migration(migrations.Migration):
    dependencies = [("booking", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="slot",
            name="withdrawn_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="appointment",
            name="end_time",
            field=models.TimeField(editable=False, null=True),
        ),
        migrations.RunPython(snapshot_end_times, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="appointment",
            name="end_time",
            field=models.TimeField(editable=False),
        ),
    ]
