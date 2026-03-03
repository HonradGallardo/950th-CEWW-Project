from django.http import JsonResponse
from rest_framework import viewsets
from ..models import Asset, IncidentComment, Maintenance, Incident, Notification
from .serializers import AssetSerializer, ChangePasswordSerializer, IncidentCommentSerializer, MaintenanceSerializer, IncidentSerializer, NotificationSerializer, UserSerializer
from rest_framework.decorators import action
from django.contrib.auth.models import User
from rest_framework.response import Response
from rest_framework.views import APIView, settings
from django.db.models import Q, Count
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from django.contrib.auth import update_session_auth_hash
from rest_framework.permissions import IsAuthenticated, AllowAny
import random
from django.core.mail import send_mail
from django.contrib.auth.views import LoginView

from core.api.serializers import (
    UserSerializer, 
    AssetSerializer, 
    MaintenanceSerializer, 
    IncidentSerializer,
    IncidentCommentSerializer,
    NotificationSerializer,
)
class APILoginView(LoginView):
    template_name = 'registration/login.html'

    def form_valid(self, form):
        # If it's an AJAX request, return a JSON response
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.contrib.auth import login
            login(self.request, form.get_user())
            return JsonResponse({
                'status': 'success',
                'redirect_url': '/role-redirect/',
                'mfa_required': False  # Future hook for OTP/MFA
            })
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        return super().form_invalid(form)

class DashboardStatsAPI(APIView):
    """Provides live data for dashboard counters, charts, and tables."""
    def get(self, request):
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
            'asset_name': m.asset.assets_name,
            'technician_name': m.technician.username if m.technician else 'System',
            'status': m.status
        } for m in recent_maint]

        # 5. Table Data: Open Incidents
        open_inc_qs = Incident.objects.filter(status='Open').order_by('-date')[:5]
        inc_list = [{
            'title': i.title,
            'severity': i.severity,
        } for i in open_inc_qs]

        return Response({
            'total_assets': total_assets,
            'assigned_assets': assigned_assets,
            'maintenance_count': maintenance_count,
            'open_incidents': open_incidents_count,
            'asset_labels': asset_labels,
            'asset_totals': asset_totals,
            'severity_labels': severity_labels,
            'severity_totals': severity_totals,
            'recent_maintenance': maint_list, # 🚨 Added for table refresh
            'open_incidents_list': inc_list   # 🚨 Added for table refresh
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
    
    def get_queryset(self):
        """Allows the API to filter by category (assets_type)"""
        queryset = Asset.objects.all()
        category = self.request.query_params.get('category')
        if category and category != 'All':
            queryset = queryset.filter(assets_type=category)
        return queryset

    def perform_update(self, serializer):
        asset = serializer.save()
        self.handle_maintenance_logic(asset)

    def handle_maintenance_logic(self, asset):
        # 1. Look directly at the saved asset's status, not just the raw request data
        if asset.status == 'Maintenance':
            
            # 2. Provide a default fallback if 'type_of_maintenance' isn't in the form
            maint_type = self.request.data.get('type_of_maintenance', 'Auto-Generated Repair')
            
            # 3. Prevent duplicate logs: Check if there's already an active log for this asset
            exists = Maintenance.objects.filter(asset=asset).exclude(status='Completed').exists()
            
            if not exists:
                Maintenance.objects.create(
                    asset=asset,
                    technician=self.request.user,
                    maintenance_type=maint_type,
                    status='In Progress', # You can also set this to 'Queued' if you prefer
                    notes=f"System auto-generated log: {asset.assets_name} was marked as 'Maintenance' from the Asset Registry."
                )
            
class MaintenanceViewSet(viewsets.ModelViewSet):
    queryset = Maintenance.objects.all().select_related('asset', 'technician').order_by('-date')
    serializer_class = MaintenanceSerializer

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
        
        
# 🚨 RESTORED: This is the missing IncidentViewSet
class IncidentViewSet(viewsets.ModelViewSet):
    queryset = Incident.objects.all().order_by('-date')
    serializer_class = IncidentSerializer

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)

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
    serializer_class = NotificationSerializer # Make sure your serializer is linked!
    permission_classes = [IsAuthenticated]    # 🚨 Block anonymous users from hitting this endpoint

    def get_queryset(self):
        # 🚨 Extra safeguard: Return an empty list instead of crashing if the user is somehow logged out
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
            # Make sure RECAPTCHA_SECRET_KEY is in your settings.py
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
                # Security Practice: Do not reveal if an email exists to prevent enumeration.
                # Just return an error telling them the account wasn't found.
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