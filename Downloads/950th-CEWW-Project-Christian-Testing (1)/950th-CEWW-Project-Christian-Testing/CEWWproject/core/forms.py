from django import forms
from django.contrib.auth.models import User, Group
from .models import Asset, Maintenance, Incident

class MaintenanceForm(forms.ModelForm):
    class Meta:
        model = Maintenance
        fields = ['asset', 'maintenance_type', 'status', 'notes'] 
        widgets = {
            'asset': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'}),
            'maintenance_type': forms.TextInput(attrs={
                'placeholder': 'e.g., OS Reinstallation', 
                'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'
            }),
            'status': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'}),
            'notes': forms.Textarea(attrs={
                'placeholder': 'Detail the technical actions taken...', 
                'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50 h-32'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If we are pre-filling from an asset_id, make the dropdown look cleaner
        if 'initial' in kwargs and 'asset' in kwargs['initial']:
            self.fields['asset'].help_text = "Target asset selected."
        
class AssetForm(forms.ModelForm):
    # Keep your maintenance field
    type_of_maintenance = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'placeholder': 'Type of Maintenance (Optional)', 'class': 'w-full p-2 border rounded text-sm'})
    )

    class Meta:
        model = Asset
        # This MUST include maintenance_reason to save to the database
        fields = ['assets_name', 'assets_type', 'location', 'status', 'assigned_to', 'maintenance_reason']
        widgets = {
            'assets_name': forms.TextInput(attrs={'placeholder': 'Assets name', 'class': 'w-full p-2 border rounded text-sm'}),
            'assets_type': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'location': forms.TextInput(attrs={'placeholder': 'Location', 'class': 'w-full p-2 border rounded text-sm'}),
            'assigned_to': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'status': forms.RadioSelect(),
            'maintenance_reason': forms.TextInput(attrs={
                'placeholder': 'Type of Maintenance (Optional)', 
                'class': 'w-full p-2 border rounded text-sm'
            }),
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