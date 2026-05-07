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
from django.contrib.auth import login, update_session_auth_hash, get_user_model
from rest_framework.permissions import IsAuthenticated, AllowAny
import random
from django.views import View
from django.core.mail import send_mail
from django.contrib.auth.views import LoginView
import requests
import json, base64
import pyotp
from core.models import UserTOTP
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

User = get_user_model()

# Ensure these match your local environment
if settings.DEBUG:
    RP_ID = "localhost"
    ORIGIN = "http://localhost:8000"
else:
    RP_ID = "onthego-aims.up.railway.app"
    ORIGIN = "https://onthego-aims.up.railway.app"

class GenerateTOTPAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Connects strictly to the UserTOTP table
            user_totp, created = UserTOTP.objects.get_or_create(user=request.user)
            
            totp = pyotp.TOTP(user_totp.secret)
            qr_uri = totp.provisioning_uri(
                name=request.user.email or request.user.username,
                issuer_name="950th CEWW AIMS"
            )

            return Response({
                "secret": user_totp.secret,
                "qr_uri": qr_uri
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class VerifyTOTPSetupAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code')

        try:
            user_totp = UserTOTP.objects.get(user=request.user)
        except UserTOTP.DoesNotExist:
            return Response({"message": "Setup not initialized."}, status=400)

        if not code:
            return Response({"message": "Verification code is required."}, status=400)

        totp = pyotp.TOTP(user_totp.secret)
        
        # Verify the code
        if totp.verify(code):
            # SUCCESS: Saves the active status to UserTOTP
            user_totp.is_active = True
            user_totp.save()
            return Response({"status": "success"})
        else:
            return Response({"message": "Invalid code. Please try again."}, status=400)

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
            
            # 1. ALWAYS generate an Email OTP fallback in the background
            generated_otp = str(random.randint(100000, 999999))
            self.request.session['mfa_user_id'] = user.id
            self.request.session['mfa_expected_otp'] = generated_otp
            
            # FIX: Force save the session to the database
            self.request.session.save()

            # 2. Check the database for an active Authenticator/TOTP link
            user_totp = UserTOTP.objects.filter(user=user, is_active=True).first()
            has_totp = bool(user_totp)

            # 3. If NO Authenticator is set up, auto-send the Email OTP immediately
            if not has_totp:
                if not user.email:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'MFA required but no email is linked to this account.'
                    }, status=400)
                    
                subject = 'SYSTEM ALERT: Login Verification - 950th CEWW'
                message = f"Attention {user.username},\n\nYour secure login verification code is: {generated_otp}"
                try:
                    # Using getattr to safely fallback if DEFAULT_FROM_EMAIL isn't in settings
                    send_mail(subject, message, getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@950ceww.local'), [user.email], fail_silently=False)
                except Exception as e:
                    print(f"MFA Email failed: {e}")

            # 4. CRITICAL: Always return mfa_required=True to trigger the frontend 6-digit prompt
            obfuscated_email = f"{user.email[:3]}***@{user.email.split('@')[-1]}" if user.email else "your email"
            
            return JsonResponse({
                'status': 'success',
                'mfa_required': True,  # FIXED: Changed from False to True so the frontend stops the redirect
                'has_totp': has_totp,
                'obfuscated_email': obfuscated_email
            })
               
        return super().form_valid(form)

class SendLoginOTPAPI(APIView):
    """Triggered when a user with Authenticator prefers to use Email instead."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        user_id = request.session.get('mfa_user_id')
        expected_otp = request.session.get('mfa_expected_otp')
        
        if not user_id or not expected_otp:
            return Response({"message": "Session expired."}, status=400)
            
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"message": "User not found."}, status=400)
            
        subject = 'SYSTEM ALERT: Login Verification - 950th CEWW'
        message = f"Attention {user.username},\n\nYour secure login verification code is: {expected_otp}\n\nDo not share this code."
        try:
            send_mail(subject, message, getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@950ceww.local'), [user.email], fail_silently=True)
            obfuscated_email = f"{user.email[:3]}***@{user.email.split('@')[-1]}"
            return Response({"status": "success", "message": f"Code sent to {obfuscated_email}"})
        except Exception as e:
            return Response({"message": "Failed to send email. Check server logs."}, status=500)

class VerifyMFAAPI(APIView):
    """Verifies either the Email OTP OR the Google Authenticator code natively."""
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        # FIX: Use DRF's request.data to properly parse application/json payloads
        otp_code = request.data.get('otp_code') 
        
        # We need to access standard Django session variables
        user_id = request.session.get('mfa_user_id')
        expected_otp = request.session.get('mfa_expected_otp')

        if not user_id:
            return JsonResponse({"message": "Session expired. Please log in again."}, status=400)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({"message": "User account error."}, status=400)

        is_valid = False

        # METHOD 1: Check if they typed the code from their Email
        if expected_otp and str(otp_code) == str(expected_otp):
            is_valid = True

        # METHOD 2: Check if they typed the code from Google Authenticator
        if not is_valid:
            user_totp = UserTOTP.objects.filter(user=user, is_active=True).first()
            if user_totp:
                totp = pyotp.TOTP(user_totp.secret)
                if totp.verify(otp_code):
                    is_valid = True

        # IF EITHER MATCHES -> SUCCESS
        if is_valid:
            # 1. Clean up session cleanly
            request.session.pop('mfa_user_id', None)
            request.session.pop('mfa_expected_otp', None)
            
            # 2. Log them in using standard Django auth
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # 3. Force save the session cookie to the database & browser
            request.session.save()
            
            return JsonResponse({"status": "success", "redirect_url": "/role-redirect/"})
        else:
            return JsonResponse({"message": "Invalid code. Please try again."}, status=400)

class DashboardStatsAPI(APIView):
    """Provides live data for dashboard counters, charts, and tables."""
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # MULTI-TENANCY: Base Querysets
            user = request.user
            assets_qs = Asset.objects.all()
            maint_qs = Maintenance.objects.all()
            inc_qs = Incident.objects.all()

            if not user.is_superuser and hasattr(user, 'profile'):
                org = user.profile.organization
                grp = user.profile.unit_group
                assets_qs = assets_qs.filter(Q(assigned_to__profile__organization=org, assigned_to__profile__unit_group=grp) | Q(assigned_to__isnull=True))
                maint_qs = maint_qs.filter(asset__assigned_to__profile__organization=org, asset__assigned_to__profile__unit_group=grp)
                inc_qs = inc_qs.filter(reported_by__profile__organization=org, reported_by__profile__unit_group=grp)

            # 1. Base Summary Metrics
            total_assets = assets_qs.count()
            assigned_assets = assets_qs.exclude(status='Inactive').count()
            maintenance_count = maint_qs.filter(status='In Progress').count()
            open_incidents_count = inc_qs.filter(status='Open').count()

            # 2. Asset Distribution (Bar Chart)
            asset_qs_agg = assets_qs.values('assets_type').annotate(total=Count('id'))
            asset_labels = [item['assets_type'] for item in asset_qs_agg]
            asset_totals = [item['total'] for item in asset_qs_agg]

            # 3. Incident Severity (Doughnut Chart)
            severity_qs = inc_qs.values('severity').annotate(total=Count('id'))
            severity_labels = [item['severity'] for item in severity_qs]
            severity_totals = [item['total'] for item in severity_qs]

            # 4. Table Data: Recent Maintenance
            recent_maint = maint_qs.select_related('asset', 'technician').order_by('-date')[:5]
            maint_list = [{
                'id': m.id,
                # Safe Check: Prevents crash if the DB relationship is missing
                'asset_name': m.asset.assets_name if m.asset else 'Unknown Asset',
                'technician_name': m.technician.username if m.technician else 'System',
                'status': m.status
            } for m in recent_maint]

            # 5. Table Data: Open Incidents
            open_inc_qs = inc_qs.filter(status='Open').order_by('-date')[:5]
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
            inc_trend_qs = inc_qs.filter(date__date__gte=date_list[0]) \
                .values('date__date').annotate(count=Count('id'))
            for item in inc_trend_qs:
                idx = date_to_idx.get(item['date__date'])
                if idx is not None:
                    trend_values[idx] = item['count']

            # 7. Maintenance Metrics Data
            m_completed = [0] * 7
            m_pending = [0] * 7
            maint_trend_qs = maint_qs.filter(date__date__gte=date_list[0]) \
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
        user = request.user
        
        # MULTI-TENANCY: Base Querysets
        assets_qs = Asset.objects.all()
        maint_qs = Maintenance.objects.all()
        inc_qs = Incident.objects.all()

        if not user.is_superuser and hasattr(user, 'profile'):
            org = user.profile.organization
            grp = user.profile.unit_group
            assets_qs = assets_qs.filter(Q(assigned_to__profile__organization=org, assigned_to__profile__unit_group=grp) | Q(assigned_to__isnull=True))
            maint_qs = maint_qs.filter(asset__assigned_to__profile__organization=org, asset__assigned_to__profile__unit_group=grp)
            inc_qs = inc_qs.filter(reported_by__profile__organization=org, reported_by__profile__unit_group=grp)

        total_assets = assets_qs.count()
        
        # Format recent maintenance tasks (ADDED: asset_name and maintenance_type)
        recent_maint = maint_qs.select_related('asset', 'technician').order_by('-date')[:20]
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
        recent_inc = inc_qs.order_by('-date')[:20]
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
    queryset = User.objects.all() # ADDED
    serializer_class = UserSerializer

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.all().prefetch_related('groups', 'profile').order_by('username')
        
        # MULTI-TENANCY FILTERING
        if not user.is_superuser and hasattr(user, 'profile'):
            qs = qs.filter(
                profile__organization=user.profile.organization,
                profile__unit_group=user.profile.unit_group
            )
        return qs

    @action(detail=False, methods=['get'], url_path='live_search')
    def live_search(self, request):
            query = request.GET.get('q', '').strip()
            role = request.GET.get('role', 'ALL').upper()
            
            org_filter = request.GET.get('org', 'ALL')
            group_filter = request.GET.get('group', 'ALL')
            
            users = self.get_queryset()
            
            if query:
                users = users.filter(
                    Q(username__icontains=query) |
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query)
                ).distinct()

            # Filter by Role
            if role != 'ALL':
                users = users.filter(groups__name__iexact=role) if role != 'UNASSIGNED' else users.filter(groups__isnull=True)
            
            # --- 🚨 UPDATED: Execute Org & Group Database Queries 🚨 ---
            if org_filter != 'ALL':
                if org_filter == 'UNASSIGNED':
                    # Catch users with NO profile, or an empty organization field
                    users = users.filter(Q(profile__organization__isnull=True) | Q(profile__organization__exact=''))
                else:
                    users = users.filter(profile__organization__iexact=org_filter)
                
            if group_filter != 'ALL':
                if group_filter == 'UNASSIGNED':
                    # Catch users with NO profile, or an empty group field
                    users = users.filter(Q(profile__unit_group__isnull=True) | Q(profile__unit_group__exact=''))
                else:
                    users = users.filter(profile__unit_group__iexact=group_filter)
            
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
                    'organization': u.profile.organization if has_profile and u.profile.organization else 'Not Assigned',
                    'unit_group': u.profile.unit_group if has_profile and u.profile.unit_group else 'Not Assigned',
                    'image_url': img_url
                })
            
            return Response(data)
    
class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all() # ADDED
    serializer_class = AssetSerializer

    # MULTI-TENANT QUERYSET
    def get_queryset(self):
        queryset = Asset.objects.all()
        user = self.request.user
        
        if not user.is_superuser and hasattr(user, 'profile'):
            queryset = queryset.filter(
                Q(assigned_to__profile__organization=user.profile.organization,
                  assigned_to__profile__unit_group=user.profile.unit_group) |
                Q(assigned_to__isnull=True)
            )

        category = self.request.query_params.get('category')
        if category and category != 'All':
            queryset = queryset.filter(
                Q(assets_type__iexact=category) | Q(status__iexact=category)
            )
        return queryset

    def perform_create(self, serializer):
        asset = serializer.save(assigned_to=self.request.user)
        
        # FIX: Manually trigger the notification to the database so the frontend can catch it
        Notification.objects.create(
            recipient=self.request.user, 
            message=f"New IT Asset registered: {asset.assets_name}"
        )
        
        self.handle_maintenance_logic(asset)

    def perform_update(self, serializer):
        asset = serializer.save()
        self.handle_maintenance_logic(asset)

    def handle_maintenance_logic(self, asset):
        # 1. ASSET GOES INTO MAINTENANCE
        if asset.status in ['Maintenance', 'Under Maintenance']:
            
            maint_type = self.request.data.get('maintenance_reason', 'Auto-Generated Repair')
            faulty_hw = self.request.data.get('faulty_hardware_part', None)
            sw_issue = self.request.data.get('software_issue_type', None)

            if not faulty_hw: faulty_hw = None
            if not sw_issue: sw_issue = None

            asset.maintenance_reason = maint_type
            asset.faulty_hardware_part = faulty_hw
            asset.software_issue_type = sw_issue
            asset.save(update_fields=['maintenance_reason', 'faulty_hardware_part', 'software_issue_type'])

            exists = Maintenance.objects.filter(asset=asset).exclude(status='Completed').exists()

            if not exists:
                Maintenance.objects.create(
                    asset=asset,
                    technician=self.request.user,
                    maintenance_type=maint_type,
                    faulty_hardware_part=faulty_hw, 
                    software_issue_type=sw_issue,   
                    status='In Progress',
                    notes=f"System auto-generated log: {asset.assets_name} was marked as 'Maintenance'."
                )
                
        # 2. ASSET IS REACTIVATED (NEW LOGIC)
        elif asset.status == 'Active':
            # Find all open maintenance logs for this specific asset
            open_logs = Maintenance.objects.filter(asset=asset, status='In Progress')
            
            # Close them out automatically
            for log in open_logs:
                log.status = 'Completed'
                log.notes = f"{log.notes}\n\n[System Auto-Update: Task completed because asset was reactivated.]"
                log.save(update_fields=['status', 'notes'])
            
            # Wipe the diagnostic data from the asset profile since it's healthy now
            asset.maintenance_reason = None
            asset.faulty_hardware_part = None
            asset.software_issue_type = None
            asset.save(update_fields=['maintenance_reason', 'faulty_hardware_part', 'software_issue_type'])
                
class MaintenanceViewSet(viewsets.ModelViewSet):
    queryset = Maintenance.objects.all() # ADDED
    permission_classes = [IsAuthenticated] # 🚨 SECURITY: Explicit Auth Requirement
    serializer_class = MaintenanceSerializer

    # MULTI-TENANT QUERYSET
    def get_queryset(self):
        queryset = Maintenance.objects.all().select_related('asset', 'technician').order_by('-date')
        user = self.request.user
        
        if not user.is_superuser and hasattr(user, 'profile'):
            queryset = queryset.filter(
                asset__assigned_to__profile__organization=user.profile.organization,
                asset__assigned_to__profile__unit_group=user.profile.unit_group
            )

        category = self.request.query_params.get('category')
        if category and category != 'All':
            queryset = queryset.filter(
                Q(maintenance_type__iexact=category) | Q(status__iexact=category)
            )
        return queryset

    # SECURITY FIX: Catch 500 Backend Crashes during Save
    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            from rest_framework.exceptions import ValidationError
            if isinstance(e, ValidationError): raise e
            import traceback
            print(traceback.format_exc())
            return Response({"detail": f"BACKEND CRASH: {str(e)}"}, status=500)

    # SECURITY FIX: Catch 500 Backend Crashes during Update
    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            from rest_framework.exceptions import ValidationError
            if isinstance(e, ValidationError): raise e
            import traceback
            print(traceback.format_exc())
            return Response({"detail": f"BACKEND CRASH: {str(e)}"}, status=500)


    def perform_create(self, serializer):
        # CRITICAL API FIX: Force asset relationship if serializer drops it
        asset_id = self.request.data.get('asset') or self.request.data.get('asset_id')
        save_kwargs = {'technician': self.request.user}
        
        # Manually inject the asset_id directly to the database layer
        if asset_id and str(asset_id).isdigit():
            save_kwargs['asset_id'] = int(asset_id)
            
        instance = serializer.save(**save_kwargs)
        
        # 1. SMART LOGIC: If a new maintenance task is started, mark the asset as Under Maintenance
        asset = instance.asset
        if asset and instance.status != 'Completed':
            asset.status = 'Maintenance'
            asset.maintenance_reason = instance.maintenance_type
            asset.faulty_hardware_part = instance.faulty_hardware_part
            asset.software_issue_type = instance.software_issue_type
            asset.save(update_fields=['status', 'maintenance_reason', 'faulty_hardware_part', 'software_issue_type'])
            
        # 2. If it's somehow created as 'Completed' right away, ensure the asset is active
        elif asset and instance.status == 'Completed':
            asset.status = 'Active'
            asset.save(update_fields=['status'])
        
        # FIX: Manually trigger the notification to the database so the frontend can catch it
        Notification.objects.create(
            recipient=self.request.user, 
            message=f"Maintenance task created: {instance.maintenance_type}"
        )

    def perform_update(self, serializer):
        # CRITICAL API FIX: Force asset relationship if serializer drops it
        asset_id = self.request.data.get('asset') or self.request.data.get('asset_id')
        save_kwargs = {}
        
        if asset_id and str(asset_id).isdigit():
            save_kwargs['asset_id'] = int(asset_id)
            
        instance = serializer.save(**save_kwargs)
        
        # SMART LOGIC: Sync changes back to the main Asset profile
        asset = instance.asset
        if asset:
            if instance.status == 'Completed':
                asset.status = 'Active'
            
            # Ensure the asset's diagnostic columns match the updated log
            asset.maintenance_reason = instance.maintenance_type
            asset.faulty_hardware_part = instance.faulty_hardware_part
            asset.software_issue_type = instance.software_issue_type
            asset.save(update_fields=['status', 'maintenance_reason', 'faulty_hardware_part', 'software_issue_type'])

    def perform_destroy(self, instance):
        # Clean up the destroy method to avoid save errors on deleted objects
        asset = instance.asset
        if asset:
            asset.status = 'Active'
            asset.save()
        instance.delete()


class IncidentViewSet(viewsets.ModelViewSet):
    queryset = Incident.objects.all() # ADDED
    serializer_class = IncidentSerializer

    # MULTI-TENANT QUERYSET
    def get_queryset(self):
        queryset = Incident.objects.all().order_by('-date')
        user = self.request.user
        
        if not user.is_superuser and hasattr(user, 'profile'):
            queryset = queryset.filter(
                reported_by__profile__organization=user.profile.organization,
                reported_by__profile__unit_group=user.profile.unit_group
            )

        category = self.request.query_params.get('category')
        if category and category != 'All':
            queryset = queryset.filter(
                Q(severity__iexact=category) | Q(status__iexact=category)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)

    # BULLETPROOF DIAGNOSTIC UPDATE
    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            user = request.user

            current_owner = instance.assigned_to
            current_owner_id = str(current_owner.id) if current_owner else ""
            
            data = request.data.copy()
            
            raw_assigned = data.get('assigned_to', current_owner_id)
            new_owner_id = str(raw_assigned) if raw_assigned not in ['', 'null', 'None', None] else ""

            # --- STRICT AUTHORIZATION ---
            is_owner = (current_owner_id == str(user.id))
            is_unassigned = (current_owner_id == "")
            
            if is_unassigned:
                # REMOVED: 'and not is_superuser'
                if new_owner_id != str(user.id):
                    return Response({"detail": "Access Denied: You must take over this incident to your account first."}, status=403)
            else:
                # REMOVED: 'and not is_superuser'
                if not is_owner:
                    return Response({"detail": "Access Denied: Only the current technician can modify this incident."}, status=403)

            # --- PREVENT DRF VALIDATION CRASHES ---
            # We hide the assignment from DRF entirely so it stops choking on empty strings
            if 'assigned_to' in data:
                del data['assigned_to']

            serializer = self.get_serializer(instance, data=data, partial=partial)
            serializer.is_valid(raise_exception=True)
            updated_instance = serializer.save()

            # --- MANUALLY APPLY HISTORY SAFELY ---
            db_changed = False
            if current_owner_id != new_owner_id:
                if new_owner_id == "":
                    updated_instance.assigned_to = None
                else:
                    updated_instance.assigned_to_id = new_owner_id
                    
                if current_owner:
                    # CRITICAL CHECK: Does your model actually have this field?
                    if hasattr(updated_instance, 'last_technician'):
                        updated_instance.last_technician = current_owner.username
                    else:
                        # Pushes the error directly to your frontend screen!
                        return Response({"detail": "DATABASE ERROR: The field 'last_technician' does not exist in your models.py! Please add it."}, status=500)
                
                db_changed = True

            # Save the manual overrides
            if db_changed:
                updated_instance.save()

            if getattr(instance, '_prefetched_objects_cache', None):
                instance._prefetched_objects_cache = {}

            return Response(self.get_serializer(updated_instance).data)

        except Exception as e:
            # Let normal form validation errors pass through normally
            from rest_framework.exceptions import ValidationError
            if isinstance(e, ValidationError):
                raise e 
                
            # If it's a 500 crash, show the exact Python stack trace in the browser alert!
            import traceback
            print(traceback.format_exc())
            return Response({"detail": f"PYTHON FATAL CRASH: {str(e)}"}, status=500)

    # STRICT DELETION SECURITY
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
    queryset = IncidentComment.objects.all() # ADDED
    serializer_class = IncidentCommentSerializer

    def get_queryset(self):
        queryset = IncidentComment.objects.all().order_by('created_at')
        incident_id = self.request.query_params.get('incident')
        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)
        return queryset

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        
        # FIX: Alert the technician that a new comment was added to the ticket
        if comment.incident and getattr(comment.incident, 'assigned_to', None):
            if comment.incident.assigned_to != self.request.user:
                Notification.objects.create(
                    recipient=comment.incident.assigned_to,
                    message=f"New reply on ticket #{comment.incident.id}: {comment.incident.title}"
                )

class MonitoringDataAPI(APIView):
    def get(self, request):
        try:
            # 1. Ensure exact Timezone matching (fixes the zero-data bug on charts)
            today = timezone.localtime().date()
            date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
            labels = [d.strftime('%a') for d in date_list]
            
            # Map string dates to index for perfectly safe matching
            date_to_idx = {d.strftime('%Y-%m-%d'): i for i, d in enumerate(date_list)}

            fixed_assets, pending_assets = [0]*7, [0]*7
            new_incidents, resolved_incidents = [0]*7, [0]*7

            # Safely create a timezone-aware starting point
            start_date = timezone.make_aware(timezone.datetime.combine(date_list[0], timezone.datetime.min.time()))

            # MULTI-TENANCY FILTERING
            maint_qs = Maintenance.objects.filter(date__gte=start_date)
            inc_qs = Incident.objects.filter(date__gte=start_date)
            assets_qs = Asset.objects.all()

            user = request.user
            if not user.is_superuser and hasattr(user, 'profile'):
                org = user.profile.organization
                grp = user.profile.unit_group
                maint_qs = maint_qs.filter(asset__assigned_to__profile__organization=org, asset__assigned_to__profile__unit_group=grp)
                inc_qs = inc_qs.filter(reported_by__profile__organization=org, reported_by__profile__unit_group=grp)
                assets_qs = assets_qs.filter(Q(assigned_to__profile__organization=org, assigned_to__profile__unit_group=grp) | Q(assigned_to__isnull=True))

            # 2. Safely group Maintenance Data in Python (Bypasses Postgres __date bugs)
            for m in maint_qs:
                date_str = timezone.localtime(m.date).strftime('%Y-%m-%d')
                idx = date_to_idx.get(date_str)
                if idx is not None:
                    if m.status in ['Completed', 'Resolved']:
                        fixed_assets[idx] += 1
                    else:
                        pending_assets[idx] += 1

            # 3. Safely group Incident Data in Python
            for inc in inc_qs:
                date_str = timezone.localtime(inc.date).strftime('%Y-%m-%d')
                idx = date_to_idx.get(date_str)
                if idx is not None:
                    # Accurately count all resolved variations
                    if inc.status in ['Resolved', 'Closed', 'Completed']:
                        resolved_incidents[idx] += 1
                    else:
                        new_incidents[idx] += 1

            # 4. Accurate AI Predictive Forecasting
            total_recent = sum(new_incidents)
            avg_incidents = total_recent / 7.0
            
            # Forecast algorithm: Average * 30 days + active backlog penalty
            active_backlog = sum(pending_assets)
            predicted = int(avg_incidents * 30) + int(active_backlog * 0.5)
            
            is_rising = new_incidents[-1] > avg_incidents or active_backlog > 5

            # 5. Get true asset types for risk profiling
            asset_types = list(assets_qs.values('assets_type').annotate(total=Count('id')))

            return Response({
                'labels': labels,
                'fixed_assets': fixed_assets,
                'pending_assets': pending_assets,
                'new_incidents': new_incidents,
                'resolved_incidents': resolved_incidents,
                'predicted_incidents': max(predicted, 0),
                'confidence_level': 'High' if total_recent > 3 else ('Medium' if total_recent > 0 else 'Low'),
                'is_rising': is_rising,
                'asset_types': asset_types
            })
        except Exception as e:
            import traceback
            print("ANALYTICS API CRASHED:", traceback.format_exc())
            return Response({"error": str(e)}, status=500)
        
class NotificationViewSet(viewsets.ModelViewSet):
    """API for dynamic notification bell updates."""
    queryset = Notification.objects.all() # ADDED
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

            # FIX: Enforce is_active=True to prevent targeting disabled accounts
            user = User.objects.filter(email=email, is_active=True).first()
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

            # FIX: Prevent the API from accepting empty strings if the frontend fails
            if not new_password or new_password.strip() == "":
                return Response({'status': 'error', 'message': 'Password cannot be empty.'})

            if len(new_password) < 8:
                return Response({'status': 'error', 'message': 'Password must be at least 8 characters long.'})

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
                # FIX: Match the is_active=True enforcement from Step 1
                user = User.objects.filter(email=email, is_active=True).first()
                if user:
                    user.set_password(new_password)
                    user.save()
                    
                    # Clean up the session data for security
                    request.session.pop('reset_email', None)
                    request.session.pop('reset_captcha', None)
                    request.session.pop('expected_otp', None)
                    
                    return Response({'status': 'success'})
            
            return Response({'status': 'error', 'message': 'Session expired. Please refresh the page and try again.'})