import json
from rest_framework import serializers
from django.http import QueryDict

class StrictFieldsMixin:
    """Rejects unknown fields. Use on any serializer that should not accept extra data."""
    def to_internal_value(self, data):
        unknown = set(data.keys()) - set(self.fields.keys())
        if unknown:
            raise serializers.ValidationError(
                {field: f"Invalid field: {field}" for field in unknown}
            )
        return super().to_internal_value(data)

class MultipartJsonMixin:
    """
    Parses JSON strings embedded in multipart/form-data.
    Declare fields to parse via Meta.multipart_json_fields = ['field_name'].
    """
    def to_internal_value(self, data):
        data = data.dict() if isinstance(data, QueryDict) else dict(data)
        for field in getattr(getattr(self, 'Meta', None), 'multipart_json_fields', []):
            value = data.get(field)
            if value and isinstance(value, str):
                try:
                    data[field] = json.loads(value)
                except (ValueError, TypeError):
                    pass
        return super().to_internal_value(data)

class DictSerializerMixin:
    """Bypasses to_representation — returns the instance dict as-is."""
    def to_representation(self, instance):
        return instance
