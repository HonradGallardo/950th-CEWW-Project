from django.http import JsonResponse
from rest_framework import viewsets
from webauthn import generate_authentication_options, generate_registration_options, verify_registration_response
from ..models import Asset, IncidentComment, Maintenance, Incident, Notification
from .serializers import AssetSerializer, ChangePasswordSerializer, IncidentCommentSerializer, MaintenanceSerializer, IncidentSerializer, NotificationSerializer, UserSerializer
from rest_framework.decorators import action
from django.contrib.auth.models import User
from rest_framework.response import Response
from rest_framework.views import APIView, settings
from django.conf import settings
from django.db.models import Q, Count
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from django.contrib.auth import login, update_session_auth_hash
from rest_framework.permissions import IsAuthenticated, AllowAny
import random
from django.core.mail import send_mail
from django.contrib.auth.views import LoginView
import requests
import json, base64
from django.http import HttpResponse
from webauthn import generate_authentication_options, verify_authentication_response
from rest_framework.authentication import SessionAuthentication
from webauthn.helpers.options_to_json import options_to_json
from core.models import UserPasskey
from rest_framework.exceptions import PermissionDenied
from webauthn.helpers.structs import PublicKeyCredentialDescriptor
from webauthn.helpers.base64url_to_bytes import base64url_to_bytes
from core.api.serializers import (
    UserSerializer, 
    AssetSerializer, 
    MaintenanceSerializer, 
    IncidentSerializer,
    IncidentCommentSerializer,
    NotificationSerializer,
)

# Ensure these match your local environment
if settings.DEBUG:
    RP_ID = "localhost"
    ORIGIN = "http://localhost:8000"
else:
    RP_ID = "nine50ceww-aims.onrender.com"
    ORIGIN = "https://nine50ceww-aims.onrender.com"

# ==========================================
# PASSKEY REGISTRATION (For Profile Page)
# ==========================================
class PasskeyRegisterOptionsAPI(APIView):
    permission_classes = [IsAuthenticated] 

    def post(self, request):
        user = request.user
        
        options = generate_registration_options(
            rp_id=RP_ID,
            rp_name="950th CEWW System",
            user_id=str(user.id).encode('utf-8'),
            user_name=user.username,
        )

        challenge_b64 = base64.b64encode(options.challenge).decode('utf-8')
        request.session['webauthn_register_challenge'] = challenge_b64

        return HttpResponse(options_to_json(options), content_type='application/json')

class PasskeyRegisterVerifyAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            challenge_b64 = request.session.get('webauthn_register_challenge')
            if not challenge_b64:
                 return Response({"error": "Registration session expired. Please try again."}, status=400)
                 
            challenge_bytes = base64.b64decode(challenge_b64)
            
            credential_data = request.data 
            
            verification = verify_registration_response(
                credential=credential_data,
                expected_challenge=challenge_bytes, 
                expected_rp_id=RP_ID,
                expected_origin=ORIGIN,
            )
            
            credential_id_str = base64.b64encode(verification.credential_id).decode('utf-8')
            public_key_str = base64.b64encode(verification.credential_public_key).decode('utf-8')

            from core.models import UserPasskey
            UserPasskey.objects.create(
                user=request.user,
                name="My Authenticator",
                credential_id=credential_id_str,
                public_key=public_key_str,
                sign_count=verification.sign_count
            )
            
            return Response({"status": "success"})
        except Exception as e:
            return Response({"error": str(e)}, status=400)

# ==========================================
# PASSKEY LOGIN (For Login Page)
# ==========================================
class PasskeyLoginOptionsAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            username = request.data.get('username') 
            from django.contrib.auth.models import User
            user = User.objects.filter(username=username).first()

            if not user:
                return Response({"error": "User not found."}, status=400)

            user_passkeys = user.passkeys.all()
            if not user_passkeys:
                return Response({"error": "No passkeys registered for this account."}, status=400)

            allow_credentials = [
                PublicKeyCredentialDescriptor(
                    id=base64.b64decode(pk.credential_id)
                ) for pk in user_passkeys
            ]

            options = generate_authentication_options(
                rp_id=RP_ID,
                allow_credentials=allow_credentials,
            )

            challenge_b64 = base64.b64encode(options.challenge).decode('utf-8')
            request.session['webauthn_login_challenge'] = challenge_b64
            request.session['webauthn_user_id'] = user.id

            return HttpResponse(options_to_json(options), content_type='application/json')
            
        except Exception as e:
            return Response({"error": str(e)}, status=400)

class PasskeyLoginVerifyAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            credential_data = request.data 
            
            challenge_b64 = request.session.get('webauthn_login_challenge')
            user_id = request.session.get('webauthn_user_id')

            if not challenge_b64 or not user_id:
                return Response({"error": "Session expired. Try again."}, status=400)

            challenge_bytes = base64.b64decode(challenge_b64)

            from django.contrib.auth.models import User
            user = User.objects.filter(id=user_id).first()
            
            frontend_cred_id_bytes = base64url_to_bytes(credential_data.get('id'))
            
            passkey = None
            for pk in user.passkeys.all():
                db_cred_bytes = base64.b64decode(pk.credential_id)
                if db_cred_bytes == frontend_cred_id_bytes:
                    passkey = pk
                    break
                    
            if not passkey:
                 return Response({"error": "Unrecognized passkey."}, status=400)

            verification = verify_authentication_response(
                credential=credential_data,
                expected_challenge=challenge_bytes,
                expected_rp_id=RP_ID,
                expected_origin=ORIGIN,
                credential_public_key=base64.b64decode(passkey.public_key),
                credential_current_sign_count=passkey.sign_count,
            )

            passkey.sign_count = verification.new_sign_count
            passkey.save()

            del request.session['webauthn_login_challenge']
            del request.session['webauthn_user_id']
            
            from django.contrib.auth import login
            login(request, user)
            return Response({"status": "success", "redirect_url": "/role-redirect/"})

        except Exception as e:
            return Response({"error": "Biometric verification failed: " + str(e)}, status=400)
        
        
        
class APILoginView(LoginView):
    template_name = 'registration/login.html'

    def form_valid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            user = form.get_user()
            
            # --- MFA LOGIC CHECK ---
            mfa_enabled = False 

            if mfa_enabled:
                
                if not user.email or user.email.strip() == "":
                    return JsonResponse({
                        'status': 'error',
                        'message': 'MFA is required, but no email is registered to this account. Please contact your system administrator.'
                    }, status=400)
                # 1. Generate a 6-digit OTP
                generated_otp = str(random.randint(100000, 999999))
                
                # 2. Store pre-auth info in the session securely
                self.request.session['mfa_user_id'] = user.id
                self.request.session['mfa_expected_otp'] = generated_otp

                # 3. Send the OTP via Email
                subject = 'SYSTEM ALERT: Login Verification - 950th CEWW'
                message = f"Attention {user.username},\n\nYour secure login verification code is: {generated_otp}\n\nDo not share this code."
                try:
                    send_mail(
                        subject, message,
                        getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@950ceww.local'),
                        [user.email], fail_silently=True,
                    )
                except Exception as e:
                    print(f"Failed to send MFA email: {e}")

                # 4. Tell the frontend to show the MFA form!
                return JsonResponse({
                    'status': 'success',
                    'mfa_required': True 
                })
            else:
                # Standard Login (No MFA)
                login(self.request, user)
                return JsonResponse({
                    'status': 'success',
                    'redirect_url': '/role-redirect/',
                    'mfa_required': False 
                })
                
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid credentials.'}, status=400)
        return super().form_invalid(form)


class VerifyMFAAPI(APIView):
    """Endpoint to verify the OTP entered during login."""
    permission_classes = [AllowAny]

    def post(self, request):
        otp_code = request.data.get('otp_code')
        user_id = request.session.get('mfa_user_id')
        expected_otp = request.session.get('mfa_expected_otp')

        # 1. Check if the session expired
        if not user_id or not expected_otp:
            return Response({"message": "Session expired. Please log in again."}, status=400)

        # 2. Verify the Code
        if str(otp_code) == str(expected_otp):
            user = User.objects.filter(id=user_id).first()
            if user:
                # Success! Log them in officially.
                login(request, user)
                
                # Clean up session data
                del request.session['mfa_user_id']
                del request.session['mfa_expected_otp']
                
                return Response({"status": "success", "redirect_url": "/role-redirect/"})
            else:
                return Response({"message": "User account error."}, status=400)

        return Response({"message": "Invalid verification code."}, status=400)

