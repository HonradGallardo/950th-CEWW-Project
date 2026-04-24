from django import forms
from django.contrib.auth.models import User, Group
from .models import Asset, Maintenance, Incident

from django import forms
from .models import Maintenance, Asset

class MaintenanceForm(forms.ModelForm):
    class Meta:
        model = Maintenance
        # ADDED 'attachment' to the end of the list
        fields = [
            'asset', 'maintenance_type', 'status', 'notes', 
            'maintenance_date', 'faulty_hardware_part', 'software_issue_type',
            'attachment' , 'issue_description', 'solution_description', 'solved_description'
        ]
        widgets = {
            'asset': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'}),
            'maintenance_type': forms.TextInput(attrs={'placeholder': 'e.g., OS Reinstallation', 'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'}),
            'status': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'}),
            'notes': forms.Textarea(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50 h-32'}),
            
            # --- DIAGNOSTIC WIDGETS ---
            'maintenance_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50'}),
            'faulty_hardware_part': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50 appearance-none'}),
            'software_issue_type': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50 appearance-none'}),
            'issue_description': forms.Textarea(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50 h-32'}),
            'solution_description': forms.Textarea(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50 h-32'}),
            'solved_description': forms.Textarea(attrs={'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50 h-32'}),

            # --- NEW: ATTACHMENT WIDGET ---
            'attachment': forms.ClearableFileInput(attrs={
                'class': 'w-full p-2 border rounded-lg text-sm bg-slate-50 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-black file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'
            }),
        }
        
    def clean_asset(self):
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            return instance.asset
        return self.cleaned_data.get('asset')    

    def __init__(self, *args, **kwargs):
        edit_mode = kwargs.pop('edit_mode', False)
        super().__init__(*args, **kwargs)
        
        if not edit_mode:
            self.fields['asset'].queryset = Asset.objects.filter(status='Maintenance')
            self.fields['asset'].label_from_instance = lambda obj: f"{obj.assets_id} - {obj.assets_name}"

        if edit_mode:
            self.fields['asset'].disabled = True
            self.fields['status'].disabled = True
            self.fields['notes'].disabled = True

        
from django import forms
from .models import Asset

class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        # Updated to include all the new detailed fields
        fields = [
            'assets_name', 'assets_type', 'brand', 'model_number', 'serial_number',
            'location', 'assigned_to', 'status', 'processor', 'ram_gb', 
            'storage_capacity', 'os_version', 'ip_address', 'mac_address', 
            'firmware_version', 'total_ports', 'is_redundant_power', 'rack_unit', 
            'battery_health', 'maintenance_reason', 'faulty_hardware_part', 
            'software_issue_type'
        ]
        
        widgets = {
            # --- Base Identification ---
            'assets_name': forms.TextInput(attrs={'placeholder': 'e.g. Workstation-Alpha', 'class': 'w-full p-2 border rounded text-sm'}),
            'assets_type': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'brand': forms.TextInput(attrs={'placeholder': 'e.g. Dell, Cisco, HP', 'class': 'w-full p-2 border rounded text-sm'}),
            'model_number': forms.TextInput(attrs={'placeholder': 'Model Number', 'class': 'w-full p-2 border rounded text-sm'}),
            'serial_number': forms.TextInput(attrs={'placeholder': 'S/N Tag', 'class': 'w-full p-2 border rounded text-sm'}),
            
            # --- Assignment & Status ---
            'location': forms.TextInput(attrs={'placeholder': 'Room / Rack Slot', 'class': 'w-full p-2 border rounded text-sm'}),
            'assigned_to': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'status': forms.RadioSelect(attrs={'class': 'flex gap-4'}),
            
            # --- Computing Specs ---
            'processor': forms.TextInput(attrs={'placeholder': 'Processor (e.g. Dual Xeon)', 'class': 'w-full p-2 border rounded text-sm'}),
            'ram_gb': forms.NumberInput(attrs={'placeholder': 'RAM (GB)', 'class': 'w-full p-2 border rounded text-sm'}),
            'storage_capacity': forms.TextInput(attrs={'placeholder': 'Storage (e.g. 1TB NVMe)', 'class': 'w-full p-2 border rounded text-sm'}),
            'os_version': forms.TextInput(attrs={'placeholder': 'OS Version (e.g. RHEL 9)', 'class': 'w-full p-2 border rounded text-sm'}),
            
            # --- Networking Specs ---
            'ip_address': forms.TextInput(attrs={'placeholder': 'Static IP Address', 'class': 'w-full p-2 border rounded text-sm'}),
            'mac_address': forms.TextInput(attrs={'placeholder': 'Physical Address', 'class': 'w-full p-2 border rounded text-sm'}),
            'firmware_version': forms.TextInput(attrs={'placeholder': 'Firmware (e.g. IOS v15)', 'class': 'w-full p-2 border rounded text-sm'}),
            'total_ports': forms.NumberInput(attrs={'placeholder': 'Total Ports', 'class': 'w-full p-2 border rounded text-sm'}),
            'is_redundant_power': forms.CheckboxInput(attrs={'class': 'form-checkbox h-4 w-4 text-blue-600'}),
            
            # --- Physical/Environmental ---
            'rack_unit': forms.NumberInput(attrs={'placeholder': 'U Height', 'class': 'w-full p-2 border rounded text-sm'}),
            'battery_health': forms.NumberInput(attrs={'placeholder': 'Battery Health %', 'class': 'w-full p-2 border rounded text-sm'}),
            
            # --- Maintenance Logging ---
            'maintenance_reason': forms.Textarea(attrs={'placeholder': 'Summarize the technical issue...', 'class': 'w-full p-2 border rounded text-sm', 'rows': 3}),
            'faulty_hardware_part': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
            'software_issue_type': forms.Select(attrs={'class': 'w-full p-2 border rounded text-sm'}),
        }
        
class UserForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    
    # 🚨 FIX: We remove `required=True` here so the backend logic from views.py controls the group
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 🚨 FIX: If we are creating a NEW user, make password required
        if not self.instance.pk:
            self.fields['password'].required = True
            
        # If editing an existing user, pre-select their current group
        if self.instance.pk and self.instance.groups.exists():
            self.fields['role'].initial = self.instance.groups.first()
        
        for field in self.fields.values():
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 outline-none focus:ring-2 focus:ring-blue-500'})