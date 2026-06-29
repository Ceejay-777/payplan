# CeeJay — Django REST Framework Style Guide

> This is not a "best practices" document. It's how I write code.
> Agents working on my projects should treat this as the source of truth
> for architectural decisions, naming, patterns, and anti-patterns.
> When in doubt, do it the way this guide says — not the way the Django
> or DRF docs suggest.

---

## Philosophy

I build production Django REST Framework APIs with a **service-oriented, layer-separated architecture**.

- **Views orchestrate. Services execute. Serializers validate.**
- **Explicit over implicit** — I'd rather write 10 obvious lines than 2 clever ones.
- **Thin models** — models hold state, computed properties, and state-transition methods. Business logic belongs in services.
- **Querysets are free** — optimizing a queryset costs nothing. Forgetting to costs everything.
- **Side effects are the service's job** — views should never know that creating a record also updates a cache or sends a notification. That's the service's contract.
- **Validation is the serializer's job** — by the time a service is called, the data is already clean. No defensive programming inside services.
- **Names are contracts** — `get_<model>()` returns an object or raises `NotFound`. `list_<models>()` returns a queryset. Breaking that contract is a bug.

This guide reflects patterns confirmed across multiple production projects. The services layer is a newer adoption — new code should use it; older apps may not have it consistently.

---

## Project & App Structure

### Directory Layout

```
project-backend/
├── project/                  # Project package: settings, permissions, base models, utils
│   ├── models.py             # BaseModel (soft-delete + sqid)
│   ├── permissions.py        # Role-based permission classes
│   ├── views.py              # Base view classes (PublicGenericAPIView)
│   ├── mixins.py             # Reusable serializer mixins (project-level)
│   └── utils/                # Utilities as a package, not a single file
│       ├── email_service.py
│       ├── exception_handler.py
│       ├── generate.py
│       └── helper_services.py
├── core/                     # User management & authentication
├── <domain_app>/             # Feature domain (appointments, records, lab, etc.)
├── <service_app>/            # Cross-cutting service (notifications, payments)
└── <admin_app>/              # Internal admin tooling (separate from Django admin)
```

### App Organization

Every app follows this structure. Files are only created when needed — don't create `services.py` for an app that has no business logic.

```
<app>/
├── models.py           # Data models (inherit from BaseModel)
├── serializers.py      # Request/response validation
├── views.py            # API endpoints — or a views/ package if the app serves multiple roles
├── urls.py             # URL routing
├── services.py         # Business logic (create when logic outgrows the view)
├── selectors.py        # Complex data retrieval (create when queries get complex)
├── filters.py          # django-filter FilterSet classes
├── requests.py         # Outbound HTTP calls to external services
├── permissions.py      # App-specific permission classes
├── plugins.py          # Polymorphic behavior registry
├── tasks.py            # Background tasks
├── webhooks.py         # Webhook routing view
├── webhookshandlers.py # One handler function per webhook event
└── admin.py
```

### Splitting Views by Role

When an app serves multiple distinct user types, split views into a `views/` package:

```
accounts/
└── views/
    ├── __init__.py
    ├── hospital_views.py
    ├── patient_views.py
    └── shared_views.py
```

Don't do this prematurely. A single `views.py` is fine until it's unwieldy.

---

## Base Model

```python
# project/models.py
from django.db import models
from django.utils import timezone
from django_sqids import SqidsField

class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class BaseModel(models.Model):
    sqid = SqidsField(real_field_name="id", min_length=7)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ActiveManager()       # Filters out soft-deleted records
    all_objects = models.Manager()  # Returns everything

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    class Meta:
        abstract = True
```

All models inherit from `BaseModel`. The `objects` manager always excludes soft-deleted records. Use `all_objects` only when you explicitly need deleted records (audit trails, admin).

---

## Models

### Enums — Always Nested as Inner Classes

```python
class Appointment(BaseModel):
    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    class Mode(models.TextChoices):
        IN_PERSON = 'in_person', 'In Person'
        VIRTUAL   = 'virtual',   'Virtual'

    status = models.CharField(choices=Status.choices, max_length=20, default=Status.PENDING)
    mode   = models.CharField(choices=Mode.choices, max_length=20)
```

Never use raw string literals for choices anywhere in the codebase. Always reference the enum: `Appointment.Status.PENDING`, not `"pending"`.