class DashboardStatsAPI(APIView):
    """Provides live data for dashboard counters, charts, and tables."""
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # 1. Base Summary Metrics
            total_assets = Asset.objects.count()
            assigned_assets = Asset.objects.exclude(status='Inactive').count()
            maintenance_count = Maintenance.objects.filter(status='In Progress').count()
            open_incidents_count = Incident.objects.filter(status='Open').count()

            # 2. Asset Distribution (Bar Chart)
            asset_qs = Asset.objects.values('assets_type').annotate(total=Count('id'))
            asset_labels = [item['assets_type'] for item in asset_qs]
            asset_totals = [item['total'] for item in asset_qs]

            # 3. Incident Severity (Doughnut Chart)
            severity_qs = Incident.objects.values('severity').annotate(total=Count('id'))
            severity_labels = [item['severity'] for item in severity_qs]
            severity_totals = [item['total'] for item in severity_qs]

            # 4. Table Data: Recent Maintenance
            recent_maint = Maintenance.objects.all().select_related('asset', 'technician').order_by('-date')[:5]
            maint_list = [{
                'id': m.id,
                # Safe Check: Prevents crash if the DB relationship is missing
                'asset_name': m.asset.assets_name if m.asset else 'Unknown Asset',
                'technician_name': m.technician.username if m.technician else 'System',
                'status': m.status
            } for m in recent_maint]

            # 5. Table Data: Open Incidents
            open_inc_qs = Incident.objects.filter(status='Open').order_by('-date')[:5]
            inc_list = [{
                'id': i.id,
                'title': i.title,
                'severity': i.severity,
            } for i in open_inc_qs]

            # 6. Incident Trend Data (Last 7 Days)
            today = timezone.now().date()
            date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
            trend_labels = [d.strftime('%a') for d in date_list]  
            date_to_idx = {d: i for i, d in enumerate(date_list)}

            trend_values = [0] * 7
            inc_trend_qs = Incident.objects.filter(date__date__gte=date_list[0]) \
                .values('date__date').annotate(count=Count('id'))
            for item in inc_trend_qs:
                idx = date_to_idx.get(item['date__date'])
                if idx is not None:
                    trend_values[idx] = item['count']

            # 7. Maintenance Metrics Data
            m_completed = [0] * 7
            m_pending = [0] * 7
            maint_trend_qs = Maintenance.objects.filter(date__date__gte=date_list[0]) \
                .values('date__date', 'status').annotate(count=Count('id'))
            for item in maint_trend_qs:
                idx = date_to_idx.get(item['date__date'])
                if idx is not None:
                    if item['status'] == 'Completed':
                        m_completed[idx] = item['count']
                    else:
                        m_pending[idx] = item['count']

            return Response({
                'total_assets': total_assets,
                'assigned_assets': assigned_assets,
                'maintenance_count': maintenance_count,
                'open_incidents': open_incidents_count,
                'asset_labels': asset_labels,
                'asset_totals': asset_totals,
                'severity_labels': severity_labels,
                'severity_totals': severity_totals,
                'recent_maintenance': maint_list,
                'open_incidents_list': inc_list,
                'trend_labels': trend_labels,
                'trend_values': trend_values,
                'm_labels': trend_labels, 
                'm_completed': m_completed,
                'm_pending': m_pending,
            })
            
        except Exception as e:
            import traceback
            print("DASHBOARD API CRASHED:", traceback.format_exc())
            return Response({"error": str(e)}, status=500)

