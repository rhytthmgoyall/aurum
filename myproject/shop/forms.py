from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import RefundRequest


RETURN_WINDOW_DAYS = 7


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(file, initial) for file in data]
        return [single_file_clean(data, initial)] if data else []


class RefundRequestForm(forms.ModelForm):
    images = MultipleFileField(
        required=False,
        label="Proof images",
    )

    class Meta:
        model = RefundRequest
        fields = ("reason", "reason_detail", "refund_mode")
        widgets = {
            "reason_detail": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order
        self.fields["reason"].choices = RefundRequest.REASON_CHOICES
        self.fields["reason_detail"].label = "Reason detail (Optional)"

    def clean(self):
        cleaned_data = super().clean()

        if self.order:
            return_anchor = getattr(self.order, "delivered_at", None) or self.order.created_at
            if return_anchor + timedelta(days=RETURN_WINDOW_DAYS) < timezone.now():
                raise forms.ValidationError(
                    f"This order is outside the {RETURN_WINDOW_DAYS}-day return window."
                )

        reason = cleaned_data.get("reason")
        images = cleaned_data.get("images") or []

        if reason in ["defective", "wrong_item"] and not images:
            self.add_error("images", "Proof image is required for defective or wrong item refund requests.")    

        return cleaned_data