### Field Conventions

```python
# Timestamps: always use _at suffix
created_at    = models.DateTimeField(auto_now_add=True)
updated_at    = models.DateTimeField(auto_now=True)
responded_at  = models.DateTimeField(null=True, blank=True)
deleted_at    = models.DateTimeField(null=True, blank=True)

# Booleans: always prefix with is_
is_active   = models.BooleanField(default=True)
is_deleted  = models.BooleanField(default=False)
is_verified = models.BooleanField(default=False)

# Dynamic defaults: use callable, not evaluated value
start_date = models.DateTimeField(default=timezone.now)   # ✅
start_date = models.DateTimeField(default=timezone.now()) # ❌ evaluated once at import

# Validators inline on the field
duration_mins = models.IntegerField(default=60, validators=[MinValueValidator(0)])
discount_perc = models.DecimalField(
    max_digits=5, decimal_places=2, default=0,
    validators=[MinValueValidator(0), MaxValueValidator(100)]
)
```

### Properties for Computed Values

```python
@property
def discounted_price(self):
    if self.discount_perc and self.discount_perc > 0:
        amount = (self.discount_perc / Decimal("100")) * self.price
        return self.price - amount
    return self.price

@property
def is_active(self):
    return self.status == self.Status.ACTIVE
```

### State Transition Methods

Explicit methods for state changes — never update status fields directly from outside the model.

```python
def accept(self):
    self.status = self.Status.ACCEPTED
    self.responded_at = timezone.now()
    self.save(update_fields=['status', 'responded_at'])

def cancel(self):
    self.status = self.Status.CANCELLED
    self.save(update_fields=['status'])

def update_status(self, status):
    self.status = status
    self.save(update_fields=['status'])
```

Always pass `update_fields` to `save()`. Never call a bare `self.save()` from a state transition method — it's wasteful and masks intent.

### Multi-Step Validation Methods

Return `(bool, str)` tuples — never raise from model methods:

```python
def verify(self, token):
    if self.verified:
        return False, "Token already used"
    if self.is_expired():
        return False, "Token has expired"
    if self.token != token:
        return False, "Invalid token"

    self.verified = True
    self.save(update_fields=["verified"])
    return True, "Token verified successfully"
```

### Factory Classmethods

```python
@classmethod
def generate_for_user(cls, user, expiry_minutes=10):
    """Create or replace a token for a user."""
    token  = generate_token()
    expiry = timezone.now() + timedelta(minutes=expiry_minutes)
    instance, _ = cls.objects.update_or_create(
        user=user,
        defaults={"token": token, "expiry": expiry, "verified": False}
    )
    return instance
```

### `__str__` Methods

Include context. A name alone is useless in the Django admin or logs.

```python
def __str__(self):
    return f"{self.patient.full_name} — {self.appointment_date:%Y-%m-%d}"

def __str__(self):
    return f"{self.email} ({self.role})"
```

### RelatedName Pattern for Polymorphic Relations

```python
user = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    related_name='%(app_label)s_engagements'
    # Becomes: internships_engagements, mentorships_engagements, etc.
)
```

---

## Serializers

### All Custom Validation Goes in `validate()`

Never put business logic in field-level validators. `validate()` is where all cross-field validation, object lookups, and permission checks happen.

```python
class CreateAppointmentSerializer(serializers.Serializer):
    doctor   = serializers.SlugField()
    date     = serializers.DateTimeField()
    mode     = serializers.ChoiceField(choices=Appointment.Mode.choices)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        patient = self.context["request"].user
        doctor  = get_object_or_404(DoctorProfile, sqid=attrs.pop('doctor'))

        if not doctor.is_accepting_appointments:
            raise ValidationError("This doctor is not accepting appointments.")

        if attrs['date'] < timezone.now():
            raise ValidationError("Appointment date cannot be in the past.")

        # Store validated objects for use in create()
        self.patient = patient
        self.doctor  = doctor

        return attrs
```

### Storing Validated State as Instance Attributes

After validation, store looked-up objects as `self.<name>` so `create()` doesn't have to look them up again.

```python
def validate(self, attrs):
    self.user     = self.context["request"].user
    self.instance = get_object_or_404(<Model>, sqid=attrs.pop('slug'))
    return attrs

def create(self, validated_data):
    return create_model(
        user=self.user,
        instance=self.instance,
        **validated_data
    )
```