class PersonnelStatsAPI(APIView):
    """Provides live data specifically for the Personnel Dashboard."""
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        total_assets = Asset.objects.count()
        
        # Format recent maintenance tasks (ADDED: asset_name and maintenance_type)
        recent_maint = Maintenance.objects.select_related('asset', 'technician').order_by('-date')[:20]
        maint_list = [{
            'id': m.id,
            'technician_name': m.technician.username if m.technician else 'System',
            'status': m.status,
            'asset_name': m.asset.assets_name if m.asset else 'Unknown Asset',
            'maintenance_type': m.maintenance_type
        } for m in recent_maint]

        # Format assigned assets (NEW: For the bottom left table)
        assigned = Asset.objects.filter(assigned_to=request.user).order_by('-date_added')[:20]
        asset_list = [{
            'id': a.id,
            'assets_name': a.assets_name,
            'status': a.status,
            'date_added': a.date_added.strftime('%d-%m-%Y')
        } for a in assigned]

        # Format recent incidents
        recent_inc = Incident.objects.all().order_by('-date')[:20]
        inc_list = [{
            'id': i.id,
            'title': i.title,
            'severity': i.severity,
            'status': i.status,
            'formatted_date': i.date.strftime('%b %d, %Y'),
            'date_label': i.date.strftime('%a')
        } for i in recent_inc]

        return Response({
            'total_assets_count': total_assets,
            'user_info': {'username': request.user.username},
            'recent_maintenance': maint_list,
            'recent_incidents': inc_list,
            'assigned_assets': asset_list  # Added to the payload
        })
        
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().prefetch_related('groups', 'profile').order_by('username')
    serializer_class = UserSerializer

    @action(detail=False, methods=['get'], url_path='live_search')
    def live_search(self, request):
            query = request.GET.get('q', '').strip()
            role = request.GET.get('role', 'ALL').upper()
            
            users = self.get_queryset()
            
            if query:
                users = users.filter(
                    Q(username__icontains=query) |
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query)
                ).distinct()

            if role != 'ALL':
                users = users.filter(groups__name__iexact=role) if role != 'UNASSIGNED' else users.filter(groups__isnull=True)
            
            data = []
            for u in users[:20]:
                has_profile = hasattr(u, 'profile')
                img_url = None
                
                # Safe image retrieval
                if has_profile and u.profile.image:
                    try:
                        img_url = u.profile.image.url
                    except ValueError:
                        img_url = None
                
                data.append({
                    'id': u.id,
                    'username': u.username,
                    'full_name': u.get_full_name() or u.username,
                    'email': u.email,
                    'role': u.groups.all()[0].name if u.groups.exists() else 'Unassigned',
                    'last_login': u.last_login.strftime('%d-%m-%y') if u.last_login else 'Never',
                    'date_joined': u.date_joined.strftime('%b %Y'),
                    'rank': u.profile.rank if has_profile else 'Airman',
                    'image_url': img_url
                })
            
            return Response(data)
    
class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer

    def perform_create(self, serializer):
        asset = serializer.save(assigned_to=self.request.user)
        self.handle_maintenance_logic(asset)
    
    # 🚨 UPDATED FILTER LOGIC: Matches Type OR Status
    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        if category and category != 'All':
            queryset = queryset.filter(
                Q(assets_type__iexact=category) | Q(status__iexact=category)
            )
        return queryset

    def perform_update(self, serializer):
        asset = serializer.save()
        self.handle_maintenance_logic(asset)

    def handle_maintenance_logic(self, asset):
        if asset.status == 'Maintenance':
            maint_type = self.request.data.get('maintenance_reason', 'Auto-Generated Repair')

            # ✅ Always update asset field
            asset.maintenance_reason = maint_type
            asset.save(update_fields=['maintenance_reason'])

            exists = Maintenance.objects.filter(asset=asset).exclude(status='Completed').exists()

            if not exists:
                Maintenance.objects.create(
                    asset=asset,
                    technician=self.request.user,
                    maintenance_type=maint_type,
                    status='In Progress',
                    notes=f"System auto-generated log: {asset.assets_name} was marked as 'Maintenance'."
                )
                
class MaintenanceViewSet(viewsets.ModelViewSet):
    queryset = Maintenance.objects.all().select_related('asset', 'technician').order_by('-date')
    serializer_class = MaintenanceSerializer

    # 🚨 ADDED FILTER LOGIC: Matches Type OR Status
    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        if category and category != 'All':
            queryset = queryset.filter(
                Q(maintenance_type__iexact=category) | Q(status__iexact=category)
            )
        return queryset

    def perform_create(self, serializer):
        # Automatically set the technician to the currently logged-in user
        serializer.save(technician=self.request.user)

    def perform_update(self, serializer):
        # 1. Save the updated maintenance log first
        instance = serializer.save()
        
        # 2. SMART LOGIC: If maintenance is completed, automatically activate the asset
        if instance.status == 'Completed':
            asset = instance.asset
            if asset.status != 'Active':
                asset.status = 'Active'
                asset.save()

    def perform_destroy(self, instance):
        # Clean up the destroy method to avoid save errors on deleted objects
        asset = instance.asset
        asset.status = 'Active'
        asset.save()
        instance.delete()


