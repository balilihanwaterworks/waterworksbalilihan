# consumers/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .models import Consumer, Barangay


def proper_case(value):
    """
    Convert string to proper case (Title Case) with special handling.
    Examples: 'JOHN' -> 'John', 'mary jane' -> 'Mary Jane', 'de la cruz' -> 'De La Cruz'
    """
    if not value:
        return value
    # Title case each word
    return ' '.join(word.capitalize() for word in value.strip().split())


class ConsumerForm(forms.ModelForm):
    # Change meter_brand to CharField to allow manual text input
    meter_brand = forms.CharField(
        max_length=100,
        required=True,
        label="Meter Brand",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'style': 'text-transform: capitalize;', 
            'placeholder': 'Enter Meter Brand (e.g. Actaris)'
        })
    )

    # Date pickers for birth_date and registration_date
    birth_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    registration_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sort barangay dropdown alphabetically
        self.fields['barangay'].queryset = Barangay.objects.order_by('name')
        
        # Initialize meter_brand with name instead of ID for editing
        if self.instance and self.instance.pk and self.instance.meter_brand:
            self.initial['meter_brand'] = self.instance.meter_brand.name

    def clean_first_name(self):
        """Apply proper casing to first name."""
        value = self.cleaned_data.get('first_name', '')
        return proper_case(value)

    def clean_middle_name(self):
        """Apply proper casing to middle name."""
        value = self.cleaned_data.get('middle_name', '')
        return proper_case(value) if value else value

    def clean_last_name(self):
        """Apply proper casing to last name."""
        value = self.cleaned_data.get('last_name', '')
        return proper_case(value)

    def clean_spouse_name(self):
        """Apply proper casing to spouse name."""
        value = self.cleaned_data.get('spouse_name', '')
        return proper_case(value) if value else value

    def clean_meter_brand(self):
        """Convert the manual text input into a MeterBrand instance."""
        brand_name = self.cleaned_data.get('meter_brand')
        if brand_name:
            from .models import MeterBrand
            # Ensure proper casing
            brand_name_clean = proper_case(brand_name)
            # Create or get the MeterBrand
            brand_obj, _ = MeterBrand.objects.get_or_create(
                name__iexact=brand_name_clean,
                defaults={'name': brand_name_clean}
            )
            return brand_obj
        return None

    def clean(self):
        """
        Validate for duplicate consumers with same first name and last name.
        Allows different middle name or suffix to differentiate.
        """
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')

        if first_name and last_name:
            # Check for existing consumer with same first and last name
            existing = Consumer.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name
            )

            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                # Get the existing consumer(s) for the error message
                duplicates = list(existing[:3])  # Show up to 3 duplicates
                duplicate_info = ", ".join([
                    f"{c.full_name} (ID: {c.id_number or 'N/A'})"
                    for c in duplicates
                ])

                raise ValidationError(
                    f"A consumer with the name '{first_name} {last_name}' already exists: {duplicate_info}. "
                    "If this is a different person, please use a different middle name or suffix to distinguish them."
                )

        return cleaned_data

    class Meta:
        model = Consumer
        # ✅ EXPLICIT FIELD LIST with suffix added
        fields = [
            # Personal Information
            'first_name', 'middle_name', 'last_name', 'suffix', 'birth_date', 'gender', 'phone_number',
            # Household Information
            'civil_status', 'spouse_name', 'barangay', 'purok', 'household_number',
            # Water Meter Information
            'usage_type', 'meter_brand', 'serial_number', 'first_reading', 'registration_date',
        ]
        labels = {
            'first_reading': 'Previous Reading',
        }

        widgets = {
            # Personal Information
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'style': 'text-transform: capitalize;'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'style': 'text-transform: capitalize;'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'style': 'text-transform: capitalize;'}),
            'suffix': forms.Select(attrs={'class': 'form-select'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),

            # Household Information
            'civil_status': forms.Select(attrs={'class': 'form-select'}),
            'spouse_name': forms.TextInput(attrs={'class': 'form-control', 'style': 'text-transform: capitalize;'}),
            'barangay': forms.Select(attrs={'class': 'form-select'}),
            'purok': forms.Select(attrs={'class': 'form-select', 'id': 'id_purok'}),
            'household_number': forms.TextInput(attrs={'class': 'form-control'}),

            # Water Meter Information
            'usage_type': forms.Select(attrs={'class': 'form-select'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'first_reading': forms.NumberInput(attrs={'class': 'form-control'}),
        }