### Custom `create()` — Explicit Nested Handling

```python
def create(self, validated_data):
    profile_data = validated_data.pop('profile')
    image        = profile_data.pop('image', None)

    validated_data['role'] = User.Role.PATIENT
    user = User.objects.create_user(**validated_data)
    Profile.objects.create(user=user, **profile_data)

    if image:
        image.user = user
        image.save()

    return user
```

### Custom `update()` — Delegate to Service

```python
def update(self, instance, validated_data):
    return update_appointment(
        appointment=instance,
        date=validated_data.get("date"),
        mode=validated_data.get("mode"),
        metadata=validated_data.get("metadata"),
    )
```

### Field Patterns

```python
# List fields
tags = serializers.ListField(child=serializers.CharField(), required=False)

# FK by slug, not raw ID
doctor = serializers.SlugRelatedField(
    queryset=DoctorProfile.objects.all(),
    slug_field='sqid',
    required=True
)

# Nested read-only representation
doctor_info = DoctorDetailSerializer(source="doctor", read_only=True)

# Computed read-only
thumbnail_url = serializers.SerializerMethodField(read_only=True)

def get_thumbnail_url(self, obj):
    return obj.image.url if obj.image else None
```

### Meta — Be Explicit

```python
class Meta:
    model  = Appointment
    fields = ['sqid', 'doctor_info', 'date', 'mode', 'status', 'created_at']
    read_only_fields = fields

# OR

class Meta:
    model   = Appointment
    exclude = ['id', 'is_deleted', 'deleted_at']
```

Never use `fields = '__all__'`. It's a liability — new fields get exposed automatically.

### Project-Level Serializer Mixins

These live in `project/mixins.py` and are available to all apps:

```python
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
```

---

## Views

### No ViewSets. No Routers. Ever.

```python
# ❌ Not my pattern
router = DefaultRouter()
router.register(r'appointments', AppointmentViewSet)

# ✅ My pattern
path('appointments', ListAppointmentsView.as_view(), name='list-appointments'),
path('appointments/create', CreateAppointmentView.as_view(), name='create-appointment'),
path('appointments/<slug:sqid>', RetrieveAppointmentView.as_view(), name='retrieve-appointment'),
```

Explicit paths are searchable, debuggable, and don't hide behavior behind router magic.

### Base Classes

```python
# Default — requires authentication (set globally in settings)
class CreateAppointmentView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]

# Role-based
class DoctorDashboardView(generics.ListAPIView):
    permission_classes = [IsAuthenticatedDoctor | IsAuthenticatedAdmin]

# Public — no auth (login, signup, webhooks)
from project.views import PublicGenericAPIView

class SignupView(generics.CreateAPIView, PublicGenericAPIView):
    serializer_class = SignupSerializer
```

### `perform_create` / `perform_update` Pattern

```python
class CreateAppointmentView(generics.CreateAPIView):
    serializer_class   = CreateAppointmentSerializer
    permission_classes = [IsAuthenticatedPatient]

    def perform_create(self, serializer):
        self.appointment = create_appointment(**serializer.validated_data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            AppointmentSerializer(self.appointment).data,
            status=status.HTTP_201_CREATED
        )
```

### Transaction Safety

```python
@transaction.atomic
def perform_create(self, serializer):
    user  = serializer.save()
    token = VerificationToken.generate_for_user(user)
    # Email sends outside the atomic block — network calls don't belong inside transactions
    transaction.on_commit(lambda: send_verification_email(user, token))
```

Side effects that shouldn't roll back (emails, notifications, cache invalidation) go in `transaction.on_commit()`, not inside the atomic block.

### Response Shaping

```python
def post(self, request, *args, **kwargs):
    response = super().post(request, *args, **kwargs)

    if response.status_code == status.HTTP_200_OK:
        set_refresh_cookie(response)
        user = User.objects.get(email=request.data.get("email"))
        response.data["role"]    = user.role
        response.data["user_id"] = user.sqid
        response.data["profile"] = user.profile.sqid

    return response
```

### `get_queryset` — Always Optimize

```python
def get_queryset(self):
    return Appointment.objects.filter(
        patient=self.request.user
    ).select_related(
        "patient", "doctor", "doctor__profile"
    ).prefetch_related(
        "notes", "attachments"
    ).order_by("-created_at")
```