class IncidentViewSet(viewsets.ModelViewSet):
    queryset = Incident.objects.all().order_by('-date')
    serializer_class = IncidentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        if category and category != 'All':
            queryset = queryset.filter(
                Q(severity__iexact=category) | Q(status__iexact=category)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)

    # 🚨 BULLETPROOF UPDATE: Fixes Serializer Validation & Forces DB Write
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        user = request.user

        # 1. Capture exact DB state BEFORE validation
        current_owner = instance.assigned_to
        current_owner_id = str(current_owner.id) if current_owner else ""
        
        data = request.data.copy()
        
        # 2. Extract proposed new owner safely
        raw_assigned = data.get('assigned_to', current_owner_id)
        new_owner_id = str(raw_assigned) if raw_assigned not in ['', 'null', 'None', None] else ""

        # 3. Security Checks (Includes Superuser bypass syncing)
        is_owner = (current_owner_id == str(user.id))
        is_unassigned = (current_owner_id == "")
        is_superuser = user.is_superuser
        
        if is_unassigned:
            if new_owner_id != str(user.id) and not is_superuser:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Access Denied: You must take over this incident to your account first.")
        else:
            if not is_owner and not is_superuser:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Access Denied: Only the current technician can modify this incident.")

        # 4. 🔥 FIX THE DRF CRASH: Properly format empty assignments as Python None
        if 'assigned_to' in data and data['assigned_to'] in ['', 'null', 'None']:
            data['assigned_to'] = None

        # 5. Standard DRF Validation & Save
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()

        # 6. 🔥 DIRECT SQL OVERRIDE: Physically force the previous tech into the database
        if current_owner_id != new_owner_id:
            if current_owner:
                # This bypasses all serializers and writes directly to the hard drive
                Incident.objects.filter(id=updated_instance.id).update(
                    last_technician=current_owner.username
                )

        # Clear cache to ensure frontend gets fresh data
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    # 🚨 STRICT DELETION SECURITY
    def perform_destroy(self, instance):
        current_owner = instance.assigned_to
        if current_owner and current_owner.id == self.request.user.id:
            instance.delete()
        elif self.request.user.is_superuser:
            instance.delete()
        else:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Access Denied: Only the current technician can delete this incident.")
        
class IncidentCommentViewSet(viewsets.ModelViewSet):
    serializer_class = IncidentCommentSerializer

    def get_queryset(self):
        queryset = IncidentComment.objects.all().order_by('created_at')
        incident_id = self.request.query_params.get('incident')
        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class MonitoringDataAPI(APIView):
    def get(self, request):
        today = timezone.now().date()
        date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
        labels = [d.strftime('%a') for d in date_list]
        date_to_idx = {d: i for i, d in enumerate(date_list)}

        fixed_assets, pending_assets = [0]*7, [0]*7
        new_incidents, resolved_incidents = [0]*7, [0]*7

        # 1. Maintenance Trends
        maint_qs = Maintenance.objects.filter(date__date__gte=date_list[0]) \
            .values('date__date', 'status').annotate(count=Count('id'))
        for item in maint_qs:
            idx = date_to_idx.get(item['date__date'])
            if idx is not None:
                if item['status'] == 'Completed': fixed_assets[idx] = item['count']
                else: pending_assets[idx] = item['count']

        # 2. Incident Trends
        inc_qs = Incident.objects.filter(date__date__gte=date_list[0]) \
            .values('date__date', 'status').annotate(count=Count('id'))
        for item in inc_qs:
            idx = date_to_idx.get(item['date__date'])
            if idx is not None:
                if item['status'] == 'Resolved': resolved_incidents[idx] = item['count']
                else: new_incidents[idx] = item['count']

        # 3. Basic AI Prediction (Linear Growth)
        # We check if incidents today are higher than the 7-day average
        avg_incidents = sum(new_incidents) / 7
        predicted = int(avg_incidents * 30) + 2 # Projection for next 30 days
        is_rising = new_incidents[-1] > avg_incidents

        return Response({
            'labels': labels,
            'fixed_assets': fixed_assets,
            'pending_assets': pending_assets,
            'new_incidents': new_incidents,
            'resolved_incidents': resolved_incidents,
            'predicted_incidents': max(predicted, 1),
            'confidence_level': 'High' if sum(new_incidents) > 5 else 'Medium',
            'is_rising': is_rising,
            'asset_types': list(Asset.objects.values('assets_type').annotate(total=Count('id')))
        })
        
class NotificationViewSet(viewsets.ModelViewSet):
    """API for dynamic notification bell updates."""
    serializer_class = NotificationSerializer 
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Notification.objects.none()
            
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')
    
