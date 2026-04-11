import pyotp
from django.http import JsonResponse
from rest_framework import viewsets
from webauthn import generate_authentication_options, generate_registration_options, verify_registration_response
from ..models import Asset, IncidentComment, Maintenance, Incident, Notification
from .serializers import AssetSerializer, ChangePasswordSerializer, IncidentCommentSerializer, MaintenanceSerializer, IncidentSerializer, NotificationSerializer, UserSerializer
from rest_framework.decorators import action, api_view, permission_classes
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
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from webauthn import generate_authentication_options, verify_authentication_response
from rest_framework.authentication import SessionAuthentication
from webauthn.helpers.options_to_json import options_to_json
from core.models import UserPasskey
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


# ==========================================
# STANDARD LOGIN + HYBRID MFA (TOTP or EMAIL)
# ==========================================
class APILoginView(LoginView):
    template_name = 'registration/login.html'

    def form_valid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            user = form.get_user()
            
            # --- MFA LOGIC CHECK ---
            mfa_enabled = True # Toggle to turn MFA entirely on/off

            if mfa_enabled:
                # 1. Check if user has an active TOTP Authenticator App setup
                user_totp = getattr(user, 'totp', None)
                
                if user_totp and user_totp.is_active:
                    # ROUTE A: Use Authenticator App (Google Auth/Authy)
                    self.request.session['mfa_user_id'] = user.id
                    self.request.session['mfa_method'] = 'authenticator'
                    
                    return JsonResponse({
                        'status': 'success',
                        'mfa_required': True 
                    })
                
                else:
                    # ROUTE B: Fallback to Email OTP
                    if not user.email or user.email.strip() == "":
                        return JsonResponse({
                            'status': 'error',
                            'message': 'MFA is required, but no email or Authenticator app is registered.'
                        }, status=400)
                    
                    generated_otp = str(random.randint(100000, 999999))
                    
                    self.request.session['mfa_user_id'] = user.id
                    self.request.session['mfa_method'] = 'email'
                    self.request.session['mfa_expected_otp'] = generated_otp

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

                    return JsonResponse({
                        'status': 'success',
                        'mfa_required': True 
                    })
            else:
                # Standard Login (No MFA Active globally)
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
    """Endpoint to verify the OTP (Email or Authenticator App) entered during login."""
    permission_classes = [AllowAny]

    def post(self, request):
        otp_code = str(request.data.get('otp_code', '')).strip()
        user_id = request.session.get('mfa_user_id')
        mfa_method = request.session.get('mfa_method')

        # Fallback for old active sessions that didn't have 'mfa_method' saved
        if user_id and not mfa_method and 'mfa_expected_otp' in request.session:
            mfa_method = 'email'

        if not user_id or not mfa_method:
            return Response({"message": "Session expired. Please log in again."}, status=400)

        from django.contrib.auth.models import User
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"message": "User account error."}, status=400)

        is_valid = False

        # Verify Google Authenticator Code
        if mfa_method == 'authenticator':
            user_totp = getattr(user, 'totp', None)
            if user_totp and user_totp.is_active:
                totp = pyotp.TOTP(user_totp.secret)
                is_valid = totp.verify(otp_code)
                
        # Verify Email Code
        elif mfa_method == 'email':
            expected_otp = request.session.get('mfa_expected_otp')
            is_valid = (otp_code == str(expected_otp))

        if is_valid:
            # Success! Log them in officially.
            login(request, user)
            
            # Clean up session data
            request.session.pop('mfa_user_id', None)
            request.session.pop('mfa_method', None)
            request.session.pop('mfa_expected_otp', None)
            
            return Response({"status": "success", "redirect_url": "/role-redirect/"})
        else:
            return Response({"message": "Invalid verification code."}, status=400)

# ==========================================
# SETUP TOTP API (QR CODE GENERATION)
# ==========================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_authenticator_qr(request):
    from core.models import UserTOTP
    totp_record, created = UserTOTP.objects.get_or_create(user=request.user)
    
    provisioning_uri = pyotp.totp.TOTP(totp_record.secret).provisioning_uri(
        name=request.user.email or request.user.username,
        issuer_name="950th_CEWW" 
    )
    
    return Response({"qr_uri": provisioning_uri, "secret": totp_record.secret})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_totp_setup(request):
    """Verifies the first code to officially link the app to the account."""
    code = str(request.data.get('code', '')).strip()
    from core.models import UserTOTP
    totp_record = UserTOTP.objects.filter(user=request.user).first()

    if not totp_record:
        return Response({"message": "Setup not initiated."}, status=400)

    # Check if the code they typed matches their new secret
    totp = pyotp.TOTP(totp_record.secret)
    if totp.verify(code):
        totp_record.is_active = True # Officially activate it!
        totp_record.save()
        return Response({"status": "success"})
    else:
        return Response({"message": "Invalid code. Try again."}, status=400)