### Schema Documentation

```python
@extend_schema(
    tags=["Appointments"],
    summary="Book an appointment with a doctor",
    description="Creates a pending appointment. Doctor must be accepting appointments.",
)
class CreateAppointmentView(generics.CreateAPIView):
    ...
```

Every public view gets `@extend_schema`. Tags group views in the API docs.

---

## URL Configuration

### App-Level

```python
from django.urls import path
from .views import CreateAppointmentView, ListAppointmentsView

urlpatterns = [
    path('/appointments', ListAppointmentsView.as_view(), name='list-appointments'),
    path('/appointments/create', CreateAppointmentView.as_view(), name='create-appointment'),
    path('/appointments/<slug:sqid>', RetrieveAppointmentView.as_view(), name='retrieve-appointment'),
]
```

### Project-Level

```python
urlpatterns = [
    path('api/auth',         include('core.urls')),
    path('api/appointments', include('hospital_ops.urls')),
    path('api/records',      include('records.urls')),
    path('api/payments',     include('payments.urls')),
]
```

### Naming Rules

- kebab-case for URL names: `create-appointment`, `verify-email`, `list-records`
- Paths start with `/` at the app level
- Names match intent: `create-appointment` not `appointment-create`

---

## Services & Business Logic

### `services.py` Pattern

Business logic lives here. Views call services; services handle the work and side effects.

```python
# <app>/services.py

def create_appointment(patient, doctor, date, mode, metadata=None):
    """
    Create an appointment and trigger all related side effects.
    All inputs are already validated — no defensive checks here.
    """
    appointment = Appointment.objects.create(
        patient=patient,
        doctor=doctor,
        date=date,
        mode=mode,
        metadata=metadata or {},
    )

    appointment.refresh_from_db()
    notify_doctor_of_new_appointment(doctor, appointment)  # Side effect

    return appointment


def cancel_appointment(appointment, cancelled_by):
    appointment.cancel()
    appointment.refresh_from_db()
    notify_cancellation(appointment, cancelled_by)
    return appointment


def recalculate_doctor_stats(doctor):
    """Recalculate and cache a doctor's aggregate stats."""
    data = Appointment.objects.filter(
        doctor=doctor, status=Appointment.Status.COMPLETED
    ).aggregate(
        total=Count("id"),
        avg_rating=Avg("rating")
    )

    doctor.profile.__class__.objects.filter(pk=doctor.profile.pk).update(
        total_appointments=data.get("total", 0),
        avg_rating=data.get("avg_rating"),
    )
```

### Key Principles

- Accept fully-qualified objects as parameters — not IDs that need re-fetching
- Always return the updated/created object
- Call `refresh_from_db()` after `create()` or `save()` when the caller needs fresh DB state
- Handle all side effects (notifications, cache, stats) — the view should never touch these
- Use queryset `.update()` for bulk writes instead of looping and calling `.save()`

---

## External HTTP Calls — `requests.py`

All outbound HTTP calls to a single external service live in `<app>/requests.py`. One file per integration. Functions either return data or raise an exception — never return `None` silently.

```python
# <app>/requests.py
import os
import requests

BASE_URL = "https://api.external-service.com/v1"
headers  = {
    "Authorization": f"Bearer {os.getenv('SERVICE_API_KEY')}",
    "Content-Type": "application/json"
}

def verify_identity(payload_id):
    """
    Call external identity verification.
    Returns the reference ID on success.
    Raises Exception on failure — callers must handle it.
    """
    try:
        response = requests.post(
            f"{BASE_URL}/verify",
            json={"id": payload_id},
            headers=headers,
            timeout=10,
        )
        data = response.json()

        if response.ok and data.get("status"):
            return data["data"]["reference"]

        raise Exception(data.get("message", "Verification failed"))

    except Exception as e:
        raise Exception("Unable to reach verification service") from e
```

### Principles

- One `requests.py` per external service — don't mix integrations
- Always set a `timeout` — never let an external call hang indefinitely
- Raise, don't return falsy — callers should `except Exception`, not check `if result:`
- Re-raise with a user-friendly message and preserve the original with `from e`
- Log with structured context at the call site, not inside the function

---

## Webhooks

### Split `webhooks.py` from `webhookshandlers.py`

