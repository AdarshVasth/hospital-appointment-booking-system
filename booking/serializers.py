from rest_framework import serializers

from .models import Doctor, Slot, Specialty


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "name"]


class DoctorSerializer(serializers.ModelSerializer):
    specialty = SpecialtySerializer()

    class Meta:
        model = Doctor
        fields = ["id", "name", "specialty", "experience", "fee", "bio"]


class SlotSerializer(serializers.ModelSerializer):
    reserved = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Slot
        fields = ["id", "date", "start_time", "end_time", "reserved"]


class BookSerializer(serializers.Serializer):
    slot = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500)


class CompleteSerializer(serializers.Serializer):
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class AvailabilitySerializer(serializers.Serializer):
    doctor = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
