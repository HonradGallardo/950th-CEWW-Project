from django import forms
import bleach
from django.contrib.auth.models import User, Group
from .models import Asset, Maintenance, Incident

class MaintenanceForm(forms.ModelForm):
    class Meta:
        model = Maintenance
        fields = ['asset', 'maintenance_type', 'status', 'notes']
        widgets = {
            'asset': forms.Select(attrs={
                'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'
            }),
            'maintenance_type': forms.TextInput(attrs={
                'placeholder': 'e.g., OS Reinstallation',
                'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50 h-32'
            }),
        }
    def clean_asset(self):
        # If the field is disabled, 'cleaned_data' might be empty.
        # This ensures the asset stays the same.
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            return instance.asset
        return self.cleaned_data.get('asset')    

    def __init__(self, *args, **kwargs):
        edit_mode = kwargs.pop('edit_mode', False)
        super().__init__(*args, **kwargs)
        # 1. 🔍 FILTER: Only show assets waiting for maintenance (Queued or Maintenance)
        # Note: Replace 'Maintenance' with whatever your "Queued" status string is in Asset model
        if not edit_mode:
            self.fields['asset'].queryset = Asset.objects.filter(status='Maintenance')
            self.fields['asset'].label_from_instance = lambda obj: f"{obj.assets_id} - {obj.assets_name}"

        # 2. 🔒 EDIT MODE: lock the Asset choice, but leave notes/status open for the tech
        if edit_mode:
            self.fields['asset'].disabled = True
            self.fields['status'].disabled = True
            self.fields['notes'].disabled = True

        
class AssetForm(forms.ModelForm):

    def clean_ip_address(self):
        ip = self.cleaned_data.get('ip_address')
        if ip:
            # Strip accidental whitespace
            return ip.strip()
        return ip
    class Meta:
        model = Asset
        # Added 'brand', 'serial_number', and other missing fields requested by your template
        fields = [
            'assets_name', 'assets_type', 'brand', 'serial_number', 'location', 'status', 
            'assigned_to', 'maintenance_reason', 'processor', 
            'ram_gb', 'storage_capacity', 'ip_address', 
            'mac_address', 'firmware_version', 'os_version', 'battery_health',
            'total_ports', 'is_redundant_power', 'faulty_hardware_part', 'software_issue_type'
        ]
        
        widgets = {
            'assets_name': forms.TextInput(attrs={'placeholder': 'Asset Name', 'class': 'w-full p-2 border rounded text-sm'}),
            'assets_type': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'brand': forms.TextInput(attrs={'placeholder': 'Brand / Manufacturer', 'class': 'w-full p-2 border rounded text-sm'}),
            'serial_number': forms.TextInput(attrs={'placeholder': 'Serial Number (S/N)', 'class': 'w-full p-2 border rounded text-sm'}),
            'location': forms.TextInput(attrs={'placeholder': 'Location', 'class': 'w-full p-2 border rounded text-sm'}),
            'assigned_to': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'status': forms.RadioSelect(),
            'maintenance_reason': forms.TextInput(attrs={'placeholder': 'Maintenance Reason', 'class': 'w-full p-2 border rounded text-sm'}),
            
            # Technical Specification Widgets
            'processor': forms.TextInput(attrs={'placeholder': 'Processor (e.g. Intel i7)', 'class': 'w-full p-2 border rounded text-sm'}),
            'ram_gb': forms.NumberInput(attrs={'placeholder': 'RAM in GB', 'class': 'w-full p-2 border rounded text-sm'}),
            'storage_capacity': forms.TextInput(attrs={'placeholder': 'Storage (e.g. 512GB SSD)', 'class': 'w-full p-2 border rounded text-sm'}),
            'ip_address': forms.TextInput(attrs={'placeholder': 'IP Address', 'class': 'w-full p-2 border rounded text-sm'}),
            'mac_address': forms.TextInput(attrs={'placeholder': 'MAC Address', 'class': 'w-full p-2 border rounded text-sm'}),
            'firmware_version': forms.TextInput(attrs={'placeholder': 'Firmware Version', 'class': 'w-full p-2 border rounded text-sm'}),
            'os_version': forms.TextInput(attrs={'placeholder': 'OS Version', 'class': 'w-full p-2 border rounded text-sm'}),
            'battery_health': forms.NumberInput(attrs={'placeholder': 'Battery Health %', 'class': 'w-full p-2 border rounded text-sm'}),
            'total_ports': forms.NumberInput(attrs={'placeholder': 'Total Ports', 'class': 'w-full p-2 border rounded text-sm'}),
            'is_redundant_power': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'}),
            'faulty_hardware_part': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'software_issue_type': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
        }
        
        
class UserForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    
    role = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False, 
        empty_label="Select Role",
        widget=forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 outline-none focus:ring-2 focus:ring-blue-500'})
    )
    
    password = forms.CharField(widget=forms.PasswordInput(), required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']

    # 🚨 SECURITY: Strict Backend Input Sanitization
    # This strips all HTML tags (like <script> or <img>) before saving to the DB
    def clean_first_name(self):
        data = self.cleaned_data.get('first_name', '')
        return bleach.clean(data, tags=[], strip=True)

    def clean_last_name(self):
        data = self.cleaned_data.get('last_name', '')
        return bleach.clean(data, tags=[], strip=True)

    def clean_username(self):
        data = self.cleaned_data.get('username', '')
        # Additionally strip any weird whitespace that could cause SQLi anomalies
        return bleach.clean(data, tags=[], strip=True).strip()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if not self.instance.pk:
            self.fields['password'].required = True
            
        if self.instance.pk and self.instance.groups.exists():
            self.fields['role'].initial = self.instance.groups.first()
        
        for field in self.fields.values():
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 outline-none focus:ring-2 focus:ring-blue-500'})