The webhook view does exactly three things: verify signature, identify event type, delegate to handler. No business logic.

```python
# payments/webhooks.py

class PaymentWebhookView(APIView):
    authentication_classes = []
    permission_classes      = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload   = request.body
        signature = request.headers.get('x-service-signature')

        if not verify_signature(payload, signature):
            return Response({"detail": "Invalid signature"}, status=403)

        event      = json.loads(payload)
        event_type = event.get("event")
        data       = event.get("data", {})

        if event_type == "subscription.create":
            handle_subscription_create(data)
        elif event_type == "charge.success":
            handle_charge_success(data)
        elif event_type == "subscription.disable":
            handle_subscription_disable(data)

        return Response({"status": "ok"}, status=200)
```

```python
# payments/webhookshandlers.py
# One function per event type. Each is fully self-contained.

def handle_subscription_create(data):
    try:
        with transaction.atomic():
            user         = User.objects.get(external_code=data["customer"]["code"])
            subscription = Subscription.objects.get(user=user)

            subscription.status = Subscription.SubscriptionStatus.ACTIVE
            subscription.save(update_fields=['status'])

    except (User.DoesNotExist, Subscription.DoesNotExist):
        logger.error("handle_subscription_create: user/sub not found", extra={"data": data})
    except Exception as e:
        logger.error(f"handle_subscription_create failed: {e}", extra={"data": data})
```

### Webhook Handler Rules

- Each handler function handles exactly one event type
- Every handler wraps its work in `transaction.atomic()`
- Every handler has two `except` blocks: specific expected errors first, then a catchall `except Exception` as a safety net — webhooks must never crash the endpoint or the provider will retry indefinitely
- Side effects that should survive a transaction rollback (e.g. calling an external API to disable something) go **outside** the `atomic()` block
- Use `select_for_update()` when concurrent webhook delivery to the same row is possible

```python
def handle_charge_success(data):
    try:
        with transaction.atomic():
            subscription = Subscription.objects.select_for_update().get(user=user)
            subscription.status = Subscription.SubscriptionStatus.ACTIVE
            subscription.save(update_fields=['status'])
    except (User.DoesNotExist, Subscription.DoesNotExist):
        logger.error("handle_charge_success: not found", extra={"data": data})
    except Exception as e:
        logger.error(f"handle_charge_success failed: {e}", extra={"data": data})
```

---

## Error Handling & Responses

### Validation Errors — In Serializers

```python
if instance.status != Appointment.Status.ACTIVE:
    raise ValidationError("Appointment is not active.")

if patient == doctor.user:
    raise serializers.ValidationError("You cannot book an appointment with yourself.")
```

### Not Found — `get_object_or_404` or Selectors

```python
# In validate()
appointment = get_object_or_404(Appointment, sqid=attrs['appointment'])

# In selectors
def get_appointment(sqid):
    try:
        return Appointment.objects.get(sqid=sqid)
    except Appointment.DoesNotExist:
        raise NotFound("Appointment not found.")
```

### Consistent Response Shape

```python
# Success with data
Response(
    {
        "data":   AppointmentSerializer(appointment).data,
        "detail": "Appointment created successfully.",
        "status": "success"
    },
    status=status.HTTP_201_CREATED
)

# Success, no data
Response(
    {"detail": "Email verified successfully."},
    status=status.HTTP_200_OK
)

# Error
Response(
    {"detail": message, "status": "error"},
    status=status.HTTP_400_BAD_REQUEST
)

# External service failure
Response(
    {"error": "Failed to reach external service. Try again later."},
    status=status.HTTP_502_BAD_GATEWAY
)
```

Every response is explicit. No guessing the shape from the calling code.

---

## Permissions & Access Control

### Role-Based Permission Classes

```python
# project/permissions.py
class IsAuthenticatedDoctor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.Role.DOCTOR

class IsAuthenticatedPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.Role.PATIENT
```

### Composing Permissions

```python
permission_classes = [IsAuthenticatedDoctor | IsAuthenticatedAdmin]
```

### Object-Level Permissions

```python
class IsAppointmentOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user == obj.patient.user
```

---

## Plugin / Registry Pattern

For polymorphic behavior where logic varies by type — use a registry instead of if/else chains.