# ==========================================
# GENERAL DASHBOARD APIS
# ==========================================
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

            # 2. Asset Distribution
            asset_qs = Asset.objects.values('assets_type').annotate(total=Count('id'))
            asset_labels = [item['assets_type'] for item in asset_qs]
            asset_totals = [item['total'] for item in asset_qs]

            # 3. Incident Severity
            severity_qs = Incident.objects.values('severity').annotate(total=Count('id'))
            severity_labels = [item['severity'] for item in severity_qs]
            severity_totals = [item['total'] for item in severity_qs]

            # 4. Table Data: Recent Maintenance
            recent_maint = Maintenance.objects.all().select_related('asset', 'technician').order_by('-date')[:5]
            maint_list = [{
                'id': m.id,
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
            
            # FIX: Format the Python dictionary keys as strings so SQLite can safely match them
            date_to_idx = {d.strftime('%Y-%m-%d'): i for i, d in enumerate(date_list)}

            trend_values = [0] * 7
            inc_trend_qs = Incident.objects.filter(date__date__gte=date_list[0]) \
                .values('date__date').annotate(count=Count('id'))
            for item in inc_trend_qs:
                # Safely convert the database date to a matching string
                db_date_str = str(item['date__date'])[:10]
                idx = date_to_idx.get(db_date_str)
                if idx is not None:
                    # FIX: Use += instead of =
                    trend_values[idx] += item['count']

            # 7. Maintenance Metrics Data
            m_completed = [0] * 7
            m_pending = [0] * 7
            maint_trend_qs = Maintenance.objects.filter(date__date__gte=date_list[0]) \
                .values('date__date', 'status').annotate(count=Count('id'))
            for item in maint_trend_qs:
                db_date_str = str(item['date__date'])[:10]
                idx = date_to_idx.get(db_date_str)
                if idx is not None:
                    # FIX: Use += instead of =
                    if item['status'] == 'Completed':
                        m_completed[idx] += item['count']
                    else:
                        m_pending[idx] += item['count']

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
        
        recent_maint = Maintenance.objects.select_related('asset', 'technician').order_by('-date')[:20]
        maint_list = [{
            'id': m.id,
            'technician_name': m.technician.username if m.technician else 'System',
            'status': m.status,
            'asset_name': m.asset.assets_name if m.asset else 'Unknown Asset',
            'maintenance_type': m.maintenance_type
        } for m in recent_maint]

        assigned = Asset.objects.filter(assigned_to=request.user).order_by('-date_added')[:20]
        asset_list = [{
            'id': a.id,
            'assets_name': a.assets_name,
            'status': a.status,
            'date_added': a.date_added.strftime('%d-%m-%Y')
        } for a in assigned]

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
            'assigned_assets': asset_list  
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

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        if category and category != 'All':
            queryset = queryset.filter(
                Q(maintenance_type__iexact=category) | Q(status__iexact=category)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(technician=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.status == 'Completed':
            asset = instance.asset
            if asset.status != 'Active':
                asset.status = 'Active'
                asset.save()

    def perform_destroy(self, instance):
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

    def perform_update(self, serializer):
        take_over = self.request.data.get('take_over') == 'true'
        
        if take_over:
            serializer.save(assigned_to=self.request.user)
        else:
            serializer.save()

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
        now_local = timezone.localtime(timezone.now())
        today = now_local.date()
        
        date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
        labels = [d.strftime('%a') for d in date_list]
        
        # Format keys as YYYY-MM-DD
        date_to_idx = {d.strftime('%Y-%m-%d'): i for i, d in enumerate(date_list)}

        fixed_assets, pending_assets = [0]*7, [0]*7
        new_incidents, resolved_incidents = [0]*7, [0]*7

        # 1. Maintenance Trends (Using TruncDate)
        maint_qs = Maintenance.objects.filter(date__date__gte=date_list[0]) \
            .annotate(day=TruncDate('date')) \
            .values('day', 'status').annotate(count=Count('id'))
            
        for item in maint_qs:
            if item['day']:
                db_date_str = item['day'].strftime('%Y-%m-%d')
                idx = date_to_idx.get(db_date_str)
                if idx is not None:
                    if item['status'] == 'Completed': 
                        fixed_assets[idx] += item['count']
                    else: 
                        pending_assets[idx] += item['count']

        # 2. Incident Trends (Using TruncDate)
        inc_qs = Incident.objects.filter(date__date__gte=date_list[0]) \
            .annotate(day=TruncDate('date')) \
            .values('day', 'status').annotate(count=Count('id'))
            
        for item in inc_qs:
            if item['day']:
                # Safely format the TruncDate object into a string
                db_date_str = item['day'].strftime('%Y-%m-%d')
                idx = date_to_idx.get(db_date_str)
                
                if idx is not None:
                    if item['status'] in ['Open', 'Investigating']: 
                        new_incidents[idx] += item['count']
                    elif item['status'] == 'Resolved': 
                        resolved_incidents[idx] += item['count']

        # 3. Basic AI Prediction
        avg_incidents = sum(new_incidents) / 7 if sum(new_incidents) > 0 else 0
        predicted = int(avg_incidents * 30) + 2
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
    serializer_class = NotificationSerializer 
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Notification.objects.none()
            
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')
    
class ChangePasswordAPI(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.data.get("old_password")):
                return Response(
                    {"errors": {"old_password": ["Incorrect current password."]}}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user.set_password(serializer.data.get("new_password"))
            user.save()
            update_session_auth_hash(request, user)
            
            return Response({"status": "success"}, status=status.HTTP_200_OK)
            
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        action = request.data.get('action')

        if action == 'send_otp':
            email = request.data.get('email')
            recaptcha_response = request.data.get('g-recaptcha-response')
            
            if not email:
                return Response({'status': 'error', 'message': 'Email is required.'})
            if not recaptcha_response:
                return Response({'status': 'error', 'message': 'Security check required.'})

            recaptcha_secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', None)
            if recaptcha_secret:
                verify_req = requests.post(
                    'https://www.google.com/recaptcha/api/siteverify',
                    data={'secret': recaptcha_secret, 'response': recaptcha_response}
                )
                if not verify_req.json().get('success'):
                    return Response({'status': 'error', 'message': 'reCAPTCHA verification failed.'})

            user = User.objects.filter(email=email).first()
            if not user:
                return Response({'status': 'error', 'message': 'No active personnel account found with that email.'})

            generated_otp = str(random.randint(100000, 999999))
            
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
                    subject, message, getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@950ceww.local'),
                    [email], fail_silently=False,
                )
            except Exception as e:
                print(f"Email Error: {e}")
                return Response({'status': 'error', 'message': 'Failed to transmit OTP email. Check terminal logs.'})

            num3 = random.randint(1, 10)
            num4 = random.randint(1, 10)
            
            request.session['reset_email'] = email
            request.session['reset_captcha'] = num3 + num4
            request.session['expected_otp'] = generated_otp

            return Response({'status': 'success', 'num3': num3, 'num4': num4})

        elif action == 'reset_password':
            otp = request.data.get('otp')
            new_password = request.data.get('new_password')
            confirm_password = request.data.get('confirm_password')
            captcha_ans = request.data.get('step2_captcha_ans')

            if new_password != confirm_password:
                return Response({'status': 'error', 'message': 'Passwords do not match.'})

            expected_captcha = request.session.get('reset_captcha')
            if str(captcha_ans) != str(expected_captcha):
                return Response({'status': 'error', 'message': 'Incorrect math security answer.'})
            
            expected_otp = request.session.get('expected_otp')
            if str(otp) != str(expected_otp):
                return Response({'status': 'error', 'message': 'Invalid or expired OTP.'})

            email = request.session.get('reset_email')
            if email:
                user = User.objects.filter(email=email).first()
                if user:
                    user.set_password(new_password)
                    user.save()
                    
                    request.session.pop('reset_email', None)
                    request.session.pop('reset_captcha', None)
                    request.session.pop('expected_otp', None)
                    
                    return Response({'status': 'success'})
            
            return Response({'status': 'error', 'message': 'Session expired. Please refresh the page and try again.'})