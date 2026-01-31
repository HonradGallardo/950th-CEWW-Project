from django import forms
from django.contrib.auth.models import User, Group
from .models import Asset, Maintenance, Incident

class MaintenanceForm(forms.ModelForm):
    class Meta:
        model = Maintenance
        # Specify the fields you want to show in the form
        fields = ['asset', 'maintenance_type', 'status', 'notes'] 
        widgets = {
            'asset': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'maintenance_type': forms.TextInput(attrs={'placeholder': 'Type of maintenance', 'class': 'w-full p-2 border rounded text-sm'}),
            'status': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'notes': forms.Textarea(attrs={'placeholder': 'Description...', 'class': 'w-full p-2 border rounded text-sm h-24'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prevents changing the asset if we are editing an existing log
        if self.instance and self.instance.pk:
            self.fields['asset'].disabled = True
        
class AssetForm(forms.ModelForm):
    # Keep your maintenance field
    type_of_maintenance = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'placeholder': 'Type of Maintenance (Optional)', 'class': 'w-full p-2 border rounded text-sm'})
    )

    class Meta:
        model = Asset
        fields = ['assets_name', 'assets_type', 'location', 'status', 'assigned_to']
        widgets = {
            'assets_name': forms.TextInput(attrs={'placeholder': 'Assets name', 'class': 'w-full p-2 border rounded text-sm'}),
            'assets_type': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'location': forms.TextInput(attrs={'placeholder': 'Location', 'class': 'w-full p-2 border rounded text-sm'}),
            'date_added': forms.DateInput(attrs={'type': 'date', 'class': 'w-full p-2 border rounded text-sm'}),
            'assigned_to': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}), # Added widget for cleaner look
            'status': forms.RadioSelect(),
        }
        
class UserForm(forms.ModelForm):
    # Add a dropdown for Groups/Roles
    role = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        empty_label="Select Role",
        widget=forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 outline-none focus:ring-2 focus:ring-blue-500'})
    )
    
    password = forms.CharField(widget=forms.PasswordInput(), required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing an existing user, pre-select their current group
        if self.instance.pk and self.instance.groups.exists():
            self.fields['role'].initial = self.instance.groups.first()
        
        for field in self.fields.values():
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 outline-none focus:ring-2 focus:ring-blue-500'})