class ChangePasswordAPI(APIView):
    """Endpoint for users to securely update their passwords."""
    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            user = request.user
            # Verify the old password
            if not user.check_password(serializer.data.get("old_password")):
                return Response(
                    {"errors": {"old_password": ["Incorrect current password."]}}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save the new password
            user.set_password(serializer.data.get("new_password"))
            user.save()
            
            # Keep the user logged in
            update_session_auth_hash(request, user)
            
            return Response({"status": "success"}, status=status.HTTP_200_OK)
            
        # If DRF validation fails (e.g., password too short/common), return the errors
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordAPI(APIView):
    """Handles OTP generation and password resetting for unauthenticated users."""
    permission_classes = [AllowAny]

    def post(self, request):
        action = request.data.get('action')

        # ==========================================
        # STEP 1: VERIFY EMAIL & SEND OTP
        # ==========================================
        if action == 'send_otp':
            email = request.data.get('email')
            recaptcha_response = request.data.get('g-recaptcha-response')
            
            if not email:
                return Response({'status': 'error', 'message': 'Email is required.'})
            if not recaptcha_response:
                return Response({'status': 'error', 'message': 'Security check required.'})

            # 1. Verify Google reCAPTCHA
            recaptcha_secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', None)
            if recaptcha_secret:
                verify_req = requests.post(
                    'https://www.google.com/recaptcha/api/siteverify',
                    data={'secret': recaptcha_secret, 'response': recaptcha_response}
                )
                if not verify_req.json().get('success'):
                    return Response({'status': 'error', 'message': 'reCAPTCHA verification failed.'})

            # 2. Verify User Exists
            user = User.objects.filter(email=email).first()
            if not user:
                return Response({'status': 'error', 'message': 'No active personnel account found with that email.'})

            # 3. Generate a 6-digit OTP
            generated_otp = str(random.randint(100000, 999999))
            
            # 4. Send the Email
            subject = 'SYSTEM ALERT: Password Reset OTP - 950th CEWW'
            message = (
                f"Attention {user.username},\n\n"
                f"A password reset was requested for your account.\n"
                f"Your authorization OTP is: {generated_otp}\n\n"
                f"This code will expire in 5 minutes.\n"
                f"If you did not request this, please contact the system administrator immediately."
            )
            
            try:
                send_mail(
                    subject,
                    message,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@950ceww.local'),
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Email Error: {e}")
                return Response({'status': 'error', 'message': 'Failed to transmit OTP email. Check terminal logs.'})

            # 5. Generate the Math Captcha for Step 2
            num3 = random.randint(1, 10)
            num4 = random.randint(1, 10)
            
            # 6. Store verification data temporarily in the session
            request.session['reset_email'] = email
            request.session['reset_captcha'] = num3 + num4
            request.session['expected_otp'] = generated_otp

            return Response({
                'status': 'success', 
                'num3': num3, 
                'num4': num4
            })

        # ==========================================
        # STEP 2: VERIFY OTP & RESET PASSWORD
        # ==========================================
        elif action == 'reset_password':
            otp = request.data.get('otp')
            new_password = request.data.get('new_password')
            confirm_password = request.data.get('confirm_password')
            captcha_ans = request.data.get('step2_captcha_ans')

            # 1. Validate Form Inputs
            if new_password != confirm_password:
                return Response({'status': 'error', 'message': 'Passwords do not match.'})

            # 2. Validate Math Captcha
            expected_captcha = request.session.get('reset_captcha')
            if str(captcha_ans) != str(expected_captcha):
                return Response({'status': 'error', 'message': 'Incorrect math security answer.'})
            
            # 3. Validate OTP
            expected_otp = request.session.get('expected_otp')
            if str(otp) != str(expected_otp):
                return Response({'status': 'error', 'message': 'Invalid or expired OTP.'})

            # 4. Update the Password
            email = request.session.get('reset_email')
            if email:
                user = User.objects.filter(email=email).first()
                if user:
                    user.set_password(new_password)
                    user.save()
                    
                    # Clean up the session data for security
                    request.session.pop('reset_email', None)
                    request.session.pop('reset_captcha', None)
                    request.session.pop('expected_otp', None)
                    
                    return Response({'status': 'success'})
            
            return Response({'status': 'error', 'message': 'Session expired. Please refresh the page and try again.'})