```python
# <app>/plugins.py
from decimal import Decimal

class BasePlugin:
    metrics_serializer = None

    def compute_score(self, metrics: dict) -> Decimal:
        if not metrics:
            return Decimal("0.00")
        values = [Decimal(str(v)) for v in metrics.values()]
        return (sum(values) / len(values)).quantize(Decimal("0.01"))


class TypeAPlugin(BasePlugin):
    metrics_serializer = TypeAMetricsSerializer


class TypeBPlugin(BasePlugin):
    metrics_serializer = TypeBMetricsSerializer


class ModelType:
    TYPE_A = "type_a"
    TYPE_B = "type_b"


PLUGIN_REGISTRY = {
    ModelType.TYPE_A: TypeAPlugin(),
    ModelType.TYPE_B: TypeBPlugin(),
}
```

```python
# Usage in serializer validate()
plugin = PLUGIN_REGISTRY.get(model_type)
metrics_serializer = plugin.metrics_serializer(data=metrics)
metrics_serializer.is_valid(raise_exception=True)
score = plugin.compute_score(metrics_serializer.validated_data)
```

---

## Background Tasks

```python
# <app>/tasks.py
from django_q.tasks import async_task, schedule, Schedule
from django.utils import timezone
from datetime import timedelta

def auto_complete_record(record_sqid):
    try:
        record = MedicalRecord.objects.get(sqid=record_sqid)
        record.update_status(MedicalRecord.Status.COMPLETED)
        async_task(
            "notifications.tasks.send_notification",
            user_ids=[record.patient.user.id],
            title="Record finalized",
            content="Your medical record has been finalized."
        )
    except MedicalRecord.DoesNotExist:
        logger.error(f"auto_complete_record: record {record_sqid} not found")
    except Exception as e:
        logger.error(f"auto_complete_record failed: {e}")


def schedule_record_completion(record):
    schedule(
        "<app>.tasks.auto_complete_record",
        record_sqid=record.sqid,
        schedule_type=Schedule.ONCE,
        next_run=timezone.now() + timedelta(hours=24),
        name=f"auto_complete_{record.sqid}"
    )
```

Background task handlers follow the same exception rules as webhook handlers — never let them crash silently.

---

## Querysets & ORM

### Always Optimize

```python
# select_related for FK / OneToOne (single JOIN query)
.select_related("patient", "doctor", "doctor__profile")

# prefetch_related for reverse FK / M2M (separate optimized query)
.prefetch_related("notes", "attachments", "tags")
```

Never return a queryset from `get_queryset()` without optimization. An unoptimized list view is an N+1 bug.

### Aggregation

```python
from django.db.models import Count, Avg, Max

stats = Appointment.objects.filter(doctor=doctor).aggregate(
    total=Count("id"),
    avg_rating=Avg("rating"),
)
```

### Bulk Updates — Never Loop + Save

```python
# ❌
for record in records:
    record.status = "archived"
    record.save()

# ✅
records.update(status="archived")

# ✅ Single record via queryset (avoids fetching the object)
Profile.objects.filter(pk=profile.pk).update(avg_rating=avg, total=count)
```

### Row-Level Locking

Use `select_for_update()` when concurrent writes to the same row are possible — webhooks, background tasks, or any scenario where the same record could be modified simultaneously.

```python
with transaction.atomic():
    subscription = Subscription.objects.select_for_update().get(user=user)
    subscription.status = Subscription.SubscriptionStatus.ACTIVE
    subscription.save(update_fields=['status'])
```

### Existence Checks

```python
already_exists = Appointment.objects.filter(
    patient=patient,
    doctor=doctor,
    status=Appointment.Status.PENDING
).exists()

if already_exists:
    raise ValidationError({"detail": "You already have a pending appointment with this doctor."})
```

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Models | PascalCase | `Appointment`, `PatientProfile` |
| Model suffixes | Descriptive | `*Profile`, `*Application`, `*Record` |
| Timestamp fields | `_at` suffix | `created_at`, `responded_at`, `deleted_at` |
| Boolean fields | `is_` prefix | `is_active`, `is_verified`, `is_deleted` |
| View classes | PascalCase + `View` | `CreateAppointmentView`, `ListRecordsView` |
| URL names | kebab-case, verb-first | `create-appointment`, `list-records` |
| Service functions | snake_case, verb-first | `create_appointment()`, `cancel_record()` |
| Selector functions | snake_case, verb-first | `get_appointment()`, `list_records_for_patient()` |
| Constants | UPPER_SNAKE_CASE | `PLUGIN_REGISTRY`, `MODELS`, `DEFAULT_TIMEOUT` |
| Cache keys | underscore-separated, domain-prefixed | `user_profile_<id>`, `pending_token_<sqid>` |
| Private/internal methods | `_` prefix | `_process_metrics()` |

---

## Import Style

```python
# 1. Standard library
from datetime import timedelta
from decimal import Decimal
import json
import os

# 2. Third-party — Django, DRF, then others alphabetically
from django.db import models, transaction
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

# 3. Local — project package first, then app-relative
from project.models import BaseModel
from project.permissions import IsAuthenticatedDoctor
from project.lib import MODELS
from core.models import User
from .models import Appointment
from .serializers import AppointmentSerializer, CreateAppointmentSerializer
from .services import create_appointment
```

Never:
- `from <app> import *`
- Circular imports — restructure to avoid them
- Late imports inside functions unless there's a documented performance reason

---

## What I Never Do

**No ViewSets or Routers**
❌ `ViewSet` + `DefaultRouter`
✅ Explicit `View` classes with `path()`

**No Fat Views**
❌ Business logic inside `perform_create` or `post()`
✅ Services handle logic; views call services and return responses

**No Field-Level Validation for Business Rules**
❌ `CharField(min_length=8)` for password rules; field validators for cross-field logic
✅ All custom validation in `serializer.validate()`

**No `fields = '__all__'`**
❌ Exposes new fields automatically — a liability
✅ Explicit `fields = [...]` or `exclude = [...]`

**No N+1 Queries**
❌ `Appointment.objects.filter(...)` without `select_related`
✅ Always optimize in `get_queryset()` or selectors

**No Magic Strings**
❌ `status == "active"` inline
✅ `status == Appointment.Status.ACTIVE`

**No Signals for Business Logic**
❌ Signals for notifications, stats recalculation, cache invalidation
✅ Explicit service calls; signals only for truly decoupled, cross-app events

**No Bare `except Exception` Outside of Webhooks/Tasks**
❌ `except Exception:` in views or services
✅ Catch specific exceptions; webhook and task handlers may use a safety-net `except Exception` with structured logging

**No Silent Failures in External Calls**
❌ Returning `None` or `False` when an external service call fails
✅ Raise an exception; let the caller decide how to handle it

**No Bare `self.save()` in State Transition Methods**
❌ `self.save()`
✅ `self.save(update_fields=['status', 'updated_at'])`

**No Comment Spam**
❌ `# Get the user` above `user = request.user`
✅ Comments only for non-obvious *why* — constraints, workarounds, deliberate decisions

---

## When to Break These Rules

Every rule has a context where it doesn't apply. Know the rule before you break it.

**ViewSets are acceptable when:**
- The project is small, stable, and unlikely to grow significantly
- All endpoints are truly standard CRUD with no customization needed

**Signals are the right tool when:**
- Two apps need to react to the same event but shouldn't import each other
- The side effect should fire regardless of *how* the model was modified (API, admin, management command, shell)
- Multiple independent subscribers respond to one event

**Field-level validators are fine when:**
- The rule is purely about the field's own format (URL validation, regex)
- The rule is reusable across many serializers and has no dependency on other fields

**`services.py` may not exist when:**
- The app is genuinely simple with no reusable business logic
- The view is a thin wrapper over a single model operation

**`except Exception` is acceptable when:**
- Inside webhook handlers — must not crash the endpoint
- Inside background task functions — must not crash the worker
- Always paired with structured logging; never swallowed silently

---

## Project-Specific Overrides

When dropping this guide into a new project, append a section like this:

```md
## [Project Name] Specifics

### BaseModel
- Location: `<project_package>/models.py`
- sqid config: min_length=X, custom alphabet: yes/no
- Additional shared fields beyond the base (e.g. `updated_at`)

### Auth Setup
- Authentication class in use
- Token type (JWT, session, custom)
- Refresh token strategy

### Key Apps & Responsibilities
- `core/` — ...
- `<app>/` — ...

### External Integrations
- Which services are integrated and which app owns each `requests.py`

### Deviations from Base Guide
- Any patterns in this project that intentionally differ, and why
```

